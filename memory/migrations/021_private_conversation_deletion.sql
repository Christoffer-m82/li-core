BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.20') THEN
    RAISE EXCEPTION 'Schema 0.20 is required before migration 021';
  END IF;
END;
$$;

GRANT DELETE ON li_runtime_data.specialist_interactions TO li_memory_function_owner;

GRANT li_memory_function_owner TO postgres;
GRANT USAGE, CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.delete_private_conversation(p_conversation_id UUID)
RETURNS TABLE (deleted BOOLEAN, specialist_interactions_deleted BIGINT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_runtime_data, li_conversation, li_memory, pg_catalog, pg_temp
AS $$
DECLARE
  v_user UUID;
BEGIN
  SELECT id INTO v_user FROM li_memory.users
  WHERE user_key = 'christoffer' AND status = 'active' LIMIT 1;

  IF NOT EXISTS (
    SELECT 1 FROM li_conversation.conversations
    WHERE id = p_conversation_id AND owner_user_id = v_user
  ) THEN
    deleted := FALSE;
    specialist_interactions_deleted := 0;
    RETURN NEXT;
    RETURN;
  END IF;

  DELETE FROM li_runtime_data.specialist_interactions
  WHERE conversation_id = p_conversation_id AND owner_user_id = v_user;
  GET DIAGNOSTICS specialist_interactions_deleted = ROW_COUNT;

  DELETE FROM li_conversation.conversations
  WHERE id = p_conversation_id AND owner_user_id = v_user;
  deleted := FOUND;
  RETURN NEXT;
END;
$$;

RESET ROLE;

REVOKE ALL ON FUNCTION li_api.delete_private_conversation(UUID)
FROM PUBLIC, anon, authenticated, service_role, li_memory_api,
  li_backend_runtime, li_memory_theo;
GRANT EXECUTE ON FUNCTION li_api.delete_private_conversation(UUID)
TO li_memory_owner_confirmation;

REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
GRANT USAGE ON SCHEMA li_api TO li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

INSERT INTO li_memory.schema_versions (version, description)
VALUES ('0.21', 'Owner-confirmed deletion of private conversations and linked specialist history')
ON CONFLICT (version) DO NOTHING;

COMMIT;
