BEGIN;

DO $$
BEGIN
  IF to_regclass('li_runtime_data.specialist_interactions') IS NULL
     OR NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version='0.25') THEN
    RAISE EXCEPTION USING ERRCODE='55000',
      MESSAGE='Migration 026 requires applied schema 0.25',
      HINT='Apply migrations through 025 first, then rerun this complete file.';
  END IF;
END;
$$;

ALTER TABLE li_runtime_data.specialist_interactions
  DROP CONSTRAINT IF EXISTS specialist_interactions_specialist_key_check;
ALTER TABLE li_runtime_data.specialist_interactions
  ADD CONSTRAINT specialist_interactions_specialist_key_check CHECK (specialist_key IN (
    'sofia','marco','elena','amelia','freja','oliver','james','victor','nora','milo','iris','clara'
  )),
  ADD COLUMN selection_mode TEXT NOT NULL DEFAULT 'li_selected'
    CHECK (selection_mode IN ('explicit','li_selected')),
  ADD COLUMN group_mode TEXT NOT NULL DEFAULT 'solo'
    CHECK (group_mode IN ('solo','multi')),
  ADD COLUMN route_category TEXT NOT NULL DEFAULT 'legacy',
  ADD COLUMN route_reason TEXT NOT NULL DEFAULT 'Recorded before generalized orchestration.';

DO $$
DECLARE
  function_owner TEXT;
BEGIN
  SELECT owner_role.rolname INTO function_owner
  FROM pg_catalog.pg_proc AS p
  JOIN pg_catalog.pg_roles AS owner_role ON owner_role.oid = p.proowner
  WHERE p.oid = 'li_api.list_specialist_interactions(text,integer)'::REGPROCEDURE;

  IF function_owner IS DISTINCT FROM 'li_memory_function_owner' THEN
    RAISE EXCEPTION 'list_specialist_interactions has unexpected owner %', function_owner;
  END IF;
  IF NOT pg_catalog.has_schema_privilege(
    'li_memory_function_owner', 'li_api', 'USAGE'
  ) THEN
    RAISE EXCEPTION 'li_memory_function_owner lacks expected USAGE on li_api';
  END IF;
  IF EXISTS (
    SELECT 1
    FROM pg_catalog.pg_depend AS d
    WHERE d.refclassid = 'pg_catalog.pg_proc'::REGCLASS
      AND d.refobjid = 'li_api.list_specialist_interactions(text,integer)'::REGPROCEDURE
  ) THEN
    RAISE EXCEPTION USING ERRCODE = '2BP01',
      MESSAGE = 'Cannot safely replace list_specialist_interactions: dependent objects exist',
      DETAIL = (
        SELECT string_agg(
          pg_catalog.pg_describe_object(d.classid, d.objid, d.objsubid), ', '
          ORDER BY pg_catalog.pg_describe_object(d.classid, d.objid, d.objsubid)
        )
        FROM pg_catalog.pg_depend AS d
        WHERE d.refclassid = 'pg_catalog.pg_proc'::REGCLASS
          AND d.refobjid = 'li_api.list_specialist_interactions(text,integer)'::REGPROCEDURE
      ),
      HINT = 'Review and handle each dependency explicitly; migration 026 never uses CASCADE.';
  END IF;
END;
$$;

CREATE TEMP TABLE migration_026_authority_state (
  added_owner_membership BOOLEAN NOT NULL,
  added_schema_create BOOLEAN NOT NULL
) ON COMMIT DROP;

INSERT INTO migration_026_authority_state
SELECT
  NOT pg_catalog.pg_has_role(CURRENT_USER, 'li_memory_function_owner', 'SET'),
  NOT pg_catalog.has_schema_privilege('li_memory_function_owner', 'li_api', 'CREATE');

DO $$
BEGIN
  IF (SELECT added_owner_membership FROM migration_026_authority_state) THEN
    EXECUTE 'GRANT li_memory_function_owner TO postgres';
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT pg_catalog.pg_has_role(CURRENT_USER, 'li_memory_function_owner', 'SET') THEN
    RAISE EXCEPTION 'Migration role cannot assume li_memory_function_owner';
  END IF;
END;
$$;

DO $$
BEGIN
  IF (SELECT added_schema_create FROM migration_026_authority_state) THEN
    EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner';
  END IF;
END;
$$;

SET LOCAL ROLE li_memory_function_owner;

DROP FUNCTION li_api.start_specialist_interaction(UUID,UUID,TEXT,TEXT);

CREATE OR REPLACE FUNCTION li_api.start_specialist_interaction(
  p_conversation UUID,p_request UUID,p_specialist TEXT,p_request_text TEXT,
  p_selection_mode TEXT,p_group_mode TEXT,p_route_category TEXT,p_route_reason TEXT)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_conversation,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID; v_id UUID;
