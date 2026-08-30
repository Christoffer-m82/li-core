BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version='0.28') THEN
    RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Migration 029 requires applied schema 0.28';
  END IF;
END $$;

CREATE TABLE li_runtime_data.action_intents (
  id UUID PRIMARY KEY,
  owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
  conversation_id UUID REFERENCES li_runtime_data.conversations(id) ON DELETE CASCADE,
  request_id UUID NOT NULL,
  action_type TEXT NOT NULL CHECK(length(action_type) BETWEEN 1 AND 100),
  payload JSONB NOT NULL CHECK(jsonb_typeof(payload)='object'),
  payload_hash TEXT NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
  payload_summary TEXT NOT NULL CHECK(length(payload_summary) BETWEEN 1 AND 1000),
  specialist_interaction_ids UUID[] NOT NULL DEFAULT '{}',
  approval_required BOOLEAN NOT NULL DEFAULT TRUE CHECK(approval_required),
  owner_confirmation_required BOOLEAN NOT NULL DEFAULT FALSE,
  state TEXT NOT NULL DEFAULT 'proposed' CHECK(state IN
    ('proposed','owner_confirmation_required','executing','succeeded','failed','denied','expired')),
  idempotency_key TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW()+INTERVAL '24 hours',
  resolved_at TIMESTAMPTZ,
  result JSONB,
  CHECK(expires_at>created_at),
  CHECK((state IN ('succeeded','failed','denied','expired'))=(resolved_at IS NOT NULL))
);
CREATE INDEX action_intents_pending_expiry_idx ON li_runtime_data.action_intents(expires_at)
  WHERE state IN ('proposed','owner_confirmation_required');
ALTER TABLE li_runtime_data.action_intents ENABLE ROW LEVEL SECURITY;
CREATE POLICY action_intent_function_access ON li_runtime_data.action_intents FOR ALL
  TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);

CREATE TABLE li_runtime_data.action_intent_events (
  event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  intent_id UUID NOT NULL REFERENCES li_runtime_data.action_intents(id) ON DELETE CASCADE,
  owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
  actor TEXT NOT NULL CHECK(actor IN ('li','owner','system','provider')),
  from_state TEXT,
  to_state TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK(length(outcome) BETWEEN 1 AND 100),
  error_metadata JSONB NOT NULL DEFAULT '{}',
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE li_runtime_data.action_intent_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY action_intent_event_function_access ON li_runtime_data.action_intent_events FOR ALL
  TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
GRANT SELECT,INSERT,UPDATE ON li_runtime_data.action_intents TO li_memory_function_owner;
GRANT SELECT,INSERT ON li_runtime_data.action_intent_events TO li_memory_function_owner;
GRANT USAGE,SELECT ON SEQUENCE li_runtime_data.action_intent_events_event_id_seq TO li_memory_function_owner;

CREATE TEMP TABLE migration_029_authority_state(added_owner BOOLEAN,added_create BOOLEAN) ON COMMIT DROP;
INSERT INTO migration_029_authority_state SELECT
 NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),
 NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_029_authority_state) THEN EXECUTE 'GRANT li_memory_function_owner TO postgres'; END IF;
 IF (SELECT added_create FROM migration_029_authority_state) THEN EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner'; END IF;
END $$;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.create_action_intent(
 p_id UUID,p_request UUID,p_interactions UUID[],p_conversation UUID,p_action_type TEXT,
 p_summary TEXT,p_payload JSONB,p_payload_hash TEXT,p_owner_confirmation BOOLEAN)
RETURNS TABLE(intent_id UUID,request_id UUID,action_type TEXT,summary TEXT,approval_state TEXT,
 approval_required BOOLEAN,owner_confirmation_required BOOLEAN,created_at TIMESTAMPTZ,
 expires_at TIMESTAMPTZ,resolved_at TIMESTAMPTZ,result JSONB)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_count INTEGER; v_state TEXT;
BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 IF p_id IS NULL OR p_request IS NULL OR p_payload IS NULL OR jsonb_typeof(p_payload)<>'object'
   OR p_payload_hash !~ '^[0-9a-f]{64}$' OR length(p_summary) NOT BETWEEN 1 AND 1000
   OR length(p_action_type) NOT BETWEEN 1 AND 100 THEN RAISE EXCEPTION 'Invalid action intent'; END IF;
 SELECT count(*) INTO v_count FROM li_runtime_data.specialist_interactions i
  WHERE i.owner_user_id=v_user AND i.request_id=p_request AND i.used_in_final IS TRUE
    AND i.id=ANY(COALESCE(p_interactions,'{}'));
 IF v_count<>cardinality(COALESCE(p_interactions,'{}')) THEN
   RAISE EXCEPTION 'Intent correlation is not a measured used contribution';
 END IF;
 v_state:=CASE WHEN p_owner_confirmation THEN 'owner_confirmation_required' ELSE 'proposed' END;
 INSERT INTO li_runtime_data.action_intents(id,owner_user_id,conversation_id,request_id,action_type,
   payload,payload_hash,payload_summary,specialist_interaction_ids,owner_confirmation_required,state,idempotency_key)
 VALUES(p_id,v_user,p_conversation,p_request,p_action_type,p_payload,p_payload_hash,p_summary,
   COALESCE(p_interactions,'{}'),p_owner_confirmation,v_state,'intent:'||p_id::text);
 INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,to_state,outcome)
 VALUES(p_id,v_user,'li',v_state,'proposed');
 RETURN QUERY SELECT a.id,a.request_id,a.action_type,a.payload_summary,a.state,a.approval_required,
   a.owner_confirmation_required,a.created_at,a.expires_at,a.resolved_at,a.result
  FROM li_runtime_data.action_intents a WHERE a.id=p_id;
