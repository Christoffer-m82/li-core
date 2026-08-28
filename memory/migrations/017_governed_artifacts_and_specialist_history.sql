BEGIN;

CREATE SCHEMA IF NOT EXISTS li_runtime_data;
REVOKE ALL ON SCHEMA li_runtime_data FROM PUBLIC, anon, authenticated,
    service_role, li_memory_api, li_backend_runtime, li_memory_theo,
    li_memory_owner_confirmation;

CREATE TABLE li_runtime_data.privacy_settings (
    owner_user_id UUID PRIMARY KEY REFERENCES li_memory.users(id),
    artifact_retention_days INTEGER NOT NULL DEFAULT 30
        CHECK (artifact_retention_days IN (7, 14, 30, 60, 90)),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE li_runtime_data.artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
    conversation_id UUID REFERENCES li_conversation.conversations(id) ON DELETE SET NULL,
    safe_filename TEXT NOT NULL CHECK (btrim(safe_filename) <> ''),
    content_type TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0 AND size_bytes <= 10485760),
    source TEXT NOT NULL CHECK (source IN ('upload', 'li_generated')),
    storage_object TEXT UNIQUE,
    storage_generation BIGINT,
    retention_state TEXT NOT NULL DEFAULT 'expiring'
        CHECK (retention_state IN ('expiring', 'kept', 'deleted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    kept_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    delete_reason TEXT,
    CHECK ((retention_state = 'kept' AND expires_at IS NULL) OR retention_state <> 'kept')
);
CREATE INDEX idx_artifacts_expiry ON li_runtime_data.artifacts(expires_at)
    WHERE retention_state = 'expiring';

CREATE TABLE li_runtime_data.specialist_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
    conversation_id UUID REFERENCES li_conversation.conversations(id) ON DELETE SET NULL,
    request_id UUID NOT NULL,
    specialist_key TEXT NOT NULL CHECK (specialist_key IN ('nora', 'victor', 'milo')),
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'failed')),
    request_text TEXT NOT NULL,
    outcome JSONB,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE li_runtime_data.privacy_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_runtime_data.specialist_interactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY privacy_function_owner_access ON li_runtime_data.privacy_settings
 FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY artifact_function_owner_access ON li_runtime_data.artifacts
 FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE POLICY specialist_function_owner_access ON li_runtime_data.specialist_interactions
 FOR ALL TO li_memory_function_owner USING(TRUE) WITH CHECK(TRUE);
CREATE INDEX idx_specialist_owner_activity
    ON li_runtime_data.specialist_interactions(owner_user_id, status, updated_at DESC);

GRANT USAGE ON SCHEMA li_runtime_data TO li_memory_function_owner;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA li_runtime_data
    TO li_memory_function_owner;
GRANT SELECT ON li_conversation.conversations, li_conversation.messages
    TO li_memory_function_owner;

GRANT li_memory_function_owner TO postgres;
GRANT USAGE, CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.get_privacy_settings()
RETURNS TABLE (artifact_retention_days INTEGER, updated_at TIMESTAMPTZ)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID;
BEGIN
  SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
  INSERT INTO li_runtime_data.privacy_settings(owner_user_id) VALUES (v_user)
    ON CONFLICT (owner_user_id) DO NOTHING;
  RETURN QUERY SELECT p.artifact_retention_days, p.updated_at
    FROM li_runtime_data.privacy_settings p WHERE p.owner_user_id=v_user;
END; $$;

CREATE FUNCTION li_api.set_artifact_retention_days(p_days INTEGER)
RETURNS INTEGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID;
BEGIN
  IF p_days NOT IN (7,14,30,60,90) THEN RAISE EXCEPTION 'Unsupported retention period'; END IF;
  SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
  INSERT INTO li_runtime_data.privacy_settings(owner_user_id, artifact_retention_days)
    VALUES(v_user,p_days) ON CONFLICT(owner_user_id) DO UPDATE
    SET artifact_retention_days=EXCLUDED.artifact_retention_days, updated_at=NOW();
  RETURN p_days;
END; $$;

CREATE FUNCTION li_api.reserve_artifact(p_filename TEXT, p_content_type TEXT,
  p_size BIGINT, p_source TEXT, p_conversation UUID DEFAULT NULL)
