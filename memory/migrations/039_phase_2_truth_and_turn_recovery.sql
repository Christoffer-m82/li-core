BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version='0.38') THEN
    RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Migration 039 requires applied schema 0.38';
  END IF;
  IF EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version='0.39') THEN
    RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Schema version 0.39 is already claimed';
  END IF;
END $$;

ALTER TABLE li_runtime_data.chat_turns
  ADD COLUMN attempt_token UUID,
  ADD COLUMN external_effect_started BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN external_effect_state TEXT NOT NULL DEFAULT 'none'
    CHECK(external_effect_state IN ('none','prepared','dispatched','completed','no_effect')),
  ADD COLUMN progress_stage TEXT NOT NULL DEFAULT 'accepted'
    CHECK(progress_stage IN ('accepted','conversation_bound','message_saved',
      'action_prepared','provider_dispatched','provider_completed','provider_no_effect',
      'model_started','response_ready'));

CREATE TEMP TABLE migration_039_authority_state(added_owner BOOLEAN,added_create BOOLEAN) ON COMMIT DROP;
INSERT INTO migration_039_authority_state SELECT
 NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),
 NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_039_authority_state) THEN EXECUTE 'GRANT li_memory_function_owner TO postgres'; END IF;
 IF (SELECT added_create FROM migration_039_authority_state) THEN EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner'; END IF;
END $$;
SET LOCAL ROLE li_memory_function_owner;

CREATE OR REPLACE FUNCTION li_api.begin_chat_turn(p_id UUID,p_request_hash TEXT)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE t li_runtime_data.chat_turns%ROWTYPE; v_user UUID; v_now TIMESTAMPTZ:=NOW();
 v_outcome TEXT; v_inserted INTEGER; v_attempt UUID:=gen_random_uuid();
BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 IF p_id IS NULL OR p_request_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'Invalid chat turn'; END IF;
 INSERT INTO li_runtime_data.chat_turns(id,owner_user_id,request_hash,lease_expires_at,attempt_token)
 VALUES(p_id,v_user,p_request_hash,v_now+INTERVAL '3 minutes',v_attempt) ON CONFLICT(id) DO NOTHING;
 GET DIAGNOSTICS v_inserted=ROW_COUNT;
 SELECT * INTO t FROM li_runtime_data.chat_turns WHERE id=p_id AND owner_user_id=v_user FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Chat turn identity does not match owner'; END IF;
 IF t.request_hash<>p_request_hash THEN
   RETURN jsonb_build_object('outcome','conflict','turn_id',t.id,'state',t.state);
 END IF;

 -- Response retention is enforced on the read path as well as by the scheduled worker.
 IF t.state='completed' AND t.response_expires_at<=v_now THEN
   UPDATE li_runtime_data.chat_turns SET state='replay_expired',response=NULL,updated_at=v_now
     WHERE id=p_id RETURNING * INTO t;
 END IF;

 IF t.state='completed' THEN v_outcome:='replay';
 ELSIF t.state='replay_expired' THEN v_outcome:='replay_expired';
 ELSIF t.state='uncertain' THEN v_outcome:='uncertain';
 ELSIF t.state='failed' OR (t.state='accepted' AND t.lease_expires_at<=v_now
     AND t.external_effect_state IN ('none','prepared','no_effect')) THEN
   UPDATE li_runtime_data.chat_turns SET state='accepted',finished_at=NULL,
     lease_expires_at=v_now+INTERVAL '3 minutes',attempt_count=attempt_count+1,
     attempt_token=v_attempt,
     progress_stage=CASE WHEN progress_stage IN (
       'action_prepared','provider_no_effect','model_started','response_ready')
       THEN 'message_saved' ELSE progress_stage END,
     updated_at=v_now
     WHERE id=p_id RETURNING * INTO t;
   v_outcome:='accepted';
 ELSIF v_inserted=1 THEN v_outcome:='accepted';
 ELSIF t.lease_expires_at>v_now THEN v_outcome:='in_progress';
 ELSE
   UPDATE li_runtime_data.chat_turns SET state='uncertain',finished_at=v_now,updated_at=v_now
     WHERE id=p_id RETURNING * INTO t;
   v_outcome:='uncertain';
 END IF;
 RETURN jsonb_build_object('outcome',v_outcome,'turn_id',t.id,'conversation_id',t.conversation_id,
   'state',t.state,'attempt_count',t.attempt_count,'attempt_token',t.attempt_token,
   'progress_stage',t.progress_stage,'external_effect_state',t.external_effect_state,
   'response',t.response);
END $$;

CREATE FUNCTION li_api.mark_chat_turn_progress(
 p_id UUID,p_request_hash TEXT,p_attempt_token UUID,p_stage TEXT)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE t li_runtime_data.chat_turns%ROWTYPE; v_user UUID; v_current INTEGER; v_next INTEGER;
BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 SELECT * INTO t FROM li_runtime_data.chat_turns WHERE id=p_id AND owner_user_id=v_user FOR UPDATE;
 IF NOT FOUND OR t.request_hash<>p_request_hash OR t.state<>'accepted'
   OR t.attempt_token IS DISTINCT FROM p_attempt_token THEN
   RAISE EXCEPTION 'Chat turn attempt is stale or unavailable';
 END IF;
 v_current:=CASE t.progress_stage WHEN 'accepted' THEN 0 WHEN 'conversation_bound' THEN 1
   WHEN 'message_saved' THEN 2 WHEN 'action_prepared' THEN 3
   WHEN 'provider_dispatched' THEN 4 WHEN 'provider_completed' THEN 5
   WHEN 'provider_no_effect' THEN 5 WHEN 'model_started' THEN 6
   WHEN 'response_ready' THEN 7 ELSE -1 END;
 v_next:=CASE p_stage WHEN 'accepted' THEN 0 WHEN 'conversation_bound' THEN 1
   WHEN 'message_saved' THEN 2 WHEN 'action_prepared' THEN 3
   WHEN 'provider_dispatched' THEN 4 WHEN 'provider_completed' THEN 5
   WHEN 'provider_no_effect' THEN 5 WHEN 'model_started' THEN 6
   WHEN 'response_ready' THEN 7 ELSE -1 END;
 IF v_next<0 OR v_next<v_current THEN RAISE EXCEPTION 'Invalid chat turn progress transition'; END IF;
 IF (t.external_effect_state='completed' AND p_stage='provider_no_effect')
   OR (t.external_effect_state='no_effect' AND p_stage IN (
     'provider_dispatched','provider_completed')) THEN
   RAISE EXCEPTION 'Contradictory external effect transition';
 END IF;
 UPDATE li_runtime_data.chat_turns SET progress_stage=p_stage,
   external_effect_started=(external_effect_started OR p_stage IN (
     'provider_dispatched','provider_completed')),
   external_effect_state=CASE p_stage
     WHEN 'action_prepared' THEN 'prepared'
     WHEN 'provider_dispatched' THEN 'dispatched'
     WHEN 'provider_completed' THEN 'completed'
     WHEN 'provider_no_effect' THEN 'no_effect'
     ELSE external_effect_state END,
   lease_expires_at=NOW()+INTERVAL '3 minutes',updated_at=NOW()
   WHERE id=p_id RETURNING * INTO t;
 RETURN jsonb_build_object('turn_id',t.id,'state',t.state,'progress_stage',t.progress_stage,
   'external_effect_state',t.external_effect_state);
END $$;

