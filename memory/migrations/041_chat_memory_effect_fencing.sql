BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.40') THEN
    RAISE EXCEPTION USING ERRCODE = '55000',
      MESSAGE = 'Migration 041 requires applied schema 0.40';
  END IF;
  IF EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.41') THEN
    RAISE EXCEPTION USING ERRCODE = '55000',
      MESSAGE = 'Schema version 0.41 is already claimed';
  END IF;
  IF (SELECT COUNT(*) FROM li_memory.users
      WHERE user_key = 'christoffer' AND status = 'active') <> 1 THEN
    RAISE EXCEPTION 'Migration 041 requires exactly one active owner';
  END IF;
END $$;

CREATE TEMP TABLE migration_041_authority_state (
  migration_role NAME NOT NULL,
  added_owner BOOLEAN NOT NULL,
  added_create BOOLEAN NOT NULL
) ON COMMIT DROP;

INSERT INTO migration_041_authority_state
SELECT CURRENT_USER,
  NOT pg_catalog.pg_has_role(CURRENT_USER, 'li_memory_function_owner', 'SET'),
  NOT pg_catalog.has_schema_privilege('li_memory_function_owner', 'li_api', 'CREATE');

DO $$
DECLARE role_name NAME := (SELECT migration_role FROM migration_041_authority_state);
BEGIN
  IF (SELECT added_owner FROM migration_041_authority_state) THEN
    EXECUTE pg_catalog.format('GRANT li_memory_function_owner TO %I', role_name);
  END IF;
  IF (SELECT added_create FROM migration_041_authority_state) THEN
    EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner';
  END IF;
END $$;

SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.mark_chat_turn_effect_started(
 p_id UUID,p_request_hash TEXT,p_attempt_token UUID)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE t li_runtime_data.chat_turns%ROWTYPE; v_user UUID;
BEGIN
 SELECT id INTO STRICT v_user FROM li_memory.users
 WHERE user_key='christoffer' AND status='active';
 SELECT * INTO t FROM li_runtime_data.chat_turns
 WHERE id=p_id AND owner_user_id=v_user FOR UPDATE;
 IF NOT FOUND OR p_request_hash IS NULL OR t.request_hash<>p_request_hash
   OR p_attempt_token IS NULL OR t.attempt_token IS DISTINCT FROM p_attempt_token
   OR t.state<>'accepted' OR t.lease_expires_at<=NOW() THEN
   RAISE EXCEPTION 'Chat turn effect attempt is stale or unavailable';
 END IF;
 -- Write-ahead uncertainty: a crash after this commit must not blindly repeat
 -- a memory mutation, even when it occurs after model response_ready.
 UPDATE li_runtime_data.chat_turns SET external_effect_started=TRUE,
   external_effect_state='dispatched',lease_expires_at=NOW()+INTERVAL '3 minutes',
   updated_at=NOW() WHERE id=p_id RETURNING * INTO t;
 RETURN jsonb_build_object('turn_id',t.id,'state',t.state,
   'progress_stage',t.progress_stage,'external_effect_state',t.external_effect_state);
END $$;


RESET ROLE;
REVOKE ALL ON FUNCTION li_api.mark_chat_turn_effect_started(UUID,TEXT,UUID)
FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_api,
 li_memory_theo,li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.mark_chat_turn_effect_started(UUID,TEXT,UUID)
TO li_memory_api;

DO $$
DECLARE role_name NAME := (SELECT migration_role FROM migration_041_authority_state);
BEGIN
 IF (SELECT added_create FROM migration_041_authority_state) THEN
   EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner';
 END IF;
 IF (SELECT added_owner FROM migration_041_authority_state) THEN
   EXECUTE pg_catalog.format('REVOKE li_memory_function_owner FROM %I',role_name);
 END IF;
END $$;

DO $$
DECLARE v_role TEXT; role_name NAME := (SELECT migration_role FROM migration_041_authority_state);
BEGIN
 IF (SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid=
   'li_api.mark_chat_turn_effect_started(uuid,text,uuid)'::REGPROCEDURE)
   IS DISTINCT FROM 'li_memory_function_owner' THEN
   RAISE EXCEPTION 'Unexpected effect fence function owner';
 END IF;
 IF NOT has_function_privilege('li_memory_api',
   'li_api.mark_chat_turn_effect_started(uuid,text,uuid)','EXECUTE') THEN
   RAISE EXCEPTION 'Li cannot call the effect fence';
 END IF;
 -- li_backend_runtime already inherits li_memory_api through migration 006.
 FOREACH v_role IN ARRAY ARRAY['anon','authenticated','service_role',
   'li_memory_theo','li_memory_owner_confirmation','li_artifact_retention','li_retention_runtime']
 LOOP
   IF has_function_privilege(v_role,
     'li_api.mark_chat_turn_effect_started(uuid,text,uuid)','EXECUTE') THEN
     RAISE EXCEPTION 'Effect fence authority exceeds Li runtime';
   END IF;
 END LOOP;
 IF has_table_privilege('li_memory_api','li_runtime_data.chat_turns','UPDATE') THEN
   RAISE EXCEPTION 'Li retained direct turn-table write access';
 END IF;
 IF (SELECT added_create FROM migration_041_authority_state)
   AND has_schema_privilege('li_memory_function_owner','li_api','CREATE') THEN
   RAISE EXCEPTION 'Temporary schema authority was not removed';
 END IF;
 IF (SELECT added_owner FROM migration_041_authority_state)
   AND (pg_has_role(role_name,'li_memory_function_owner','SET')
     OR pg_has_role(role_name,'li_memory_function_owner','USAGE')) THEN
   RAISE EXCEPTION 'Temporary function-owner authority was not removed';
 END IF;
END $$;

INSERT INTO li_memory.schema_versions(version,description)
VALUES ('0.41','Fenced write-ahead uncertainty for chat memory mutations');
COMMIT;