BEGIN
  SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
  IF p_conversation IS NOT NULL AND NOT EXISTS(
    SELECT 1 FROM li_conversation.conversations WHERE id=p_conversation AND owner_user_id=v_user
  ) THEN RAISE EXCEPTION 'Conversation not found'; END IF;
  INSERT INTO li_runtime_data.specialist_interactions(
    owner_user_id,conversation_id,request_id,specialist_key,status,request_text,
    explicit_request,selection_mode,group_mode,route_category,route_reason)
  VALUES(v_user,p_conversation,p_request,p_specialist,'active',p_request_text,
    p_selection_mode='explicit',p_selection_mode,p_group_mode,p_route_category,p_route_reason)
  RETURNING id INTO v_id;
  RETURN v_id;
END; $$;

-- PostgreSQL cannot change a RETURNS TABLE/OUT-parameter row type with
-- CREATE OR REPLACE. The dependency guard above makes this exact-signature
-- drop fail closed instead of silently removing dependent objects.
DROP FUNCTION li_api.list_specialist_interactions(TEXT,INTEGER);

CREATE FUNCTION li_api.list_specialist_interactions(
  p_specialist TEXT DEFAULT NULL,p_limit INTEGER DEFAULT 50)
RETURNS TABLE(interaction_id UUID,conversation_id UUID,request_id UUID,specialist_key TEXT,status TEXT,
 request_text TEXT,outcome JSONB,started_at TIMESTAMPTZ,completed_at TIMESTAMPTZ,updated_at TIMESTAMPTZ,
 explicit_request BOOLEAN,selection_mode TEXT,group_mode TEXT,route_category TEXT,route_reason TEXT,
 elapsed_ms BIGINT)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID;
BEGIN
  SELECT id INTO v_user FROM li_memory.users WHERE user_key='christoffer' AND status='active' LIMIT 1;
  RETURN QUERY SELECT i.id,i.conversation_id,i.request_id,i.specialist_key,i.status,i.request_text,
    i.outcome,i.started_at,i.completed_at,i.updated_at,i.explicit_request,i.selection_mode,
    i.group_mode,i.route_category,i.route_reason,
    (EXTRACT(EPOCH FROM (COALESCE(i.completed_at,NOW())-i.started_at))*1000)::BIGINT
  FROM li_runtime_data.specialist_interactions i
  WHERE i.owner_user_id=v_user AND (p_specialist IS NULL OR i.specialist_key=p_specialist)
  ORDER BY (i.status='active') DESC,i.updated_at DESC
  LIMIT LEAST(GREATEST(COALESCE(p_limit,50),1),100);
END; $$;

REVOKE ALL ON FUNCTION li_api.list_specialist_interactions(TEXT,INTEGER)
 FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_theo,
 li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.list_specialist_interactions(TEXT,INTEGER)
 TO li_memory_api;

CREATE OR REPLACE FUNCTION li_api.list_agent_analytics_events()
RETURNS TABLE(interaction_id UUID,request_id UUID,specialist_key TEXT,status TEXT,request_text TEXT,outcome JSONB,
 started_at TIMESTAMPTZ,completed_at TIMESTAMPTZ,explicit_request BOOLEAN,used_in_final BOOLEAN,
 action_taken BOOLEAN,topic_keys TEXT[],selection_mode TEXT,group_mode TEXT,route_category TEXT)
LANGUAGE sql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
 SELECT i.id,i.request_id,i.specialist_key,i.status,i.request_text,i.outcome,i.started_at,i.completed_at,
 i.explicit_request,i.used_in_final,i.action_taken,i.topic_keys,i.selection_mode,i.group_mode,i.route_category
 FROM li_runtime_data.specialist_interactions i JOIN li_memory.users u ON u.id=i.owner_user_id
 WHERE u.user_key='christoffer' AND u.status='active' ORDER BY i.started_at DESC;
$$;

REVOKE ALL ON FUNCTION li_api.start_specialist_interaction(UUID,UUID,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT),
 li_api.list_agent_analytics_events()
 FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_theo,
 li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.start_specialist_interaction(UUID,UUID,TEXT,TEXT,TEXT,TEXT,TEXT,TEXT),
 li_api.list_agent_analytics_events() TO li_memory_api;

RESET ROLE;

DO $$
BEGIN
  IF (SELECT added_schema_create FROM migration_026_authority_state) THEN
    EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner';
  END IF;
  IF (SELECT added_owner_membership FROM migration_026_authority_state) THEN
    EXECUTE 'REVOKE li_memory_function_owner FROM postgres';
  END IF;
END;
$$;

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
  IF (SELECT added_schema_create FROM migration_026_authority_state)
     AND pg_catalog.has_schema_privilege(
       'li_memory_function_owner', 'li_api', 'CREATE'
     ) THEN
    RAISE EXCEPTION 'Temporary li_api CREATE authority was not removed';
  END IF;
  IF (SELECT added_owner_membership FROM migration_026_authority_state)
     AND (
       pg_catalog.pg_has_role('postgres', 'li_memory_function_owner', 'SET')
       OR pg_catalog.pg_has_role('postgres', 'li_memory_function_owner', 'USAGE')
     ) THEN
    RAISE EXCEPTION 'Temporary function-owner authority was not removed';
  END IF;
END;
$$;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.26','Generalized permanent specialist orchestration lifecycle metadata')
ON CONFLICT(version) DO NOTHING;
COMMIT;
