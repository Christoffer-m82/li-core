BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.26') THEN
    RAISE EXCEPTION 'Migration 027 requires schema version 0.26';
  END IF;
END $$;

DO $$
DECLARE function_owner TEXT;
BEGIN
  SELECT owner_role.rolname INTO function_owner
  FROM pg_catalog.pg_proc AS p
  JOIN pg_catalog.pg_roles AS owner_role ON owner_role.oid = p.proowner
  WHERE p.oid = 'li_api.list_specialist_interactions(text,integer)'::REGPROCEDURE;

  IF function_owner IS DISTINCT FROM 'li_memory_function_owner' THEN
    RAISE EXCEPTION 'list_specialist_interactions has unexpected owner %', function_owner;
  END IF;
END $$;

CREATE TEMP TABLE migration_027_authority_state (
  added_owner_membership BOOLEAN NOT NULL,
  added_schema_create BOOLEAN NOT NULL
) ON COMMIT DROP;

INSERT INTO migration_027_authority_state
SELECT
  NOT pg_catalog.pg_has_role(CURRENT_USER, 'li_memory_function_owner', 'SET'),
  NOT pg_catalog.has_schema_privilege('li_memory_function_owner', 'li_api', 'CREATE');

DO $$
BEGIN
  IF (SELECT added_owner_membership FROM migration_027_authority_state) THEN
    EXECUTE 'GRANT li_memory_function_owner TO postgres';
  END IF;
  IF (SELECT added_schema_create FROM migration_027_authority_state) THEN
    EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner';
  END IF;
END $$;

SET LOCAL ROLE li_memory_function_owner;

CREATE OR REPLACE FUNCTION li_api.list_specialist_interactions(
  p_specialist TEXT DEFAULT NULL,p_limit INTEGER DEFAULT 50)
RETURNS TABLE(interaction_id UUID,conversation_id UUID,request_id UUID,specialist_key TEXT,status TEXT,
 request_text TEXT,outcome JSONB,started_at TIMESTAMPTZ,completed_at TIMESTAMPTZ,updated_at TIMESTAMPTZ,
 explicit_request BOOLEAN,selection_mode TEXT,group_mode TEXT,route_category TEXT,route_reason TEXT,
 elapsed_ms BIGINT)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=li_runtime_data,li_memory,pg_catalog,pg_temp AS $$
DECLARE v_user UUID;
BEGIN
  SELECT u.id INTO v_user
  FROM li_memory.users AS u
  WHERE u.user_key='christoffer' AND u.status='active'
  LIMIT 1;

  RETURN QUERY SELECT i.id,i.conversation_id,i.request_id,i.specialist_key,i.status,i.request_text,
    i.outcome,i.started_at,i.completed_at,i.updated_at,i.explicit_request,i.selection_mode,
    i.group_mode,i.route_category,i.route_reason,
    (EXTRACT(EPOCH FROM (COALESCE(i.completed_at,NOW())-i.started_at))*1000)::BIGINT
  FROM li_runtime_data.specialist_interactions AS i
  WHERE i.owner_user_id=v_user AND (p_specialist IS NULL OR i.specialist_key=p_specialist)
  ORDER BY (i.status='active') DESC,i.updated_at DESC
  LIMIT LEAST(GREATEST(COALESCE(p_limit,50),1),100);
END; $$;

REVOKE ALL ON FUNCTION li_api.list_specialist_interactions(TEXT,INTEGER)
 FROM PUBLIC,anon,authenticated,service_role,li_backend_runtime,li_memory_theo,
 li_memory_owner_confirmation,li_artifact_retention,li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.list_specialist_interactions(TEXT,INTEGER)
 TO li_memory_api;

RESET ROLE;

DO $$
BEGIN
  IF (SELECT added_schema_create FROM migration_027_authority_state) THEN
    EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner';
  END IF;
  IF (SELECT added_owner_membership FROM migration_027_authority_state) THEN
    EXECUTE 'REVOKE li_memory_function_owner FROM postgres';
  END IF;
END $$;

DO $$
BEGIN
  IF (
    SELECT owner_role.rolname FROM pg_catalog.pg_proc AS p
    JOIN pg_catalog.pg_roles AS owner_role ON owner_role.oid=p.proowner
    WHERE p.oid='li_api.list_specialist_interactions(text,integer)'::REGPROCEDURE
  ) <> 'li_memory_function_owner' THEN
    RAISE EXCEPTION 'list_specialist_interactions owner changed unexpectedly';
  END IF;
  IF NOT pg_catalog.has_function_privilege(
    'li_backend_runtime','li_api.list_specialist_interactions(text,integer)','EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Backend runtime lost specialist history execution';
  END IF;
  IF pg_catalog.has_function_privilege(
    'li_retention_runtime','li_api.list_specialist_interactions(text,integer)','EXECUTE'
  ) THEN
    RAISE EXCEPTION 'Retention runtime gained specialist history execution';
  END IF;
END $$;

INSERT INTO li_memory.schema_versions(version,description)
VALUES('0.27','Fix generalized specialist history status ambiguity')
ON CONFLICT(version) DO NOTHING;

COMMIT;
