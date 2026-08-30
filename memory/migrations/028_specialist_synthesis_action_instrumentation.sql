BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version='0.27') THEN
    RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Migration 028 requires applied schema 0.27';
  END IF;
END;
$$;

CREATE TABLE li_runtime_data.specialist_action_attributions (
  action_id UUID NOT NULL,
  interaction_id UUID NOT NULL REFERENCES li_runtime_data.specialist_interactions(id) ON DELETE CASCADE,
  owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
  request_id UUID NOT NULL,
  action_type TEXT NOT NULL CHECK (length(action_type) BETWEEN 1 AND 100),
  status TEXT NOT NULL CHECK (status IN ('succeeded','blocked','failed')),
  measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY(action_id, interaction_id)
);
ALTER TABLE li_runtime_data.specialist_action_attributions ENABLE ROW LEVEL SECURITY;
CREATE POLICY specialist_action_function_access
  ON li_runtime_data.specialist_action_attributions FOR ALL TO li_memory_function_owner
  USING(TRUE) WITH CHECK(TRUE);
GRANT SELECT,INSERT,UPDATE,DELETE ON li_runtime_data.specialist_action_attributions
  TO li_memory_function_owner;
CREATE INDEX specialist_action_request_idx
  ON li_runtime_data.specialist_action_attributions(owner_user_id,request_id,measured_at DESC);

CREATE TEMP TABLE migration_028_authority_state (
  added_owner_membership BOOLEAN NOT NULL,
  added_schema_create BOOLEAN NOT NULL
) ON COMMIT DROP;
INSERT INTO migration_028_authority_state SELECT
  NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),
  NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
  IF (SELECT added_owner_membership FROM migration_028_authority_state) THEN
    EXECUTE 'GRANT li_memory_function_owner TO postgres';
  END IF;
  IF (SELECT added_schema_create FROM migration_028_authority_state) THEN
    EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner';
  END IF;
END $$;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.record_specialist_synthesis_attribution(
  p_request UUID,p_used UUID[],p_measured UUID[])
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_expected INTEGER; v_matched INTEGER;
BEGIN
  SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
  IF p_request IS NULL OR p_measured IS NULL OR cardinality(p_measured)=0
     OR p_used IS NULL OR NOT p_used <@ p_measured THEN
    RAISE EXCEPTION 'Invalid synthesis attribution set';
  END IF;
  SELECT count(DISTINCT x) INTO v_expected FROM unnest(p_measured) x;
  SELECT count(*) INTO v_matched FROM li_runtime_data.specialist_interactions i
   WHERE i.owner_user_id=v_user AND i.request_id=p_request AND i.status='completed'
     AND i.id=ANY(p_measured);
  IF v_matched<>v_expected THEN RAISE EXCEPTION 'Attribution does not match completed request interactions'; END IF;
  UPDATE li_runtime_data.specialist_interactions i
     SET used_in_final=(i.id=ANY(p_used)),updated_at=NOW()
   WHERE i.owner_user_id=v_user AND i.request_id=p_request AND i.id=ANY(p_measured);
  RETURN TRUE;
END; $$;

CREATE FUNCTION li_api.record_specialist_action_attribution(
  p_action UUID,p_request UUID,p_interactions UUID[],p_action_type TEXT,p_status TEXT)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_expected INTEGER; v_matched INTEGER;
BEGIN
  SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
  IF p_action IS NULL OR p_request IS NULL OR p_interactions IS NULL
     OR cardinality(p_interactions)=0 OR p_status NOT IN ('succeeded','blocked','failed')
     OR length(p_action_type) NOT BETWEEN 1 AND 100 THEN
    RAISE EXCEPTION 'Invalid action attribution';
  END IF;
  SELECT count(DISTINCT x) INTO v_expected FROM unnest(p_interactions) x;
  SELECT count(*) INTO v_matched FROM li_runtime_data.specialist_interactions i
   WHERE i.owner_user_id=v_user AND i.request_id=p_request AND i.used_in_final IS TRUE
     AND i.id=ANY(p_interactions);
  IF v_matched<>v_expected THEN RAISE EXCEPTION 'Action is not linked to measured used contributions'; END IF;
  INSERT INTO li_runtime_data.specialist_action_attributions(
    action_id,interaction_id,owner_user_id,request_id,action_type,status)
  SELECT p_action,i.id,v_user,p_request,p_action_type,p_status
    FROM li_runtime_data.specialist_interactions i WHERE i.id=ANY(p_interactions)
  ON CONFLICT(action_id,interaction_id) DO UPDATE SET
    status=CASE WHEN specialist_action_attributions.status='succeeded' OR EXCLUDED.status='succeeded'
                THEN 'succeeded' ELSE EXCLUDED.status END,
    measured_at=NOW()
  WHERE specialist_action_attributions.owner_user_id=EXCLUDED.owner_user_id
    AND specialist_action_attributions.request_id=EXCLUDED.request_id
    AND specialist_action_attributions.action_type=EXCLUDED.action_type;
  UPDATE li_runtime_data.specialist_interactions i SET
    action_taken=CASE WHEN p_status='succeeded' THEN TRUE ELSE COALESCE(i.action_taken,FALSE) END,
    updated_at=NOW()
   WHERE i.owner_user_id=v_user AND i.request_id=p_request AND i.id=ANY(p_interactions);
  RETURN TRUE;
END; $$;

RESET ROLE;
REVOKE ALL ON FUNCTION li_api.record_specialist_synthesis_attribution(UUID,UUID[],UUID[]),
 li_api.record_specialist_action_attribution(UUID,UUID,UUID[],TEXT,TEXT)
 FROM PUBLIC,anon,authenticated,service_role,li_memory_theo,li_memory_owner_confirmation,
 li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.record_specialist_synthesis_attribution(UUID,UUID[],UUID[]),
 li_api.record_specialist_action_attribution(UUID,UUID,UUID[],TEXT,TEXT) TO li_memory_api;
REVOKE ALL PRIVILEGES ON li_runtime_data.specialist_action_attributions
 FROM li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation,li_retention_runtime;
DO $$ BEGIN
  IF (SELECT added_schema_create FROM migration_028_authority_state) THEN
    EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner';
  END IF;
  IF (SELECT added_owner_membership FROM migration_028_authority_state) THEN
    EXECUTE 'REVOKE li_memory_function_owner FROM postgres';
  END IF;
END $$;

DO $$ BEGIN
  IF (SELECT added_schema_create FROM migration_028_authority_state)
     AND pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE') THEN
    RAISE EXCEPTION 'Temporary li_api CREATE authority was not removed';
  END IF;
  IF pg_catalog.has_function_privilege('li_retention_runtime',
     'li_api.record_specialist_action_attribution(uuid,uuid,uuid[],text,text)','EXECUTE') THEN
    RAISE EXCEPTION 'Retention runtime gained action attribution execution';
  END IF;
END $$;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.28','Measured specialist synthesis and Li-owned action attribution')
ON CONFLICT(version) DO NOTHING;
COMMIT;
