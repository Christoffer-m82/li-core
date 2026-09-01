BEGIN;

DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.35') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 036 requires applied schema 0.35';
 END IF;
 IF EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.36') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Schema version 0.36 is already claimed';
 END IF;
 IF (SELECT count(*) FROM li_memory.users WHERE user_key='christoffer' AND status='active')<>1 THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 036 requires exactly one active owner';
 END IF;
END $$;

ALTER TABLE li_runtime_data.model_registry
 ADD COLUMN configuration_state TEXT NOT NULL DEFAULT 'not_configured'
  CHECK(configuration_state IN('configured','not_configured')),
 ADD COLUMN configuration_version INTEGER NOT NULL DEFAULT 0 CHECK(configuration_version>=0),
 ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE li_runtime_data.model_registry_audit(
 audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
 request_id UUID NOT NULL,
 actor_reference TEXT NOT NULL CHECK(length(actor_reference) BETWEEN 1 AND 160),
 model_key TEXT NOT NULL CHECK(length(model_key) BETWEEN 1 AND 80),
 previous_metadata JSONB NOT NULL CHECK(jsonb_typeof(previous_metadata)='object' AND pg_column_size(previous_metadata)<=32768),
 new_metadata JSONB NOT NULL CHECK(jsonb_typeof(new_metadata)='object' AND pg_column_size(new_metadata)<=32768),
 reason TEXT NOT NULL CHECK(length(reason) BETWEEN 8 AND 500),
 configuration_version INTEGER NOT NULL CHECK(configuration_version>0),
 changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 UNIQUE(owner_user_id,request_id)
);
ALTER TABLE li_runtime_data.model_registry_audit ENABLE ROW LEVEL SECURITY;

CREATE TEMP TABLE migration_036_authority_state(migration_role NAME,added_owner BOOLEAN,added_create BOOLEAN) ON COMMIT DROP;
INSERT INTO migration_036_authority_state SELECT CURRENT_USER,NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_036_authority_state) THEN EXECUTE pg_catalog.format('GRANT li_memory_function_owner TO %I',(SELECT migration_role FROM migration_036_authority_state)); END IF;
 IF (SELECT added_create FROM migration_036_authority_state) THEN EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner'; END IF;
END $$;
DO $$ BEGIN
 IF NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET') THEN RAISE EXCEPTION 'Migration role cannot assume li_memory_function_owner'; END IF;
 IF NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE') THEN RAISE EXCEPTION 'Function owner cannot create in li_api'; END IF;
END $$;

GRANT SELECT,INSERT ON li_runtime_data.model_registry_audit TO li_memory_function_owner;
GRANT SELECT,UPDATE ON li_runtime_data.model_registry TO li_memory_function_owner;
CREATE POLICY model_registry_function_access ON li_runtime_data.model_registry FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY model_registry_audit_function_access ON li_runtime_data.model_registry_audit FOR SELECT TO li_memory_function_owner USING(TRUE);
CREATE POLICY model_registry_audit_insert ON li_runtime_data.model_registry_audit FOR INSERT TO li_memory_function_owner WITH CHECK(TRUE);

SET LOCAL ROLE li_memory_function_owner;
CREATE FUNCTION li_api.reject_model_registry_audit_mutation() RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN RAISE EXCEPTION 'Model registry audit is append-only'; END $$;
CREATE TRIGGER model_registry_audit_append_only
 BEFORE UPDATE OR DELETE ON li_runtime_data.model_registry_audit
 FOR EACH ROW EXECUTE FUNCTION li_api.reject_model_registry_audit_mutation();

