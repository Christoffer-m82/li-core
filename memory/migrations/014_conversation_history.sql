BEGIN;

-- Conversation history is deliberately stored outside li_memory. It is
-- short-term runtime context, not canonical memory, and can only be reached
-- by the normal backend through the narrow li_api functions below.
CREATE SCHEMA IF NOT EXISTS li_conversation;
REVOKE ALL ON SCHEMA li_conversation FROM PUBLIC, anon, authenticated,
    service_role, li_memory_api, li_backend_runtime, li_memory_theo,
    li_memory_owner_confirmation;

CREATE TABLE li_conversation.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    retention_policy TEXT NOT NULL DEFAULT 'standard',
    retain_until TIMESTAMPTZ,
    privacy_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE li_conversation.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL
        REFERENCES li_conversation.conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL CHECK (btrim(content) <> ''),
    privacy_metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversation_owner_updated
    ON li_conversation.conversations(owner_user_id, updated_at DESC);
CREATE INDEX idx_conversation_messages_recent
    ON li_conversation.messages(conversation_id, created_at DESC, id DESC);

GRANT USAGE ON SCHEMA li_conversation TO li_memory_function_owner;
GRANT SELECT, INSERT, UPDATE ON li_conversation.conversations
    TO li_memory_function_owner;
GRANT SELECT, INSERT ON li_conversation.messages
    TO li_memory_function_owner;

GRANT li_memory_function_owner TO postgres;
GRANT USAGE, CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.create_conversation(
    p_retention_policy TEXT DEFAULT 'standard',
    p_retain_until TIMESTAMPTZ DEFAULT NULL,
    p_privacy_metadata JSONB DEFAULT '{}'::JSONB
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_conversation, li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_conversation_id UUID;
BEGIN
    SELECT id INTO v_user_id FROM li_memory.users
    WHERE user_key = 'christoffer' AND status = 'active' LIMIT 1;
    IF v_user_id IS NULL THEN RAISE EXCEPTION 'Active primary user not found'; END IF;

    INSERT INTO li_conversation.conversations (
        owner_user_id, retention_policy, retain_until, privacy_metadata
    ) VALUES (
        v_user_id, COALESCE(NULLIF(btrim(p_retention_policy), ''), 'standard'),
        p_retain_until, COALESCE(p_privacy_metadata, '{}'::JSONB)
    ) RETURNING id INTO v_conversation_id;
    RETURN v_conversation_id;
END;
$$;

CREATE FUNCTION li_api.append_conversation_message(
    p_conversation_id UUID,
    p_role TEXT,
    p_content TEXT,
    p_privacy_metadata JSONB DEFAULT '{}'::JSONB
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_conversation, li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_message_id UUID;
BEGIN
    SELECT id INTO v_user_id FROM li_memory.users
    WHERE user_key = 'christoffer' AND status = 'active' LIMIT 1;
    IF p_role NOT IN ('user', 'assistant') THEN RAISE EXCEPTION 'Invalid message role'; END IF;
    IF p_content IS NULL OR btrim(p_content) = '' THEN RAISE EXCEPTION 'Message content is required'; END IF;
    IF NOT EXISTS (
        SELECT 1 FROM li_conversation.conversations
        WHERE id = p_conversation_id AND owner_user_id = v_user_id AND status = 'active'
    ) THEN RAISE EXCEPTION 'Active conversation not found'; END IF;

    INSERT INTO li_conversation.messages (
        conversation_id, role, content, privacy_metadata
    ) VALUES (
        p_conversation_id, p_role, p_content,
        COALESCE(p_privacy_metadata, '{}'::JSONB)
    ) RETURNING id INTO v_message_id;
    UPDATE li_conversation.conversations SET updated_at = NOW()
    WHERE id = p_conversation_id;
    RETURN v_message_id;
END;
$$;

CREATE FUNCTION li_api.get_recent_conversation_messages(
    p_conversation_id UUID,
    p_limit INTEGER DEFAULT 12
)
RETURNS TABLE (message_id UUID, role TEXT, content TEXT, created_at TIMESTAMPTZ)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_conversation, li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_limit INTEGER;
BEGIN
    SELECT id INTO v_user_id FROM li_memory.users
    WHERE user_key = 'christoffer' AND status = 'active' LIMIT 1;
    IF NOT EXISTS (
        SELECT 1 FROM li_conversation.conversations
        WHERE id = p_conversation_id AND owner_user_id = v_user_id AND status = 'active'
    ) THEN RAISE EXCEPTION 'Active conversation not found'; END IF;
    v_limit := LEAST(GREATEST(COALESCE(p_limit, 12), 1), 40);

    RETURN QUERY
    SELECT recent.id, recent.role, recent.content, recent.created_at
    FROM (
        SELECT m.id, m.role, m.content, m.created_at
        FROM li_conversation.messages m
        WHERE m.conversation_id = p_conversation_id
        ORDER BY m.created_at DESC, m.id DESC LIMIT v_limit
    ) recent
    ORDER BY recent.created_at, recent.id;
END;
$$;

RESET ROLE;

REVOKE ALL ON FUNCTION li_api.create_conversation(TEXT, TIMESTAMPTZ, JSONB)
    FROM PUBLIC, anon, authenticated, service_role, li_memory_theo,
    li_memory_owner_confirmation;
REVOKE ALL ON FUNCTION li_api.append_conversation_message(UUID, TEXT, TEXT, JSONB)
    FROM PUBLIC, anon, authenticated, service_role, li_memory_theo,
    li_memory_owner_confirmation;
REVOKE ALL ON FUNCTION li_api.get_recent_conversation_messages(UUID, INTEGER)
    FROM PUBLIC, anon, authenticated, service_role, li_memory_theo,
    li_memory_owner_confirmation;
GRANT EXECUTE ON FUNCTION li_api.create_conversation(TEXT, TIMESTAMPTZ, JSONB)
    TO li_memory_api;
GRANT EXECUTE ON FUNCTION li_api.append_conversation_message(UUID, TEXT, TEXT, JSONB)
    TO li_memory_api;
GRANT EXECUTE ON FUNCTION li_api.get_recent_conversation_messages(UUID, INTEGER)
    TO li_memory_api;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA li_conversation
    FROM li_backend_runtime, li_memory_api, li_memory_theo,
    li_memory_owner_confirmation;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA li_conversation
    FROM li_backend_runtime, li_memory_api, li_memory_theo,
    li_memory_owner_confirmation;

REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
GRANT USAGE ON SCHEMA li_api TO li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

INSERT INTO li_memory.schema_versions (version, description)
VALUES ('0.14', 'Add separate bounded conversation and message history')
ON CONFLICT (version) DO NOTHING;

COMMIT;