END $$;

CREATE FUNCTION li_api.resolve_action_intent(
 p_id UUID,p_decision TEXT,p_owner_confirmation TEXT DEFAULT NULL,
 p_execution_status TEXT DEFAULT NULL,p_result JSONB DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE a li_runtime_data.action_intents%ROWTYPE; v_user UUID; v_now TIMESTAMPTZ:=NOW();
 v_public JSONB; v_outcome TEXT;
BEGIN
 SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
 SELECT * INTO a FROM li_runtime_data.action_intents WHERE id=p_id AND owner_user_id=v_user FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Action intent not found'; END IF;
 IF a.state IN ('succeeded','failed','denied','expired') THEN v_outcome:='resolved';
 ELSIF a.expires_at<=v_now THEN
   UPDATE li_runtime_data.action_intents SET state='expired',resolved_at=v_now WHERE id=p_id;
   INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome)
    VALUES(p_id,v_user,'system',a.state,'expired','expired_without_attempt'); v_outcome:='resolved';
 ELSIF p_decision='deny' AND a.state IN ('proposed','owner_confirmation_required') THEN
   UPDATE li_runtime_data.action_intents SET state='denied',resolved_at=v_now WHERE id=p_id;
   INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome)
    VALUES(p_id,v_user,'owner',a.state,'denied','denied_without_attempt'); v_outcome:='resolved';
 ELSIF p_decision='approve' AND a.state='owner_confirmation_required' THEN
   IF p_owner_confirmation IS DISTINCT FROM 'confirm_permanent_agent_change' THEN
     v_outcome:='owner_confirmation_required';
   ELSE
     v_outcome:='owner_executor_required';
     INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome)
      VALUES(p_id,v_user,'owner',a.state,a.state,'owner_confirmed_existing_executor_required');
   END IF;
 ELSIF p_decision='approve' AND a.state='proposed' THEN
   UPDATE li_runtime_data.action_intents SET state='executing' WHERE id=p_id;
   INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome)
    VALUES(p_id,v_user,'owner','proposed','executing','approved_and_claimed'); v_outcome:='execute';
 ELSIF p_decision='complete' AND a.state='executing' AND p_execution_status IN ('succeeded','failed') THEN
   UPDATE li_runtime_data.action_intents SET state=p_execution_status,resolved_at=v_now,result=COALESCE(p_result,'{}') WHERE id=p_id;
   INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome,error_metadata)
    VALUES(p_id,v_user,'provider','executing',p_execution_status,p_execution_status,
      CASE WHEN p_execution_status='failed' THEN jsonb_build_object('category','provider_failure') ELSE '{}' END);
   IF cardinality(a.specialist_interaction_ids)>0 THEN
     PERFORM li_api.record_specialist_action_attribution(a.id,a.request_id,a.specialist_interaction_ids,
       a.action_type,CASE WHEN p_execution_status='succeeded' THEN 'succeeded' ELSE 'failed' END);
   END IF;
   v_outcome:='resolved';
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

CREATE FUNCTION li_api.expire_action_intents(p_limit INTEGER DEFAULT 100)
RETURNS INTEGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_count INTEGER;
BEGIN
 WITH expired AS (SELECT id,owner_user_id,state FROM li_runtime_data.action_intents
   WHERE state IN ('proposed','owner_confirmation_required') AND expires_at<=NOW()
   ORDER BY expires_at LIMIT LEAST(GREATEST(p_limit,1),500) FOR UPDATE SKIP LOCKED),
 updated AS (UPDATE li_runtime_data.action_intents a SET state='expired',resolved_at=NOW()
   FROM expired e WHERE a.id=e.id RETURNING a.id,a.owner_user_id,e.state)
 INSERT INTO li_runtime_data.action_intent_events(intent_id,owner_user_id,actor,from_state,to_state,outcome)
 SELECT id,owner_user_id,'system',state,'expired','expired_without_attempt' FROM updated;
 GET DIAGNOSTICS v_count=ROW_COUNT; RETURN v_count;
END $$;

RESET ROLE;
REVOKE ALL ON FUNCTION li_api.create_action_intent(UUID,UUID,UUID[],UUID,TEXT,TEXT,JSONB,TEXT,BOOLEAN),
 li_api.resolve_action_intent(UUID,TEXT,TEXT,TEXT,JSONB),li_api.expire_action_intents(INTEGER)
 FROM PUBLIC,anon,authenticated,service_role,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.create_action_intent(UUID,UUID,UUID[],UUID,TEXT,TEXT,JSONB,TEXT,BOOLEAN),
 li_api.resolve_action_intent(UUID,TEXT,TEXT,TEXT,JSONB) TO li_memory_api;
GRANT EXECUTE ON FUNCTION li_api.expire_action_intents(INTEGER) TO li_artifact_retention;
REVOKE ALL PRIVILEGES ON li_runtime_data.action_intents,li_runtime_data.action_intent_events
 FROM li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation,li_retention_runtime;
DO $$ BEGIN
 IF (SELECT added_create FROM migration_029_authority_state) THEN EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner'; END IF;
 IF (SELECT added_owner FROM migration_029_authority_state) THEN EXECUTE 'REVOKE li_memory_function_owner FROM postgres'; END IF;
END $$;
INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.29','Durable Li-owned approval and action intents') ON CONFLICT(version) DO NOTHING;
COMMIT;
