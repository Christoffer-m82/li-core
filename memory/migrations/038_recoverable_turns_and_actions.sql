BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version='0.37') THEN
    RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Migration 038 requires applied schema 0.37';
  END IF;
  IF EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version='0.38') THEN
    RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Schema version 0.38 is already claimed';
  END IF;
END $$;

CREATE TABLE li_runtime_data.chat_turns (
  id UUID PRIMARY KEY,
  owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
  conversation_id UUID REFERENCES li_conversation.conversations(id) ON DELETE CASCADE,
  request_hash TEXT NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
  state TEXT NOT NULL DEFAULT 'accepted'
    CHECK(state IN ('accepted','completed','replay_expired','failed','uncertain')),
  attempt_count INTEGER NOT NULL DEFAULT 1 CHECK(attempt_count BETWEEN 1 AND 20),
  lease_expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW()+INTERVAL '3 minutes',
  response JSONB,
  response_expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW()+INTERVAL '30 days',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  CHECK((state='completed')=(response IS NOT NULL)),
  CHECK((state='accepted')=(finished_at IS NULL)),
  CHECK(state<>'completed' OR conversation_id IS NOT NULL)
);
CREATE INDEX chat_turns_owner_updated_idx
  ON li_runtime_data.chat_turns(owner_user_id,updated_at DESC);
CREATE INDEX chat_turns_response_expiry_idx
  ON li_runtime_data.chat_turns(response_expires_at,id) WHERE state='completed';
ALTER TABLE li_runtime_data.chat_turns ENABLE ROW LEVEL SECURITY;
CREATE POLICY chat_turn_function_access ON li_runtime_data.chat_turns FOR ALL
  TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
GRANT SELECT,INSERT,UPDATE ON li_runtime_data.chat_turns TO li_memory_function_owner;

-- Add an explicit state for writes whose provider outcome could not be observed.
DO $$
DECLARE c RECORD;
BEGIN
  FOR c IN SELECT conname,pg_get_constraintdef(oid) AS definition
    FROM pg_constraint
    WHERE conrelid='li_runtime_data.action_intents'::REGCLASS AND contype='c'
  LOOP
    IF c.definition LIKE '%state%' AND c.definition LIKE '%resolved_at%'
      OR (c.definition LIKE '%state%' AND c.definition LIKE '%owner_confirmation_required%'
          AND c.definition LIKE '%executing%') THEN
      EXECUTE format('ALTER TABLE li_runtime_data.action_intents DROP CONSTRAINT %I',c.conname);
    END IF;
  END LOOP;
END $$;
ALTER TABLE li_runtime_data.action_intents
  ADD CONSTRAINT action_intents_state_check_v038 CHECK(state IN
    ('proposed','owner_confirmation_required','executing','succeeded','failed','uncertain','denied','expired')),
  ADD CONSTRAINT action_intents_resolution_check_v038 CHECK(
    (state IN ('succeeded','failed','uncertain','denied','expired'))=(resolved_at IS NOT NULL));

CREATE TEMP TABLE migration_038_authority_state(added_owner BOOLEAN,added_create BOOLEAN) ON COMMIT DROP;
INSERT INTO migration_038_authority_state SELECT
 NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),
 NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_038_authority_state) THEN EXECUTE 'GRANT li_memory_function_owner TO postgres'; END IF;
 IF (SELECT added_create FROM migration_038_authority_state) THEN EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner'; END IF;
END $$;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.begin_chat_turn(p_id UUID,p_request_hash TEXT)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE t li_runtime_data.chat_turns%ROWTYPE; v_user UUID; v_now TIMESTAMPTZ:=NOW(); v_outcome TEXT;
 v_inserted INTEGER;
BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 IF p_id IS NULL OR p_request_hash !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'Invalid chat turn'; END IF;
 INSERT INTO li_runtime_data.chat_turns(id,owner_user_id,request_hash,lease_expires_at)
 VALUES(p_id,v_user,p_request_hash,v_now+INTERVAL '3 minutes') ON CONFLICT(id) DO NOTHING;
 GET DIAGNOSTICS v_inserted=ROW_COUNT;
 SELECT * INTO t FROM li_runtime_data.chat_turns WHERE id=p_id AND owner_user_id=v_user FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Chat turn identity does not match owner'; END IF;
 IF t.request_hash<>p_request_hash THEN
   RETURN jsonb_build_object('outcome','conflict','turn_id',t.id,'state',t.state);
 END IF;
 IF t.state='completed' THEN v_outcome:='replay';
 ELSIF t.state='replay_expired' THEN v_outcome:='replay_expired';
 ELSIF t.state='uncertain' THEN v_outcome:='uncertain';
 ELSIF t.state='failed' THEN
   UPDATE li_runtime_data.chat_turns SET state='accepted',finished_at=NULL,
     lease_expires_at=v_now+INTERVAL '3 minutes',attempt_count=attempt_count+1,updated_at=v_now
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
   'state',t.state,'attempt_count',t.attempt_count,'response',t.response);
END $$;

CREATE FUNCTION li_api.bind_chat_turn_conversation(p_id UUID,p_request_hash TEXT,p_conversation UUID)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,li_conversation,pg_catalog,pg_temp AS $$
DECLARE t li_runtime_data.chat_turns%ROWTYPE; v_user UUID;
BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 SELECT * INTO t FROM li_runtime_data.chat_turns WHERE id=p_id AND owner_user_id=v_user FOR UPDATE;
 IF NOT FOUND OR t.request_hash<>p_request_hash OR t.state<>'accepted' THEN
   RAISE EXCEPTION 'Chat turn cannot be bound';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM li_conversation.conversations
   WHERE id=p_conversation AND owner_user_id=v_user) THEN RAISE EXCEPTION 'Conversation not found'; END IF;
 IF t.conversation_id IS NOT NULL AND t.conversation_id<>p_conversation THEN
   RAISE EXCEPTION 'Chat turn is already bound to another conversation';
 END IF;
 UPDATE li_runtime_data.chat_turns SET conversation_id=p_conversation,updated_at=NOW() WHERE id=p_id RETURNING * INTO t;
 RETURN jsonb_build_object('turn_id',t.id,'conversation_id',t.conversation_id,'state',t.state);
END $$;