CREATE FUNCTION li_api.finish_chat_turn_attempt(
 p_id UUID,p_request_hash TEXT,p_attempt_token UUID,p_state TEXT,p_response JSONB DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE t li_runtime_data.chat_turns%ROWTYPE; v_user UUID; v_now TIMESTAMPTZ:=NOW();
BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 SELECT * INTO t FROM li_runtime_data.chat_turns WHERE id=p_id AND owner_user_id=v_user FOR UPDATE;
 IF NOT FOUND OR t.request_hash<>p_request_hash OR t.attempt_token IS DISTINCT FROM p_attempt_token THEN
   RAISE EXCEPTION 'Chat turn attempt is stale or unavailable';
 END IF;
 IF p_state NOT IN ('completed','failed','uncertain')
   OR (p_state='completed' AND (p_response IS NULL OR jsonb_typeof(p_response)<>'object'))
   OR (p_state<>'completed' AND p_response IS NOT NULL) THEN
   RAISE EXCEPTION 'Invalid chat turn completion';
 END IF;
 IF t.state<>'accepted' THEN
   IF t.state<>p_state THEN RAISE EXCEPTION 'Chat turn has a different final state'; END IF;
   RETURN jsonb_build_object('outcome','replay','turn_id',t.id,'state',t.state,'response',t.response);
 END IF;
 UPDATE li_runtime_data.chat_turns SET state=p_state,response=p_response,
   finished_at=v_now,updated_at=v_now WHERE id=p_id RETURNING * INTO t;
 RETURN jsonb_build_object('outcome','recorded','turn_id',t.id,'state',t.state,'response',t.response);
END $$;

-- Preserve a private correction source even when the superseded memory was shareable.
CREATE FUNCTION li_api.correct_explicit_memory(
 p_memory_id UUID,p_new_value_text TEXT,p_new_domain TEXT,
 p_new_title TEXT,p_source_reference TEXT,p_source_private_to_li BOOLEAN)
RETURNS TABLE(previous_memory_id UUID,memory_id UUID,outcome TEXT)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_memory,li_api,pg_catalog,pg_temp AS $$
DECLARE v_previous UUID; v_memory UUID; v_outcome TEXT;
BEGIN
 SELECT r.previous_memory_id,r.memory_id,r.outcome INTO v_previous,v_memory,v_outcome
 FROM li_api.correct_explicit_memory(
   p_memory_id,p_new_value_text,p_new_domain,p_new_title,p_source_reference) r;
 IF COALESCE(p_source_private_to_li,FALSE) THEN
   UPDATE li_memory.memory_records SET private_to_li=TRUE,updated_at=NOW()
   WHERE id=v_memory;
 END IF;
 RETURN QUERY SELECT v_previous,v_memory,v_outcome;
END $$;

-- Enforce the inference/truth pairing inside the canonical write boundary as well as in Theo's runtime.
CREATE OR REPLACE FUNCTION li_api.review_memory_proposal(
 p_proposal_id UUID,p_decision TEXT,p_review_note TEXT DEFAULT NULL,
 p_final_truth_status TEXT DEFAULT NULL,p_final_temporal_status TEXT DEFAULT NULL,
 p_final_confidence NUMERIC DEFAULT NULL)
RETURNS TABLE(proposal_id UUID,proposal_status TEXT,memory_id UUID,outcome TEXT)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_memory,li_api,pg_catalog,pg_temp AS $$
DECLARE v_status TEXT; v_class TEXT; v_truth TEXT;
BEGIN
 SELECT p.status,p.proposed_class,p.proposed_truth_status INTO v_status,v_class,v_truth
 FROM li_memory.memory_write_proposals p WHERE p.id=p_proposal_id FOR UPDATE;
 IF v_status IS NULL THEN RAISE EXCEPTION 'Memory proposal not found: %',p_proposal_id; END IF;
 IF p_decision='approve' AND v_status='needs_user_confirmation' THEN
   RAISE EXCEPTION 'Owner confirmation is required before this proposal can be approved';
 END IF;
 IF p_decision='approve' AND (v_class='inference' OR v_truth='inferred')
   AND COALESCE(p_final_truth_status,v_truth,'inferred')<>'inferred' THEN
   RAISE EXCEPTION 'Inference proposals must retain inferred truth status';
 END IF;
 RETURN QUERY SELECT * FROM li_api.review_memory_proposal_internal(
   p_proposal_id,p_decision,p_review_note,p_final_truth_status,p_final_temporal_status,p_final_confidence);
END $$;

RESET ROLE;
REVOKE ALL ON FUNCTION li_api.mark_chat_turn_progress(UUID,TEXT,UUID,TEXT),
 li_api.finish_chat_turn_attempt(UUID,TEXT,UUID,TEXT,JSONB),
 li_api.correct_explicit_memory(UUID,TEXT,TEXT,TEXT,TEXT,BOOLEAN) FROM PUBLIC,anon,authenticated,
 service_role,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.mark_chat_turn_progress(UUID,TEXT,UUID,TEXT),
 li_api.finish_chat_turn_attempt(UUID,TEXT,UUID,TEXT,JSONB),
 li_api.correct_explicit_memory(UUID,TEXT,TEXT,TEXT,TEXT,BOOLEAN) TO li_memory_api;
REVOKE ALL ON FUNCTION li_api.review_memory_proposal(UUID,TEXT,TEXT,TEXT,TEXT,NUMERIC)
 FROM PUBLIC,anon,authenticated,service_role,li_memory_api,li_memory_owner_confirmation,
 li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.review_memory_proposal(UUID,TEXT,TEXT,TEXT,TEXT,NUMERIC)
 TO li_memory_theo;
DO $$ BEGIN
 IF (SELECT added_create FROM migration_039_authority_state) THEN EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner'; END IF;
 IF (SELECT added_owner FROM migration_039_authority_state) THEN EXECUTE 'REVOKE li_memory_function_owner FROM postgres'; END IF;
END $$;

DO $$
DECLARE function_name TEXT;
BEGIN
 FOREACH function_name IN ARRAY ARRAY[
  'li_api.begin_chat_turn(uuid,text)','li_api.mark_chat_turn_progress(uuid,text,uuid,text)',
  'li_api.finish_chat_turn_attempt(uuid,text,uuid,text,jsonb)',
  'li_api.correct_explicit_memory(uuid,text,text,text,text,boolean)',
  'li_api.review_memory_proposal(uuid,text,text,text,text,numeric)'
 ] LOOP
  IF (SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
      WHERE p.oid=function_name::REGPROCEDURE) IS DISTINCT FROM 'li_memory_function_owner' THEN
   RAISE EXCEPTION 'Function % has unexpected owner',function_name;
  END IF;
 END LOOP;
 IF pg_catalog.has_function_privilege('li_artifact_retention',
      'li_api.finish_chat_turn_attempt(uuid,text,uuid,text,jsonb)','EXECUTE')
   OR pg_catalog.has_function_privilege('li_memory_api',
      'li_api.review_memory_proposal(uuid,text,text,text,text,numeric)','EXECUTE') THEN
   RAISE EXCEPTION 'Phase 2 function privileges are broader than intended';
 END IF;
END $$;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.39','Phase 2 truth pairing and fenced recoverable chat attempts');
COMMIT;