RETURNS TABLE (artifact_id UUID, owner_user_id UUID, expires_at TIMESTAMPTZ)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_conversation, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID; v_days INTEGER; v_id UUID; v_exp TIMESTAMPTZ;
BEGIN
  SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
  IF p_conversation IS NOT NULL AND NOT EXISTS (SELECT 1 FROM li_conversation.conversations
      WHERE id=p_conversation AND owner_user_id=v_user) THEN RAISE EXCEPTION 'Conversation not found'; END IF;
  SELECT COALESCE((SELECT artifact_retention_days FROM li_runtime_data.privacy_settings
      WHERE owner_user_id=v_user),30) INTO v_days;
  v_exp := CASE WHEN p_source='li_generated' THEN NOW()+make_interval(days=>v_days) ELSE NULL END;
  INSERT INTO li_runtime_data.artifacts(owner_user_id,conversation_id,safe_filename,
      content_type,size_bytes,source,expires_at)
    VALUES(v_user,p_conversation,p_filename,p_content_type,p_size,p_source,v_exp)
    RETURNING id INTO v_id;
  RETURN QUERY SELECT v_id,v_user,v_exp;
END; $$;

CREATE FUNCTION li_api.finalize_artifact(p_id UUID,p_object TEXT,p_generation BIGINT,
  p_keep BOOLEAN DEFAULT FALSE)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID;
BEGIN
  SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
  UPDATE li_runtime_data.artifacts SET storage_object=p_object,storage_generation=p_generation,
    retention_state=CASE WHEN p_keep THEN 'kept' ELSE 'expiring' END,
    expires_at=CASE WHEN p_keep THEN NULL ELSE COALESCE(expires_at,NOW()+INTERVAL '30 days') END,
    kept_at=CASE WHEN p_keep THEN NOW() ELSE NULL END
  WHERE id=p_id AND owner_user_id=v_user AND retention_state<>'deleted'; RETURN FOUND;
END; $$;

CREATE FUNCTION li_api.get_artifact(p_id UUID)
RETURNS TABLE (artifact_id UUID,owner_user_id UUID,safe_filename TEXT,content_type TEXT,
 size_bytes BIGINT,source TEXT,storage_object TEXT,retention_state TEXT,created_at TIMESTAMPTZ,
 expires_at TIMESTAMPTZ,kept_at TIMESTAMPTZ,deleted_at TIMESTAMPTZ)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID;
BEGIN SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
RETURN QUERY SELECT a.id,a.owner_user_id,a.safe_filename,a.content_type,a.size_bytes,a.source,
 a.storage_object,a.retention_state,a.created_at,a.expires_at,a.kept_at,a.deleted_at
 FROM li_runtime_data.artifacts a WHERE a.id=p_id AND a.owner_user_id=v_user; END; $$;

CREATE FUNCTION li_api.change_artifact_retention(p_id UUID,p_action TEXT)
RETURNS TABLE (storage_object TEXT,retention_state TEXT)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID;
BEGIN SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
IF p_action='keep' THEN UPDATE li_runtime_data.artifacts a SET retention_state='kept',expires_at=NULL,
 kept_at=NOW() WHERE a.id=p_id AND a.owner_user_id=v_user AND a.retention_state<>'deleted'
 RETURNING a.storage_object,a.retention_state INTO storage_object,retention_state;
ELSIF p_action='delete' THEN UPDATE li_runtime_data.artifacts a SET retention_state='deleted',
 deleted_at=NOW(),delete_reason='owner_request' WHERE a.id=p_id AND a.owner_user_id=v_user
 AND a.retention_state<>'deleted' RETURNING a.storage_object,a.retention_state INTO storage_object,retention_state;
ELSE RAISE EXCEPTION 'Invalid retention action'; END IF; RETURN NEXT; END; $$;

CREATE FUNCTION li_api.list_expired_artifacts(p_limit INTEGER DEFAULT 100)
RETURNS TABLE (artifact_id UUID,storage_object TEXT)
LANGUAGE sql SECURITY DEFINER
SET search_path = li_runtime_data, pg_catalog, pg_temp AS $$
 SELECT id,storage_object FROM li_runtime_data.artifacts WHERE retention_state='expiring'
 AND expires_at<=NOW() ORDER BY expires_at LIMIT LEAST(GREATEST(COALESCE(p_limit,100),1),500)
 FOR UPDATE SKIP LOCKED; $$;

CREATE FUNCTION li_api.mark_artifact_expired(p_id UUID)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, pg_catalog, pg_temp AS $$
BEGIN UPDATE li_runtime_data.artifacts SET retention_state='deleted',deleted_at=NOW(),
 delete_reason='retention_expired' WHERE id=p_id AND retention_state='expiring' AND expires_at<=NOW();
 RETURN FOUND; END; $$;

CREATE FUNCTION li_api.start_specialist_interaction(p_conversation UUID,p_request UUID,
 p_specialist TEXT,p_request_text TEXT)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_conversation, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID; v_id UUID;
BEGIN SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
IF p_conversation IS NOT NULL AND NOT EXISTS(SELECT 1 FROM li_conversation.conversations WHERE id=p_conversation AND owner_user_id=v_user)
 THEN RAISE EXCEPTION 'Conversation not found'; END IF;