CREATE FUNCTION li_api.finish_chat_turn(p_id UUID,p_request_hash TEXT,p_state TEXT,p_response JSONB DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE t li_runtime_data.chat_turns%ROWTYPE; v_user UUID; v_now TIMESTAMPTZ:=NOW();
BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 SELECT * INTO t FROM li_runtime_data.chat_turns WHERE id=p_id AND owner_user_id=v_user FOR UPDATE;
 IF NOT FOUND OR t.request_hash<>p_request_hash THEN RAISE EXCEPTION 'Chat turn not found'; END IF;
 IF p_state NOT IN ('completed','failed','uncertain')
   OR (p_state='completed' AND (p_response IS NULL OR jsonb_typeof(p_response)<>'object'))
   OR (p_state<>'completed' AND p_response IS NOT NULL) THEN RAISE EXCEPTION 'Invalid chat turn completion'; END IF;
 IF t.state<>'accepted' THEN
   IF t.state<>p_state THEN RAISE EXCEPTION 'Chat turn has a different final state'; END IF;
   RETURN jsonb_build_object('outcome','replay','turn_id',t.id,'state',t.state,'response',t.response);
 END IF;
 UPDATE li_runtime_data.chat_turns SET state=p_state,response=p_response,finished_at=v_now,updated_at=v_now
   WHERE id=p_id RETURNING * INTO t;
 RETURN jsonb_build_object('outcome','recorded','turn_id',t.id,'state',t.state,'response',t.response);
END $$;

CREATE OR REPLACE FUNCTION li_api.resolve_action_intent(
 p_id UUID,p_decision TEXT,p_owner_confirmation TEXT DEFAULT NULL,
 p_execution_status TEXT DEFAULT NULL,p_result JSONB DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE a li_runtime_data.action_intents%ROWTYPE; v_user UUID; v_now TIMESTAMPTZ:=NOW();
 v_public JSONB; v_outcome TEXT; v_final TEXT;
BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 SELECT * INTO a FROM li_runtime_data.action_intents WHERE id=p_id AND owner_user_id=v_user FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Action intent not found'; END IF;
 IF a.state IN ('succeeded','failed','uncertain','denied','expired') THEN v_outcome:='resolved';
 ELSIF p_decision='complete' AND a.state='executing' AND p_execution_status IN ('succeeded','failed','uncertain') THEN
   UPDATE li_runtime_data.action_intents SET state=p_execution_status,resolved_at=v_now,result=COALESCE(p_result,'{}') WHERE id=p_id;
   INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome,error_metadata)
    VALUES(p_id,v_user,'provider','executing',p_execution_status,p_execution_status,
      CASE WHEN p_execution_status='failed' THEN jsonb_build_object('category','provider_failure')
           WHEN p_execution_status='uncertain' THEN jsonb_build_object('category','provider_outcome_unobserved') ELSE '{}' END);
   IF p_execution_status IN ('succeeded','failed') AND cardinality(a.specialist_interaction_ids)>0 THEN
     PERFORM li_api.record_specialist_action_attribution(a.id,a.request_id,a.specialist_interaction_ids,a.action_type,p_execution_status);
   END IF;
   v_outcome:='resolved';
 ELSIF a.expires_at<=v_now THEN
   v_final:=CASE WHEN a.state='executing' THEN 'uncertain' ELSE 'expired' END;
   UPDATE li_runtime_data.action_intents SET state=v_final,resolved_at=v_now WHERE id=p_id;
   INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome,error_metadata)
    VALUES(p_id,v_user,'system',a.state,v_final,
      CASE WHEN v_final='uncertain' THEN 'execution_lease_expired_outcome_unknown' ELSE 'expired_without_attempt' END,
      CASE WHEN v_final='uncertain' THEN jsonb_build_object('category','provider_outcome_unobserved') ELSE '{}' END);
   v_outcome:='resolved';
 ELSIF p_decision='deny' AND a.state IN ('proposed','owner_confirmation_required') THEN
   UPDATE li_runtime_data.action_intents SET state='denied',resolved_at=v_now WHERE id=p_id;
   INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome)
    VALUES(p_id,v_user,'owner',a.state,'denied','denied_without_attempt'); v_outcome:='resolved';
 ELSIF p_decision='approve' AND a.state='owner_confirmation_required' THEN
   IF p_owner_confirmation IS DISTINCT FROM 'confirm_permanent_agent_change' THEN v_outcome:='owner_confirmation_required';
   ELSE v_outcome:='owner_executor_required';
     INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome)
      VALUES(p_id,v_user,'owner',a.state,a.state,'owner_confirmed_existing_executor_required'); END IF;
 ELSIF p_decision='approve' AND a.state='proposed' THEN
   UPDATE li_runtime_data.action_intents SET state='executing' WHERE id=p_id;
   INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome)
    VALUES(p_id,v_user,'owner','proposed','executing','approved_and_claimed'); v_outcome:='execute';
 ELSE RAISE EXCEPTION 'Invalid or replayed action intent transition'; END IF;
 SELECT jsonb_build_object('intent_id',x.id,'request_id',x.request_id,'action_type',x.action_type,
   'summary',x.payload_summary,'approval_state',x.state,'approval_required',x.approval_required,
   'owner_confirmation_required',x.owner_confirmation_required,'created_at',x.created_at,
   'expires_at',x.expires_at,'resolved_at',x.resolved_at,'result',x.result) INTO v_public
  FROM li_runtime_data.action_intents x WHERE x.id=p_id;
 RETURN jsonb_build_object('outcome',v_outcome,'intent',v_public,'payload',a.payload,
  'payload_hash',a.payload_hash,'request_id',a.request_id,'action_type',a.action_type,
  'specialist_interaction_ids',a.specialist_interaction_ids);
END $$;

CREATE OR REPLACE FUNCTION li_api.expire_action_intents(p_limit INTEGER DEFAULT 100)
RETURNS INTEGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_count INTEGER;
BEGIN
 WITH candidates AS (SELECT id,owner_user_id,state FROM li_runtime_data.action_intents
   WHERE state IN ('proposed','owner_confirmation_required','executing') AND expires_at<=NOW()
   ORDER BY expires_at LIMIT LEAST(GREATEST(COALESCE(p_limit,100),1),500) FOR UPDATE SKIP LOCKED),
 updated AS (UPDATE li_runtime_data.action_intents a
   SET state=CASE WHEN c.state='executing' THEN 'uncertain' ELSE 'expired' END,resolved_at=NOW()
   FROM candidates c WHERE a.id=c.id RETURNING a.id,a.owner_user_id,c.state,a.state AS final_state)
 INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome,error_metadata)
 SELECT id,owner_user_id,'system',state,final_state,
   CASE WHEN final_state='uncertain' THEN 'execution_lease_expired_outcome_unknown' ELSE 'expired_without_attempt' END,
   CASE WHEN final_state='uncertain' THEN jsonb_build_object('category','provider_outcome_unobserved') ELSE '{}' END
 FROM updated;
 GET DIAGNOSTICS v_count=ROW_COUNT; RETURN v_count;
