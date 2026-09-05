BEGIN;

DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.36') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Migration 037 requires applied schema 0.36';
 END IF;
 IF EXISTS(SELECT 1 FROM li_memory.schema_versions WHERE version='0.37') THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='Schema version 0.37 is already claimed';
 END IF;
END $$;

DO $$ DECLARE function_owner NAME; BEGIN
 SELECT r.rolname INTO function_owner
 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
 WHERE p.oid='li_api.get_recent_conversation_messages(uuid,integer)'::REGPROCEDURE;
 IF function_owner IS DISTINCT FROM 'li_memory_function_owner' THEN
  RAISE EXCEPTION 'get_recent_conversation_messages has unexpected owner %',function_owner;
 END IF;
 IF EXISTS(
  SELECT 1 FROM pg_catalog.pg_depend d
  WHERE d.refclassid='pg_catalog.pg_proc'::REGCLASS
   AND d.refobjid='li_api.get_recent_conversation_messages(uuid,integer)'::REGPROCEDURE
 ) THEN
  RAISE EXCEPTION USING ERRCODE='2BP01',
   MESSAGE='Cannot safely replace get_recent_conversation_messages: dependent objects exist',
   HINT='Review dependencies explicitly; migration 037 never uses CASCADE.';
 END IF;
END $$;

CREATE TEMP TABLE migration_037_authority_state(
 migration_role NAME NOT NULL,
 added_owner BOOLEAN NOT NULL,
 added_create BOOLEAN NOT NULL
) ON COMMIT DROP;
INSERT INTO migration_037_authority_state
SELECT CURRENT_USER,
 NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET'),
 NOT pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE');
DO $$ BEGIN
 IF (SELECT added_owner FROM migration_037_authority_state) THEN
  EXECUTE pg_catalog.format('GRANT li_memory_function_owner TO %I',(SELECT migration_role FROM migration_037_authority_state));
 END IF;
 IF (SELECT added_create FROM migration_037_authority_state) THEN
  EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner';
 END IF;
END $$;
DO $$ BEGIN
 IF NOT pg_catalog.pg_has_role(CURRENT_USER,'li_memory_function_owner','SET') THEN
  RAISE EXCEPTION 'Migration role cannot assume li_memory_function_owner';
 END IF;
END $$;

SET LOCAL ROLE li_memory_function_owner;
DROP FUNCTION li_api.get_recent_conversation_messages(UUID,INTEGER);
CREATE FUNCTION li_api.get_recent_conversation_messages(
 p_conversation_id UUID,p_limit INTEGER DEFAULT 12
) RETURNS TABLE(
 message_id UUID,role TEXT,content TEXT,privacy_metadata JSONB,created_at TIMESTAMPTZ
) LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_conversation,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user_id UUID;v_limit INTEGER;
BEGIN
 SELECT id INTO v_user_id FROM li_memory.users
 WHERE user_key='christoffer' AND status='active' LIMIT 1;
 IF NOT EXISTS(
  SELECT 1 FROM li_conversation.conversations
  WHERE id=p_conversation_id AND owner_user_id=v_user_id AND status='active'
 ) THEN RAISE EXCEPTION 'Active conversation not found'; END IF;
 v_limit:=LEAST(GREATEST(COALESCE(p_limit,12),1),40);
 RETURN QUERY
 SELECT recent.id,recent.role,recent.content,recent.privacy_metadata,recent.created_at
 FROM(
  SELECT m.id,m.role,m.content,m.privacy_metadata,m.created_at
  FROM li_conversation.messages m WHERE m.conversation_id=p_conversation_id
  ORDER BY m.created_at DESC,m.id DESC LIMIT v_limit
 ) recent ORDER BY recent.created_at,recent.id;
END $$;
REVOKE ALL ON FUNCTION li_api.get_recent_conversation_messages(UUID,INTEGER)
 FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_theo,
 li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.get_recent_conversation_messages(UUID,INTEGER)
 TO li_memory_api;
RESET ROLE;

DO $$ BEGIN
 IF (SELECT added_create FROM migration_037_authority_state) THEN
  EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner';
 END IF;
 IF (SELECT added_owner FROM migration_037_authority_state) THEN
  EXECUTE pg_catalog.format('REVOKE li_memory_function_owner FROM %I',(SELECT migration_role FROM migration_037_authority_state));
 END IF;
END $$;

DO $$ BEGIN
 IF (SELECT r.rolname FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
     WHERE p.oid='li_api.get_recent_conversation_messages(uuid,integer)'::REGPROCEDURE)
    IS DISTINCT FROM 'li_memory_function_owner' THEN
  RAISE EXCEPTION 'get_recent_conversation_messages owner changed unexpectedly';
 END IF;
 IF NOT pg_catalog.has_function_privilege(
  'li_backend_runtime','li_api.get_recent_conversation_messages(uuid,integer)','EXECUTE'
 ) THEN RAISE EXCEPTION 'Backend runtime lost conversation history execution'; END IF;
 IF pg_catalog.has_function_privilege(
  'li_retention_runtime','li_api.get_recent_conversation_messages(uuid,integer)','EXECUTE'
 ) THEN RAISE EXCEPTION 'Retention runtime gained conversation history execution'; END IF;
 IF (SELECT added_create FROM migration_037_authority_state)
    AND pg_catalog.has_schema_privilege('li_memory_function_owner','li_api','CREATE') THEN
  RAISE EXCEPTION 'Temporary li_api CREATE authority was not removed';
 END IF;
END $$;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.37','Preserve conversation privacy metadata during context retrieval');
COMMIT;
