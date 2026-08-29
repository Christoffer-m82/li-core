BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.24') THEN
    RAISE EXCEPTION 'Migration 025 requires schema version 0.24';
  END IF;
END $$;

-- The original private-deletion migration shared version 0.21 with the artifact
-- library migration and was therefore skipped by the staging apply sequence.
-- Restore the missing owner-only function without broadening runtime access.
GRANT DELETE ON li_runtime_data.specialist_interactions TO li_memory_function_owner;
GRANT li_memory_function_owner TO postgres;

DO $$
BEGIN
  IF NOT pg_catalog.pg_has_role(CURRENT_USER, 'li_memory_function_owner', 'SET') THEN
    RAISE EXCEPTION 'Migration role cannot assume li_memory_function_owner';
  END IF;
END $$;

GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE OR REPLACE FUNCTION li_api.delete_private_conversation(p_conversation_id UUID)
RETURNS TABLE (deleted BOOLEAN, specialist_interactions_deleted BIGINT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_runtime_data, li_conversation, li_memory, pg_catalog, pg_temp
AS $$
DECLARE
  v_user UUID;
BEGIN
  SELECT u.id INTO v_user
  FROM li_memory.users AS u
  WHERE u.user_key = 'christoffer' AND u.status = 'active'
  LIMIT 1;

  IF NOT EXISTS (
    SELECT 1
    FROM li_conversation.conversations AS c
    WHERE c.id = p_conversation_id AND c.owner_user_id = v_user
  ) THEN
    deleted := FALSE;
    specialist_interactions_deleted := 0;
    RETURN NEXT;
    RETURN;
  END IF;

  DELETE FROM li_runtime_data.specialist_interactions AS i
  WHERE i.conversation_id = p_conversation_id AND i.owner_user_id = v_user;
  GET DIAGNOSTICS specialist_interactions_deleted = ROW_COUNT;

  DELETE FROM li_conversation.conversations AS c
  WHERE c.id = p_conversation_id AND c.owner_user_id = v_user;
  deleted := FOUND;
  RETURN NEXT;
END;
$$;

REVOKE ALL ON FUNCTION li_api.delete_private_conversation(UUID)
FROM PUBLIC, anon, authenticated, service_role, li_memory_api,
  li_backend_runtime, li_memory_theo, li_artifact_retention,
  li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.delete_private_conversation(UUID)
TO li_memory_owner_confirmation;

RESET ROLE;
REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

DO $$
BEGIN
  IF (
    SELECT owner_role.rolname
    FROM pg_catalog.pg_proc AS p
    JOIN pg_catalog.pg_roles AS owner_role ON owner_role.oid = p.proowner
    WHERE p.oid = 'li_api.delete_private_conversation(uuid)'::REGPROCEDURE
  ) <> 'li_memory_function_owner' THEN
    RAISE EXCEPTION 'delete_private_conversation has unexpected owner';
  END IF;
  IF NOT pg_catalog.has_function_privilege(
    'li_memory_owner_confirmation',
    'li_api.delete_private_conversation(uuid)', 'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Owner runtime lacks private conversation deletion';
  END IF;
  IF pg_catalog.has_function_privilege(
    'li_backend_runtime',
    'li_api.delete_private_conversation(uuid)', 'EXECUTE'
  ) OR pg_catalog.has_function_privilege(
    'li_retention_runtime',
    'li_api.delete_private_conversation(uuid)', 'EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Non-owner runtime gained private conversation deletion';
  END IF;
  IF pg_catalog.has_schema_privilege(
    'li_memory_function_owner', 'li_api', 'CREATE'
  ) THEN
    RAISE EXCEPTION 'Temporary li_api CREATE authority was not removed';
  END IF;
  IF pg_catalog.pg_has_role(
    'postgres', 'li_memory_function_owner', 'SET'
  ) OR pg_catalog.pg_has_role(
    'postgres', 'li_memory_function_owner', 'USAGE'
  ) THEN
    RAISE EXCEPTION 'Temporary function-owner authority was not removed';
  END IF;
END $$;

INSERT INTO li_memory.schema_versions(version, description)
VALUES ('0.25', 'Restore owner-confirmed private conversation deletion')
ON CONFLICT(version) DO NOTHING;

COMMIT;