END $$;

CREATE FUNCTION li_api.expire_chat_replay_responses(p_limit INTEGER DEFAULT 100)
RETURNS INTEGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,pg_catalog,pg_temp AS $$
DECLARE v_count INTEGER;
BEGIN
 WITH candidates AS (
   SELECT id FROM li_runtime_data.chat_turns
   WHERE state='completed' AND response_expires_at<=NOW()
   ORDER BY response_expires_at,id LIMIT LEAST(GREATEST(COALESCE(p_limit,100),1),500)
   FOR UPDATE SKIP LOCKED
 ), expired AS (
   UPDATE li_runtime_data.chat_turns t
   SET state='replay_expired',response=NULL,updated_at=NOW()
   FROM candidates c WHERE t.id=c.id RETURNING t.id
 ) SELECT count(*) INTO v_count FROM expired;
 RETURN v_count;
END $$;

RESET ROLE;
REVOKE ALL ON FUNCTION li_api.begin_chat_turn(UUID,TEXT),
 li_api.bind_chat_turn_conversation(UUID,TEXT,UUID),li_api.finish_chat_turn(UUID,TEXT,TEXT,JSONB),
 li_api.resolve_action_intent(UUID,TEXT,TEXT,TEXT,JSONB),li_api.expire_action_intents(INTEGER),
 li_api.expire_chat_replay_responses(INTEGER)
 FROM PUBLIC,anon,authenticated,service_role,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.begin_chat_turn(UUID,TEXT),
 li_api.bind_chat_turn_conversation(UUID,TEXT,UUID),li_api.finish_chat_turn(UUID,TEXT,TEXT,JSONB),
 li_api.resolve_action_intent(UUID,TEXT,TEXT,TEXT,JSONB) TO li_memory_api;
GRANT EXECUTE ON FUNCTION li_api.expire_action_intents(INTEGER) TO li_artifact_retention;
GRANT EXECUTE ON FUNCTION li_api.expire_chat_replay_responses(INTEGER) TO li_artifact_retention;
REVOKE ALL PRIVILEGES ON li_runtime_data.chat_turns
 FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,li_memory_theo,
 li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
DO $$ BEGIN
 IF (SELECT added_create FROM migration_038_authority_state) THEN EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner'; END IF;
 IF (SELECT added_owner FROM migration_038_authority_state) THEN EXECUTE 'REVOKE li_memory_function_owner FROM postgres'; END IF;
END $$;

DO $$
DECLARE function_name TEXT;
BEGIN
 FOREACH function_name IN ARRAY ARRAY[
  'li_api.begin_chat_turn(uuid,text)','li_api.bind_chat_turn_conversation(uuid,text,uuid)',
  'li_api.finish_chat_turn(uuid,text,text,jsonb)','li_api.resolve_action_intent(uuid,text,text,text,jsonb)',
  'li_api.expire_action_intents(integer)','li_api.expire_chat_replay_responses(integer)'
 ] LOOP
  IF (SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
      WHERE p.oid=function_name::REGPROCEDURE) IS DISTINCT FROM 'li_memory_function_owner' THEN
   RAISE EXCEPTION 'Function % has unexpected owner',function_name;
  END IF;
 END LOOP;
 IF pg_catalog.has_function_privilege('li_memory_api','li_api.expire_action_intents(integer)','EXECUTE')
   OR pg_catalog.has_function_privilege('li_memory_api','li_api.expire_chat_replay_responses(integer)','EXECUTE')
   OR pg_catalog.has_function_privilege('li_artifact_retention','li_api.finish_chat_turn(uuid,text,text,jsonb)','EXECUTE') THEN
   RAISE EXCEPTION 'Recoverable-turn function privileges are broader than intended';
 END IF;
END $$;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.38','Recoverable chat turns and explicit uncertain action outcomes');
COMMIT;
