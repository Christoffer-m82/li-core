BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.22') THEN
    RAISE EXCEPTION USING ERRCODE = '55000',
      MESSAGE = 'Migration 023 requires migration 022 (schema 0.22)';
  END IF;
END;
$$;

-- Migration 017 created reserve_artifact as this NOLOGIN owner and then removed
-- its CREATE privilege on li_api. Verify the expected owner through the catalogs
-- before temporarily restoring only the authority needed to replace the function.
DO $$
DECLARE
  function_owner TEXT;
BEGIN
  SELECT owner_role.rolname
  INTO function_owner
  FROM pg_catalog.pg_proc AS p
  JOIN pg_catalog.pg_namespace AS n ON n.oid = p.pronamespace
  JOIN pg_catalog.pg_roles AS owner_role ON owner_role.oid = p.proowner
  WHERE n.nspname = 'li_api'
    AND p.proname = 'reserve_artifact'
    AND pg_catalog.pg_get_function_identity_arguments(p.oid) =
      'p_filename text, p_content_type text, p_size bigint, p_source text, p_conversation uuid';

  IF function_owner IS DISTINCT FROM 'li_memory_function_owner' THEN
    RAISE EXCEPTION 'reserve_artifact has unexpected owner %', function_owner;
  END IF;

  IF NOT pg_catalog.has_schema_privilege(
    'li_memory_function_owner', 'li_api', 'USAGE'
  ) THEN
    RAISE EXCEPTION 'li_memory_function_owner lacks expected USAGE on li_api';
  END IF;
END;
$$;

GRANT li_memory_function_owner TO postgres;

DO $$
BEGIN
  IF NOT pg_catalog.pg_has_role(
    CURRENT_USER, 'li_memory_function_owner', 'SET'
  ) THEN
    RAISE EXCEPTION 'Migration role cannot assume li_memory_function_owner';
  END IF;
END;
$$;

GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE OR REPLACE FUNCTION li_api.reserve_artifact(
  p_filename TEXT,
  p_content_type TEXT,
  p_size BIGINT,
  p_source TEXT,
  p_conversation UUID DEFAULT NULL
)
RETURNS TABLE (artifact_id UUID, owner_user_id UUID, expires_at TIMESTAMPTZ)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_conversation, li_memory, pg_catalog, pg_temp AS $$
DECLARE
  v_user UUID;
  v_days INTEGER;
  v_id UUID;
  v_exp TIMESTAMPTZ;
BEGIN
  SELECT u.id INTO v_user
  FROM li_memory.users AS u
  WHERE u.user_key = 'christoffer' AND u.status = 'active'
  LIMIT 1;

  IF p_conversation IS NOT NULL AND NOT EXISTS (
    SELECT 1
    FROM li_conversation.conversations AS c
    WHERE c.id = p_conversation AND c.owner_user_id = v_user
  ) THEN
    RAISE EXCEPTION 'Conversation not found';
  END IF;

  SELECT COALESCE((
    SELECT ps.artifact_retention_days
    FROM li_runtime_data.privacy_settings AS ps
    WHERE ps.owner_user_id = v_user
  ), 30) INTO v_days;

  v_exp := CASE
    WHEN p_source = 'li_generated' THEN NOW() + make_interval(days => v_days)
    ELSE NULL
  END;

  INSERT INTO li_runtime_data.artifacts(
    owner_user_id, conversation_id, safe_filename, content_type,
    size_bytes, source, expires_at
  ) VALUES (
    v_user, p_conversation, p_filename, p_content_type,
    p_size, p_source, v_exp
  ) RETURNING id INTO v_id;

  RETURN QUERY SELECT v_id, v_user, v_exp;
END;
$$;

RESET ROLE;
REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

DO $$
BEGIN
  IF (
    SELECT owner_role.rolname
    FROM pg_catalog.pg_proc AS p
    JOIN pg_catalog.pg_roles AS owner_role ON owner_role.oid = p.proowner
    WHERE p.oid = 'li_api.reserve_artifact(text,text,bigint,text,uuid)'::REGPROCEDURE
  ) <> 'li_memory_function_owner' THEN
    RAISE EXCEPTION 'reserve_artifact owner changed unexpectedly';
  END IF;

  IF NOT has_function_privilege(
    'li_backend_runtime',
    'li_api.reserve_artifact(text,text,bigint,text,uuid)',
    'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Backend runtime lost reserve_artifact execution';
  END IF;
END;
$$;

INSERT INTO li_memory.schema_versions(version, description)
VALUES ('0.23', 'Fix artifact reservation output-column ambiguity')
ON CONFLICT (version) DO NOTHING;

COMMIT;