CREATE FUNCTION li_api.configure_model_registry(
 p_request_id UUID,p_actor_reference TEXT,p_model_key TEXT,p_provider TEXT,p_model_name TEXT,
 p_configuration_state TEXT,p_health TEXT,p_capabilities JSONB,p_context_limit INTEGER,
 p_cost_metadata JSONB,p_reason TEXT,p_expected_version INTEGER DEFAULT NULL
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_owner UUID;v_current li_runtime_data.model_registry%ROWTYPE;v_previous JSONB;v_new JSONB;v_existing JSONB;
BEGIN
 IF p_request_id IS NULL OR length(btrim(COALESCE(p_actor_reference,''))) NOT BETWEEN 1 AND 160
  OR length(btrim(COALESCE(p_reason,''))) NOT BETWEEN 8 AND 500 THEN RAISE EXCEPTION 'Owner correlation and audit reason are required'; END IF;
 IF (p_model_key,p_provider,p_model_name) IS DISTINCT FROM ('claude-primary','anthropic','claude-sonnet-5') THEN
  RAISE EXCEPTION 'Model is not present in the approved code/config registry';
 END IF;
 IF p_configuration_state<>'configured' OR p_health NOT IN('healthy','degraded','unavailable') THEN RAISE EXCEPTION 'Invalid configured model state'; END IF;
 IF p_context_limit<>200000 OR p_capabilities IS DISTINCT FROM '["reasoning","structured_output","coding"]'::jsonb THEN RAISE EXCEPTION 'Model capabilities or context do not match the approved registry'; END IF;
 IF jsonb_typeof(p_cost_metadata)<>'object' OR pg_column_size(p_cost_metadata)>8192
  OR p_cost_metadata ?| ARRAY['api_key','token','secret','credential','password','authorization']
  OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_cost_metadata) k WHERE lower(k) ~ '(secret|credential|password|api.?key|token|authorization)')
  OR EXISTS(SELECT 1 FROM jsonb_object_keys(p_cost_metadata) k WHERE k NOT IN('input_per_million_usd','output_per_million_usd','currency','measured_at','source'))
  OR (p_cost_metadata ? 'input_per_million_usd' AND jsonb_typeof(p_cost_metadata->'input_per_million_usd')<>'number')
  OR (p_cost_metadata ? 'output_per_million_usd' AND jsonb_typeof(p_cost_metadata->'output_per_million_usd')<>'number')
  OR (p_cost_metadata ? 'currency' AND p_cost_metadata->>'currency'<>'USD')
  OR (p_cost_metadata ? 'source' AND p_cost_metadata->>'source'<>'approved_runtime_configuration')
  OR (p_cost_metadata ? 'measured_at' AND (jsonb_typeof(p_cost_metadata->'measured_at')<>'string' OR length(p_cost_metadata->>'measured_at')>40))
 THEN RAISE EXCEPTION 'Cost metadata contains an unsupported or secret-like field'; END IF;
 SELECT id INTO STRICT v_owner FROM li_memory.users WHERE user_key='christoffer' AND status='active';
 SELECT new_metadata INTO v_existing FROM li_runtime_data.model_registry_audit WHERE owner_user_id=v_owner AND request_id=p_request_id;
 IF FOUND THEN RETURN v_existing||jsonb_build_object('idempotent',TRUE); END IF;
 SELECT * INTO STRICT v_current FROM li_runtime_data.model_registry WHERE owner_user_id=v_owner AND model_key=p_model_key FOR UPDATE;
 IF p_expected_version IS NOT NULL AND p_expected_version<>v_current.configuration_version THEN RAISE EXCEPTION 'Model registry version conflict'; END IF;
 v_previous:=jsonb_build_object('model_key',v_current.model_key,'provider',v_current.provider,'model_name',v_current.model_name,'configuration_state',v_current.configuration_state,'health',v_current.health,'capabilities',v_current.capabilities,'context_limit',v_current.context_limit,'cost_metadata',v_current.cost_metadata,'is_primary',v_current.is_primary,'configuration_version',v_current.configuration_version,'updated_at',v_current.updated_at);
 UPDATE li_runtime_data.model_registry SET provider=p_provider,model_name=p_model_name,configuration_state=p_configuration_state,health=p_health,
  capabilities=p_capabilities,context_limit=p_context_limit,cost_metadata=p_cost_metadata,is_primary=TRUE,
  configuration_version=configuration_version+1,updated_at=NOW()
 WHERE owner_user_id=v_owner AND model_key=p_model_key RETURNING * INTO v_current;
 v_new:=jsonb_build_object('model_key',v_current.model_key,'provider',v_current.provider,'model_name',v_current.model_name,'configuration_state',v_current.configuration_state,'health',v_current.health,'capabilities',v_current.capabilities,'context_limit',v_current.context_limit,'cost_metadata',v_current.cost_metadata,'is_primary',v_current.is_primary,'configuration_version',v_current.configuration_version,'updated_at',v_current.updated_at);
 INSERT INTO li_runtime_data.model_registry_audit(owner_user_id,request_id,actor_reference,model_key,previous_metadata,new_metadata,reason,configuration_version)
 VALUES(v_owner,p_request_id,btrim(p_actor_reference),p_model_key,v_previous,v_new,btrim(p_reason),v_current.configuration_version);
 RETURN v_new||jsonb_build_object('idempotent',FALSE);
