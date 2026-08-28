BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version='0.19') THEN
    RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Migration 020 requires migration 019';
  END IF;
END;
$$;

ALTER TABLE li_runtime_data.agent_recommendations
  DROP CONSTRAINT agent_recommendations_status_check,
  ADD CONSTRAINT agent_recommendations_status_check
    CHECK(status IN ('pending_approval','approved_pending_execution','rejected','executed','execution_failed'));

INSERT INTO li_runtime_data.agent_registry_state(owner_user_id,agent_key,state)
SELECT u.id,a.agent_key,'idle'
FROM li_memory.users u
CROSS JOIN unnest(ARRAY['sofia','marco','elena','amelia','freja','oliver','james','nora','victor','milo','iris','clara']) a(agent_key)
WHERE u.user_key='christoffer' AND u.status='active'
ON CONFLICT(owner_user_id,agent_key) DO NOTHING;

CREATE TABLE li_runtime_data.agent_recommendation_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
  recommendation_id UUID NOT NULL REFERENCES li_runtime_data.agent_recommendations(id),
  idempotency_key UUID NOT NULL,
  actor TEXT NOT NULL CHECK(actor='owner:christoffer'),
  confirmed_at TIMESTAMPTZ NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  action TEXT NOT NULL,
  subject_agent TEXT NOT NULL,
  before_registry JSONB NOT NULL,
  after_registry JSONB NOT NULL,
  registry_diff JSONB NOT NULL,
  outcome TEXT NOT NULL CHECK(outcome IN ('executed','executed_as_archive','no_op','failed')),
  error TEXT,
  owner_note TEXT,
  UNIQUE(recommendation_id,idempotency_key)
);
CREATE UNIQUE INDEX one_successful_agent_execution
  ON li_runtime_data.agent_recommendation_executions(recommendation_id)
  WHERE outcome IN ('executed','executed_as_archive','no_op');

ALTER TABLE li_runtime_data.agent_recommendation_executions ENABLE ROW LEVEL SECURITY;
CREATE POLICY agent_execution_function_access
  ON li_runtime_data.agent_recommendation_executions FOR ALL TO li_memory_function_owner
  USING(TRUE) WITH CHECK(TRUE);
GRANT SELECT,INSERT ON li_runtime_data.agent_recommendation_executions TO li_memory_function_owner;

CREATE FUNCTION li_runtime_data.reject_agent_execution_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Agent execution audit is immutable'; END; $$;
CREATE TRIGGER immutable_agent_execution_audit
  BEFORE UPDATE OR DELETE ON li_runtime_data.agent_recommendation_executions
  FOR EACH ROW EXECUTE FUNCTION li_runtime_data.reject_agent_execution_mutation();

GRANT li_memory_function_owner TO postgres;
GRANT USAGE,CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.execute_agent_recommendation(
  p_id UUID,p_idempotency_key UUID,p_confirmation TEXT,p_owner_note TEXT DEFAULT NULL
)
RETURNS TABLE(execution_id UUID,recommendation_id UUID,status TEXT,outcome TEXT,error TEXT,registry_diff JSONB)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE
  v_user UUID; v_rec li_runtime_data.agent_recommendations%ROWTYPE;
  v_existing li_runtime_data.agent_recommendation_executions%ROWTYPE;
  v_before JSONB; v_after JSONB; v_diff JSONB := '{}'::jsonb;
  v_outcome TEXT := 'executed'; v_error TEXT; v_execution UUID; v_target TEXT;
