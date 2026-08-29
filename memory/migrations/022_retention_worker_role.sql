BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.21') THEN
    RAISE EXCEPTION USING ERRCODE = '55000',
      MESSAGE = 'Migration 022 requires migration 021 (schema 0.21)';
  END IF;
END;
$$;

-- A NOLOGIN capability owns exactly the two retention operations. The LOGIN role
-- inherits only this capability and has no direct table, sequence, or function grants.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'li_artifact_retention') THEN
    CREATE ROLE li_artifact_retention
      NOLOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'li_retention_runtime') THEN
    CREATE ROLE li_retention_runtime
      LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
      CONNECTION LIMIT 2 PASSWORD NULL;
  END IF;
END;
$$;

REVOKE ALL ON SCHEMA li_memory, li_runtime_data FROM li_artifact_retention, li_retention_runtime;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA li_memory, li_runtime_data
  FROM li_artifact_retention, li_retention_runtime;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA li_memory, li_runtime_data
  FROM li_artifact_retention, li_retention_runtime;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA li_memory, li_runtime_data
  FROM li_artifact_retention, li_retention_runtime;
REVOKE ALL ON SCHEMA li_api FROM li_artifact_retention, li_retention_runtime;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA li_api
  FROM li_artifact_retention, li_retention_runtime;

REVOKE EXECUTE ON FUNCTION
  li_api.list_expired_artifacts(INTEGER),
  li_api.mark_artifact_expired(UUID)
FROM PUBLIC, anon, authenticated, service_role, li_memory_api,
  li_backend_runtime, li_memory_theo, li_memory_owner_confirmation,
  li_retention_runtime;

GRANT USAGE ON SCHEMA li_api TO li_artifact_retention;
GRANT EXECUTE ON FUNCTION
  li_api.list_expired_artifacts(INTEGER),
  li_api.mark_artifact_expired(UUID)
TO li_artifact_retention;

REVOKE li_memory_api, li_memory_theo, li_memory_owner_confirmation,
  li_memory_function_owner, li_artifact_retention
FROM li_retention_runtime;
GRANT li_artifact_retention TO li_retention_runtime;

ALTER ROLE li_retention_runtime SET statement_timeout = '30s';
ALTER ROLE li_retention_runtime SET lock_timeout = '5s';
ALTER ROLE li_retention_runtime SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE li_retention_runtime SET search_path = li_api, pg_catalog;

-- Fail the migration if its final permission boundary is not exact.
DO $$
BEGIN
  IF NOT pg_has_role('li_retention_runtime', 'li_artifact_retention', 'MEMBER') THEN
    RAISE EXCEPTION 'Retention runtime is missing its capability role';
  END IF;
  IF NOT has_function_privilege(
    'li_retention_runtime', 'li_api.list_expired_artifacts(integer)', 'EXECUTE'
  ) OR NOT has_function_privilege(
    'li_retention_runtime', 'li_api.mark_artifact_expired(uuid)', 'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Retention runtime is missing an approved function';
  END IF;
  IF has_function_privilege(
    'li_memory_api', 'li_api.list_expired_artifacts(integer)', 'EXECUTE'
  ) OR has_function_privilege(
    'li_memory_api', 'li_api.mark_artifact_expired(uuid)', 'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Broad memory API still has retention execution';
  END IF;
  IF has_function_privilege(
    'li_retention_runtime', 'li_api.list_artifacts(integer)', 'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Retention runtime can execute an ordinary application function';
  END IF;
  IF has_table_privilege(
    'li_retention_runtime', 'li_runtime_data.artifacts',
    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'
  ) THEN
    RAISE EXCEPTION 'Retention runtime has direct artifact-table privileges';
  END IF;
END;
$$;

INSERT INTO li_memory.schema_versions(version, description)
VALUES ('0.22', 'Dedicated least-privilege artifact retention worker')
ON CONFLICT (version) DO NOTHING;

COMMIT;
