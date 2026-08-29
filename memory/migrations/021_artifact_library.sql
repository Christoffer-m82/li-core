BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version='0.20') THEN
    RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='Migration 021 requires migration 020';
  END IF;
END;
$$;

GRANT li_memory_function_owner TO postgres;
GRANT USAGE, CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.list_artifacts(p_limit INTEGER DEFAULT 50)
RETURNS TABLE (artifact_id UUID, conversation_id UUID, safe_filename TEXT,
  content_type TEXT, size_bytes BIGINT, source TEXT, retention_state TEXT,
  created_at TIMESTAMPTZ, expires_at TIMESTAMPTZ, kept_at TIMESTAMPTZ)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID;
BEGIN
  SELECT u.id INTO v_user FROM li_memory.users u
    WHERE u.user_key='christoffer' AND u.status='active' LIMIT 1;
  RETURN QUERY SELECT a.id,a.conversation_id,a.safe_filename,a.content_type,a.size_bytes,
    a.source,a.retention_state,a.created_at,a.expires_at,a.kept_at
  FROM li_runtime_data.artifacts a
  WHERE a.owner_user_id=v_user AND a.retention_state IN ('expiring','kept')
    AND a.storage_object IS NOT NULL
  ORDER BY a.created_at DESC
  LIMIT LEAST(GREATEST(COALESCE(p_limit,50),1),100);
END;
$$;

RESET ROLE;
REVOKE ALL ON FUNCTION li_api.list_artifacts(INTEGER)
  FROM PUBLIC,anon,authenticated,service_role,li_memory_theo,li_memory_owner_confirmation;
GRANT EXECUTE ON FUNCTION li_api.list_artifacts(INTEGER) TO li_memory_api;
REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.21','Owner-scoped active artifact library') ON CONFLICT(version) DO NOTHING;
COMMIT;
