BEGIN;

CREATE POLICY li_conversation_function_owner_access
ON li_conversation.conversations
FOR ALL TO li_memory_function_owner
USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY li_conversation_message_function_owner_access
ON li_conversation.messages
FOR ALL TO li_memory_function_owner
USING (TRUE) WITH CHECK (TRUE);

GRANT DELETE ON li_conversation.conversations TO li_memory_function_owner;

GRANT li_memory_function_owner TO postgres;
GRANT USAGE, CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.delete_conversation(p_conversation_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_conversation, li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_deleted BOOLEAN;
BEGIN
    SELECT id INTO v_user_id FROM li_memory.users
    WHERE user_key = 'christoffer' AND status = 'active' LIMIT 1;
    DELETE FROM li_conversation.conversations
    WHERE id = p_conversation_id AND owner_user_id = v_user_id;
    v_deleted := FOUND;
    RETURN v_deleted;
END;
$$;

RESET ROLE;

REVOKE ALL ON FUNCTION li_api.delete_conversation(UUID)
FROM PUBLIC, anon, authenticated, service_role, li_memory_api,
    li_backend_runtime, li_memory_theo;
GRANT EXECUTE ON FUNCTION li_api.delete_conversation(UUID)
TO li_memory_owner_confirmation;

REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
GRANT USAGE ON SCHEMA li_api TO li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

INSERT INTO li_memory.schema_versions (version, description)
VALUES ('0.15', 'Fix conversation RLS and add privileged conversation cleanup')
ON CONFLICT (version) DO NOTHING;

COMMIT;