INSERT INTO li_runtime_data.specialist_interactions(owner_user_id,conversation_id,request_id,
 specialist_key,status,request_text) VALUES(v_user,p_conversation,p_request,p_specialist,'active',p_request_text)
RETURNING id INTO v_id; RETURN v_id; END; $$;

CREATE FUNCTION li_api.finish_specialist_interaction(p_id UUID,p_status TEXT,p_outcome JSONB)
RETURNS BOOLEAN LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID;
BEGIN SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
UPDATE li_runtime_data.specialist_interactions SET status=p_status,outcome=p_outcome,
 completed_at=NOW(),updated_at=NOW() WHERE id=p_id AND owner_user_id=v_user AND status='active'; RETURN FOUND; END; $$;

CREATE FUNCTION li_api.list_specialist_interactions(p_specialist TEXT DEFAULT NULL,p_limit INTEGER DEFAULT 50)
RETURNS TABLE(interaction_id UUID,conversation_id UUID,request_id UUID,specialist_key TEXT,status TEXT,
 request_text TEXT,outcome JSONB,started_at TIMESTAMPTZ,completed_at TIMESTAMPTZ,updated_at TIMESTAMPTZ)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_runtime_data, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID;
BEGIN SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
RETURN QUERY SELECT i.id,i.conversation_id,i.request_id,i.specialist_key,i.status,i.request_text,
 i.outcome,i.started_at,i.completed_at,i.updated_at FROM li_runtime_data.specialist_interactions i
 WHERE i.owner_user_id=v_user AND (p_specialist IS NULL OR i.specialist_key=p_specialist)
 ORDER BY (i.status='active') DESC,i.updated_at DESC LIMIT LEAST(GREATEST(COALESCE(p_limit,50),1),100); END; $$;

CREATE FUNCTION li_api.list_conversations(p_limit INTEGER DEFAULT 30)
RETURNS TABLE(conversation_id UUID,title TEXT,created_at TIMESTAMPTZ,updated_at TIMESTAMPTZ)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_conversation, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user UUID;
BEGIN SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
RETURN QUERY SELECT c.id,COALESCE(left((SELECT m.content FROM li_conversation.messages m
 WHERE m.conversation_id=c.id AND m.role='user' ORDER BY m.created_at LIMIT 1),80),'New conversation'),
 c.created_at,c.updated_at FROM li_conversation.conversations c WHERE c.owner_user_id=v_user
 ORDER BY c.updated_at DESC LIMIT LEAST(GREATEST(COALESCE(p_limit,30),1),100); END; $$;

RESET ROLE;

REVOKE ALL ON FUNCTION li_api.get_privacy_settings(),li_api.set_artifact_retention_days(INTEGER),
 li_api.reserve_artifact(TEXT,TEXT,BIGINT,TEXT,UUID),li_api.finalize_artifact(UUID,TEXT,BIGINT,BOOLEAN),
 li_api.get_artifact(UUID),li_api.change_artifact_retention(UUID,TEXT),
 li_api.list_expired_artifacts(INTEGER),li_api.mark_artifact_expired(UUID),
 li_api.start_specialist_interaction(UUID,UUID,TEXT,TEXT),
 li_api.finish_specialist_interaction(UUID,TEXT,JSONB),
 li_api.list_specialist_interactions(TEXT,INTEGER),li_api.list_conversations(INTEGER)
 FROM PUBLIC,anon,authenticated,service_role,li_memory_theo,li_memory_owner_confirmation;
GRANT EXECUTE ON FUNCTION li_api.get_privacy_settings(),li_api.set_artifact_retention_days(INTEGER),
 li_api.reserve_artifact(TEXT,TEXT,BIGINT,TEXT,UUID),li_api.finalize_artifact(UUID,TEXT,BIGINT,BOOLEAN),
 li_api.get_artifact(UUID),li_api.change_artifact_retention(UUID,TEXT),
 li_api.list_expired_artifacts(INTEGER),li_api.mark_artifact_expired(UUID),
 li_api.start_specialist_interaction(UUID,UUID,TEXT,TEXT),
 li_api.finish_specialist_interaction(UUID,TEXT,JSONB),
 li_api.list_specialist_interactions(TEXT,INTEGER),li_api.list_conversations(INTEGER)
 TO li_memory_api;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA li_runtime_data FROM li_backend_runtime,
 li_memory_api,li_memory_theo,li_memory_owner_confirmation;
REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.17','Governed artifacts, privacy settings, specialist events, and conversation listing')
ON CONFLICT(version) DO NOTHING;
COMMIT;
