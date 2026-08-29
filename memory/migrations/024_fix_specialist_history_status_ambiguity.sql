BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.23') THEN
    RAISE EXCEPTION 'Migration 024 requires schema version 0.23';
  END IF;
END $$;

DO $$
DECLARE function_owner TEXT;
BEGIN
  SELECT owner_role.rolname INTO function_owner
  FROM pg_catalog.pg_proc AS p
  JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
  JOIN pg_catalog.pg_roles AS owner_role ON owner_role.oid = p.proowner
  WHERE n.nspname = 'li_api'
    AND p.proname = 'list_specialist_interactions'
    AND pg_catalog.pg_get_function_identity_arguments(p.oid) =
      'p_specialist text, p_limit integer';

  IF function_owner IS DISTINCT FROM 'li_memory_function_owner' THEN
    RAISE EXCEPTION 'list_specialist_interactions has unexpected owner %', function_owner;
  END IF;
  IF NOT pg_catalog.has_schema_privilege(
    'li_memory_function_owner', 'li_api', 'USAGE'
  ) THEN
    RAISE EXCEPTION 'li_memory_function_owner lacks expected USAGE on li_api';
  END IF;
END $$;

GRANT li_memory_function_owner TO postgres;

DO $$
BEGIN
  IF NOT pg_catalog.pg_has_role(CURRENT_USER, 'li_memory_function_owner', 'SET') THEN
    RAISE EXCEPTION 'Migration role cannot assume li_memory_function_owner';
  END IF;
END $$;

GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE OR REPLACE FUNCTION li_api.list_specialist_interactions(
  p_specialist TEXT DEFAULT NULL,
  p_limit INTEGER DEFAULT 50
)
RETURNS TABLE(
  interaction_id UUID, conversation_id UUID, request_id UUID,
  specialist_key TEXT, status TEXT, request_text TEXT, outcome JSONB,
  started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp
AS $$
DECLARE v_user UUID;
BEGIN
  SELECT u.id INTO v_user
  FROM li_memory.users AS u
  WHERE u.user_key = 'christoffer' AND u.status = 'active'
  LIMIT 1;

  RETURN QUERY
  SELECT i.id, i.conversation_id, i.request_id, i.specialist_key, i.status,
    i.request_text, i.outcome, i.started_at, i.completed_at, i.updated_at
  FROM li_runtime_data.specialist_interactions AS i
  WHERE i.owner_user_id = v_user
    AND (p_specialist IS NULL OR i.specialist_key = p_specialist)
  ORDER BY (i.status = 'active') DESC, i.updated_at DESC
  LIMIT LEAST(GREATEST(COALESCE(p_limit, 50), 1), 100);
END;
$$;

-- Function ACL changes must run as the function owner. PostgreSQL does not let
-- the migration-session role manage an existing function's privileges merely
-- because it can temporarily SET ROLE to that owner.
REVOKE ALL ON FUNCTION li_api.list_specialist_interactions(TEXT, INTEGER)
FROM PUBLIC, anon, authenticated, service_role, li_memory_theo,
  li_memory_owner_confirmation, li_artifact_retention, li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.list_specialist_interactions(TEXT, INTEGER)
TO li_memory_api;

RESET ROLE;
REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

DO $$
BEGIN
  IF (
    SELECT owner_role.rolname
    FROM pg_catalog.pg_proc AS p
    JOIN pg_catalog.pg_roles AS owner_role ON owner_role.oid = p.proowner
    WHERE p.oid = 'li_api.list_specialist_interactions(text,integer)'::REGPROCEDURE
  ) <> 'li_memory_function_owner' THEN
    RAISE EXCEPTION 'list_specialist_interactions owner changed unexpectedly';
  END IF;
  IF NOT pg_catalog.has_function_privilege(
    'li_backend_runtime',
    'li_api.list_specialist_interactions(text,integer)', 'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Backend runtime lost specialist history execution';
  END IF;
  IF pg_catalog.has_function_privilege(
    'li_retention_runtime',
    'li_api.list_specialist_interactions(text,integer)', 'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Retention runtime gained specialist history execution';
  END IF;
  IF pg_catalog.has_schema_privilege(
    'li_memory_function_owner', 'li_api', 'CREATE'
  ) THEN
    RAISE EXCEPTION 'Temporary li_api CREATE authority was not removed';
  END IF;
  -- PostgreSQL 16+ can retain multiple grantor- and option-specific rows in
  -- pg_auth_members. A row by itself does not prove that postgres can inherit
  -- this role's privileges or SET ROLE to it. Verify the effective authority
  -- that the temporary grant provided instead; the REVOKE above remains the
  -- operation that removes this migration's grant.
  IF pg_catalog.pg_has_role(
    'postgres', 'li_memory_function_owner', 'SET'
  ) OR pg_catalog.pg_has_role(
    'postgres', 'li_memory_function_owner', 'USAGE'
  ) THEN
    RAISE EXCEPTION 'Temporary function-owner authority was not removed';
  END IF;
END $$;

INSERT INTO li_memory.schema_versions(version, description)
VALUES ('0.24', 'Fix specialist history status ambiguity')
ON CONFLICT(version) DO NOTHING;

COMMIT;