END $$;

CREATE FUNCTION li_api.list_model_registry_overview() RETURNS TABLE(
 model_key TEXT,provider TEXT,model_name TEXT,configuration_state TEXT,health TEXT,
 capabilities JSONB,context_limit INTEGER,cost_metadata JSONB,is_primary BOOLEAN,
 configuration_version INTEGER,updated_at TIMESTAMPTZ
) LANGUAGE sql SECURITY DEFINER SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
 SELECT r.model_key,r.provider,r.model_name,r.configuration_state,r.health,r.capabilities,
  r.context_limit,r.cost_metadata,r.is_primary,r.configuration_version,r.updated_at
 FROM li_runtime_data.model_registry r JOIN li_memory.users u ON u.id=r.owner_user_id
 WHERE u.user_key='christoffer' AND u.status='active' ORDER BY r.is_primary DESC,r.model_key
$$;
RESET ROLE;

REVOKE ALL ON FUNCTION li_api.configure_model_registry(UUID,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB,INTEGER,JSONB,TEXT,INTEGER)
 FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,li_memory_theo,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.configure_model_registry(UUID,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT,JSONB,INTEGER,JSONB,TEXT,INTEGER) TO li_memory_owner_confirmation;
REVOKE ALL ON FUNCTION li_api.reject_model_registry_audit_mutation() FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
REVOKE ALL ON FUNCTION li_api.list_model_registry_overview() FROM PUBLIC,anon,authenticated,service_role,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.list_model_registry_overview() TO li_memory_api;
REVOKE ALL PRIVILEGES ON li_runtime_data.model_registry,li_runtime_data.model_registry_audit
 FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;

DO $$ BEGIN
 IF (SELECT added_create FROM migration_036_authority_state) THEN REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner; END IF;
 IF (SELECT added_owner FROM migration_036_authority_state) THEN EXECUTE pg_catalog.format('REVOKE li_memory_function_owner FROM %I',(SELECT migration_role FROM migration_036_authority_state)); END IF;
 IF pg_catalog.has_function_privilege('li_backend_runtime','li_api.configure_model_registry(uuid,text,text,text,text,text,text,jsonb,integer,jsonb,text,integer)','EXECUTE')
  OR pg_catalog.has_function_privilege('li_memory_theo','li_api.configure_model_registry(uuid,text,text,text,text,text,text,jsonb,integer,jsonb,text,integer)','EXECUTE')
  OR pg_catalog.has_function_privilege('li_retention_runtime','li_api.configure_model_registry(uuid,text,text,text,text,text,text,jsonb,integer,jsonb,text,integer)','EXECUTE')
  OR NOT pg_catalog.has_function_privilege('li_memory_owner_confirmation','li_api.configure_model_registry(uuid,text,text,text,text,text,text,jsonb,integer,jsonb,text,integer)','EXECUTE') THEN RAISE EXCEPTION 'Model registry owner boundary is incorrect'; END IF;
 IF pg_catalog.has_table_privilege('li_memory_owner_confirmation','li_runtime_data.model_registry','UPDATE')
  OR pg_catalog.has_table_privilege('li_backend_runtime','li_runtime_data.model_registry','SELECT')
  OR pg_catalog.has_table_privilege('li_memory_api','li_runtime_data.model_registry_audit','SELECT') THEN RAISE EXCEPTION 'Model registry direct table boundary is broader than intended'; END IF;
 IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_trigger WHERE tgname='model_registry_audit_append_only' AND NOT tgisinternal) THEN RAISE EXCEPTION 'Model registry audit append-only trigger is missing'; END IF;
END $$;

INSERT INTO li_memory.schema_versions(version,description) VALUES('0.36','Owner-only audited model-registry configuration and safe read-only status');
COMMIT;