BEGIN
  IF p_confirmation <> 'confirm_permanent_agent_change' THEN
    RAISE EXCEPTION 'Explicit owner confirmation is required';
  END IF;
  SELECT u.id INTO v_user FROM li_memory.users u
    WHERE u.user_key='christoffer' AND u.status='active' LIMIT 1;
  SELECT * INTO v_existing FROM li_runtime_data.agent_recommendation_executions e
    WHERE e.recommendation_id=p_id AND e.idempotency_key=p_idempotency_key;
  IF FOUND THEN
    RETURN QUERY SELECT v_existing.id,p_id,
      CASE WHEN v_existing.outcome='failed' THEN 'execution_failed' ELSE 'executed' END,
      v_existing.outcome,v_existing.error,v_existing.registry_diff;
    RETURN;
  END IF;
  SELECT * INTO v_rec FROM li_runtime_data.agent_recommendations r
    WHERE r.id=p_id AND r.owner_user_id=v_user FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Recommendation not found'; END IF;
  IF v_rec.status='executed' THEN
    SELECT * INTO v_existing FROM li_runtime_data.agent_recommendation_executions e
      WHERE e.recommendation_id=p_id AND e.outcome IN ('executed','executed_as_archive','no_op');
    RETURN QUERY SELECT v_existing.id,p_id,'executed',v_existing.outcome,v_existing.error,v_existing.registry_diff;
    RETURN;
  END IF;
  IF v_rec.status NOT IN ('approved_pending_execution','execution_failed') THEN
    RAISE EXCEPTION 'Recommendation is not approved for execution';
  END IF;
  SELECT COALESCE(jsonb_object_agg(s.agent_key,s.state),'{}'::jsonb) INTO v_before
    FROM li_runtime_data.agent_registry_state s WHERE s.owner_user_id=v_user;
  BEGIN
    IF v_rec.action IN ('pause','archive','remove','merge') AND NOT EXISTS(
      SELECT 1 FROM li_runtime_data.agent_registry_state s
      WHERE s.owner_user_id=v_user AND s.agent_key=v_rec.subject_agent
    ) THEN RAISE EXCEPTION 'Subject agent is not in registry'; END IF;
    CASE v_rec.action
      WHEN 'keep' THEN v_outcome := 'no_op';
      WHEN 'pause' THEN
        INSERT INTO li_runtime_data.agent_registry_state(owner_user_id,agent_key,state)
          VALUES(v_user,v_rec.subject_agent,'paused')
          ON CONFLICT(owner_user_id,agent_key) DO UPDATE SET state='paused',updated_at=NOW();
      WHEN 'archive' THEN
        INSERT INTO li_runtime_data.agent_registry_state(owner_user_id,agent_key,state)
          VALUES(v_user,v_rec.subject_agent,'archived')
          ON CONFLICT(owner_user_id,agent_key) DO UPDATE SET state='archived',updated_at=NOW();
      WHEN 'remove' THEN
        INSERT INTO li_runtime_data.agent_registry_state(owner_user_id,agent_key,state)
          VALUES(v_user,v_rec.subject_agent,'archived')
          ON CONFLICT(owner_user_id,agent_key) DO UPDATE SET state='archived',updated_at=NOW();
        v_outcome := 'executed_as_archive';
      WHEN 'create' THEN
        IF v_rec.subject_agent !~ '^new:[a-z0-9][a-z0-9_-]{1,63}$' THEN RAISE EXCEPTION 'Unsafe proposed agent key'; END IF;
        IF EXISTS(SELECT 1 FROM li_runtime_data.agent_registry_state s
          WHERE s.owner_user_id=v_user AND s.agent_key=substring(v_rec.subject_agent FROM 5))
          THEN RAISE EXCEPTION 'Agent key already exists'; END IF;
        INSERT INTO li_runtime_data.agent_registry_state(owner_user_id,agent_key,state)
          VALUES(v_user,substring(v_rec.subject_agent FROM 5),'paused')
          ON CONFLICT(owner_user_id,agent_key) DO NOTHING;
      WHEN 'merge' THEN
        v_target := v_rec.evidence->>'merge_target';
        IF v_target IS NULL OR v_target=v_rec.subject_agent THEN RAISE EXCEPTION 'Safe merge target is required'; END IF;
        IF NOT EXISTS(SELECT 1 FROM li_runtime_data.agent_registry_state s WHERE s.owner_user_id=v_user AND s.agent_key=v_target AND s.state<>'archived')
          THEN RAISE EXCEPTION 'Merge target is not active in registry'; END IF;
        INSERT INTO li_runtime_data.agent_registry_state(owner_user_id,agent_key,state)
          VALUES(v_user,v_rec.subject_agent,'archived')
          ON CONFLICT(owner_user_id,agent_key) DO UPDATE SET state='archived',updated_at=NOW();
      ELSE RAISE EXCEPTION 'Unsupported agent action';
    END CASE;
  EXCEPTION WHEN OTHERS THEN
    v_error := SQLERRM; v_outcome := 'failed';
  END;
  SELECT COALESCE(jsonb_object_agg(s.agent_key,s.state),'{}'::jsonb) INTO v_after
    FROM li_runtime_data.agent_registry_state s WHERE s.owner_user_id=v_user;
  IF v_outcome='failed' THEN v_after:=v_before;
  ELSE v_diff:=jsonb_build_object('subject_agent',v_rec.subject_agent,'action',v_rec.action,
    'merge_target',v_target,'before',v_before->v_rec.subject_agent,
    'after',v_after->replace(v_rec.subject_agent,'new:',''));
  END IF;
  INSERT INTO li_runtime_data.agent_recommendation_executions(owner_user_id,recommendation_id,idempotency_key,
    actor,confirmed_at,action,subject_agent,before_registry,after_registry,registry_diff,outcome,error,owner_note)
  VALUES(v_user,p_id,p_idempotency_key,'owner:christoffer',NOW(),v_rec.action,v_rec.subject_agent,
    v_before,v_after,v_diff,v_outcome,v_error,p_owner_note) RETURNING id INTO v_execution;
  UPDATE li_runtime_data.agent_recommendations r SET status=CASE WHEN v_outcome='failed' THEN 'execution_failed' ELSE 'executed' END
    WHERE r.id=p_id;
  RETURN QUERY SELECT v_execution,p_id,CASE WHEN v_outcome='failed' THEN 'execution_failed' ELSE 'executed' END,
    v_outcome,v_error,v_diff;
END;
$$;

RESET ROLE;
REVOKE ALL ON FUNCTION li_api.execute_agent_recommendation(UUID,UUID,TEXT,TEXT)
  FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,li_memory_theo;
GRANT EXECUTE ON FUNCTION li_api.execute_agent_recommendation(UUID,UUID,TEXT,TEXT)
  TO li_memory_owner_confirmation;
REVOKE ALL PRIVILEGES ON li_runtime_data.agent_recommendation_executions
  FROM li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation;
REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.20','Controlled owner-confirmed agent governance executor') ON CONFLICT(version) DO NOTHING;
COMMIT;
