BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.39') THEN
    RAISE EXCEPTION USING ERRCODE = '55000',
      MESSAGE = 'Migration 040 requires applied schema 0.39';
  END IF;
  IF EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.40') THEN
    RAISE EXCEPTION USING ERRCODE = '55000',
      MESSAGE = 'Schema version 0.40 is already claimed';
  END IF;
  IF (SELECT COUNT(*) FROM li_memory.users
      WHERE user_key = 'christoffer' AND status = 'active') <> 1 THEN
    RAISE EXCEPTION 'Migration 040 requires exactly one active owner';
  END IF;
END $$;

CREATE TEMP TABLE migration_040_authority_state (
  migration_role NAME NOT NULL,
  added_owner BOOLEAN NOT NULL,
  added_create BOOLEAN NOT NULL
) ON COMMIT DROP;

INSERT INTO migration_040_authority_state
SELECT CURRENT_USER,
  NOT pg_catalog.pg_has_role(CURRENT_USER, 'li_memory_function_owner', 'SET'),
  NOT pg_catalog.has_schema_privilege('li_memory_function_owner', 'li_api', 'CREATE');

DO $$
DECLARE role_name NAME := (SELECT migration_role FROM migration_040_authority_state);
BEGIN
  IF (SELECT added_owner FROM migration_040_authority_state) THEN
    EXECUTE pg_catalog.format('GRANT li_memory_function_owner TO %I', role_name);
  END IF;
  IF (SELECT added_create FROM migration_040_authority_state) THEN
    EXECUTE 'GRANT CREATE ON SCHEMA li_api TO li_memory_function_owner';
  END IF;
END $$;

SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.list_owner_memory_proposals(p_limit INTEGER DEFAULT 20)
RETURNS TABLE (
  proposed_by_agent TEXT,
  proposed_class TEXT,
  proposed_domain TEXT,
  proposed_value_text TEXT,
  proposed_truth_status TEXT,
  proposed_temporal_status TEXT,
  proposed_sensitivity TEXT,
  proposal_status TEXT,
  reason TEXT,
  review_note TEXT,
  owner_confirmation_required BOOLEAN,
  created_at TIMESTAMPTZ,
  reviewed_at TIMESTAMPTZ
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
DECLARE
  v_user UUID;
  v_limit INTEGER := LEAST(GREATEST(COALESCE(p_limit, 20), 1), 50);
BEGIN
  SELECT u.id INTO STRICT v_user
  FROM li_memory.users u
  WHERE u.user_key = 'christoffer' AND u.status = 'active';

  RETURN QUERY
  SELECT
    LEFT(p.proposed_by_agent, 100),
    LEFT(p.proposed_class, 100),
    LEFT(p.proposed_domain, 100),
    LEFT(COALESCE(p.proposed_value_text, p.proposed_value_json::TEXT), 5000),
    LEFT(p.proposed_truth_status, 100),
    LEFT(p.proposed_temporal_status, 100),
    LEFT(COALESCE(p.proposed_sensitivity, 'personal'), 100),
    p.status,
    LEFT(p.reason, 2000),
    LEFT(p.metadata ->> 'theo_review_note', 2000),
    p.status = 'needs_user_confirmation',
    p.created_at,
    p.reviewed_at
  FROM li_memory.memory_write_proposals p
  WHERE p.owner_user_id = v_user
    AND p.status IN ('pending', 'needs_user_confirmation')
  ORDER BY (p.status = 'needs_user_confirmation') DESC, p.created_at DESC
  LIMIT v_limit;
END;
$$;

RESET ROLE;

REVOKE ALL ON FUNCTION li_api.list_owner_memory_proposals(INTEGER)
FROM PUBLIC, anon, authenticated, service_role, li_backend_runtime, li_memory_api,
  li_memory_theo, li_memory_owner_confirmation, li_artifact_retention, li_retention_runtime;
GRANT EXECUTE ON FUNCTION li_api.list_owner_memory_proposals(INTEGER)
TO li_memory_owner_confirmation;

REVOKE ALL PRIVILEGES ON li_memory.memory_write_proposals
FROM li_backend_runtime, li_memory_api, li_memory_theo, li_memory_owner_confirmation,
  li_artifact_retention, li_retention_runtime;

DO $$
DECLARE role_name NAME := (SELECT migration_role FROM migration_040_authority_state);
BEGIN
  IF (SELECT added_create FROM migration_040_authority_state) THEN
    EXECUTE 'REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner';
  END IF;
  IF (SELECT added_owner FROM migration_040_authority_state) THEN
    EXECUTE pg_catalog.format('REVOKE li_memory_function_owner FROM %I', role_name);
  END IF;
END $$;

DO $$
DECLARE
  function_owner NAME;
  role_name NAME := (SELECT migration_role FROM migration_040_authority_state);
BEGIN
  SELECT r.rolname INTO function_owner
  FROM pg_catalog.pg_proc p
  JOIN pg_catalog.pg_roles r ON r.oid = p.proowner
  WHERE p.oid = 'li_api.list_owner_memory_proposals(integer)'::REGPROCEDURE;

  IF function_owner IS DISTINCT FROM 'li_memory_function_owner' THEN
    RAISE EXCEPTION 'Owner memory proposal inspection function has unexpected owner';
  END IF;
  IF NOT pg_catalog.has_function_privilege(
      'li_memory_owner_confirmation',
      'li_api.list_owner_memory_proposals(integer)', 'EXECUTE')
    OR pg_catalog.has_function_privilege(
      'li_memory_api', 'li_api.list_owner_memory_proposals(integer)', 'EXECUTE')
    OR pg_catalog.has_function_privilege(
      'li_memory_theo', 'li_api.list_owner_memory_proposals(integer)', 'EXECUTE') THEN
    RAISE EXCEPTION 'Owner memory proposal inspection authority is broader than intended';
  END IF;
  IF pg_catalog.has_table_privilege(
      'li_memory_owner_confirmation', 'li_memory.memory_write_proposals', 'SELECT') THEN
    RAISE EXCEPTION 'Owner confirmation role retained direct proposal-table access';
  END IF;
  IF (SELECT added_create FROM migration_040_authority_state)
    AND pg_catalog.has_schema_privilege('li_memory_function_owner', 'li_api', 'CREATE') THEN
    RAISE EXCEPTION 'Temporary function-owner schema authority was not removed';
  END IF;
  IF (SELECT added_owner FROM migration_040_authority_state)
    AND (pg_catalog.pg_has_role(role_name, 'li_memory_function_owner', 'SET')
      OR pg_catalog.pg_has_role(role_name, 'li_memory_function_owner', 'USAGE')) THEN
    RAISE EXCEPTION 'Temporary function-owner authority was not removed';
  END IF;
END $$;

INSERT INTO li_memory.schema_versions(version, description)
VALUES ('0.40', 'Owner-scoped read-only memory proposal inspection');

COMMIT;
