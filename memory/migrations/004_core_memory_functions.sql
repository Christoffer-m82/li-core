BEGIN;

-- ============================================================
-- Li OS Core Memory Functions
-- Migration: 004
--
-- Purpose:
-- Create the first controlled Memory API operations for Li OS.
--
-- Initial capabilities:
--
-- 1. Read the active primary-user identity.
-- 2. Store low-risk explicit memories stated by Christoffer.
-- 3. Submit memory proposals for Theo to review.
-- 4. Retrieve relevant canonical memories for Li.
--
-- IMPORTANT:
-- This migration is intentionally single-user.
-- All user operations are restricted to Christoffer.
--
-- Future secondary users require a separate authenticated
-- user-scope architecture before these functions are expanded.
-- ============================================================


-- ============================================================
-- 1. TEMPORARY MIGRATION OWNERSHIP PERMISSIONS
-- ============================================================

GRANT li_memory_function_owner TO postgres;

GRANT USAGE, CREATE
ON SCHEMA li_api
TO li_memory_function_owner;


-- ============================================================
-- 2. GET PRIMARY USER
-- ============================================================

CREATE OR REPLACE FUNCTION li_api.get_primary_user()
RETURNS TABLE (
    user_id UUID,
    user_key TEXT,
    full_name TEXT,
    display_name TEXT,
    memory_namespace TEXT
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
    SELECT
        u.id,
        u.user_key,
        u.full_name,
        u.display_name,
        u.memory_namespace
    FROM li_memory.users u
    WHERE u.user_key = 'christoffer'
      AND u.status = 'active'
    LIMIT 1;
$$;


ALTER FUNCTION li_api.get_primary_user()
OWNER TO li_memory_function_owner;


REVOKE ALL
ON FUNCTION li_api.get_primary_user()
FROM PUBLIC, anon, authenticated, service_role;


GRANT EXECUTE
ON FUNCTION li_api.get_primary_user()
TO li_memory_api;


-- ============================================================
-- 3. STORE EXPLICIT LOW-RISK MEMORY
-- ============================================================

-- This function is intentionally restrictive.
--
-- Li may use it only when Christoffer explicitly states:
--
--   explicit_fact
--   explicit_preference
--   explicit_opinion
--
-- Only low or personal sensitivity is accepted.
--
-- Sensitive and highly sensitive information must go through
-- Theo's proposal/review process instead.

CREATE OR REPLACE FUNCTION li_api.store_explicit_memory(
    p_memory_class TEXT,
    p_domain TEXT,
    p_value_text TEXT,
    p_title TEXT DEFAULT NULL,
    p_sensitivity TEXT DEFAULT 'personal',
    p_private_to_li BOOLEAN DEFAULT FALSE,
    p_source_reference TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_memory_id UUID;
BEGIN

    IF p_memory_class NOT IN (
        'explicit_fact',
        'explicit_preference',
        'explicit_opinion'
    ) THEN
        RAISE EXCEPTION
            'Direct memory write is not allowed for memory class: %',
            p_memory_class;
    END IF;


    IF p_domain IS NULL
       OR btrim(p_domain) = '' THEN
        RAISE EXCEPTION
            'Memory domain is required';
    END IF;


    IF p_value_text IS NULL
       OR btrim(p_value_text) = '' THEN
        RAISE EXCEPTION
            'Memory value is required';
    END IF;


    IF p_sensitivity NOT IN (
        'low',
        'personal'
    ) THEN
        RAISE EXCEPTION
            'Sensitivity % requires Theo review',
            p_sensitivity;
    END IF;


    SELECT id
    INTO v_user_id
    FROM li_memory.users
    WHERE user_key = 'christoffer'
      AND status = 'active'
    LIMIT 1;


    IF v_user_id IS NULL THEN
        RAISE EXCEPTION
            'Active primary user not found';
    END IF;


    INSERT INTO li_memory.memory_records (
        owner_user_id,
        memory_class,
        domain,
        title,
        value_text,
        source_type,
        source_user_id,
        source_agent,
        source_reference,
        confidence,
        truth_status,
        temporal_status,
        sensitivity,
        private_to_li,
        confirmed_by_user
    )
    VALUES (
        v_user_id,
        p_memory_class,
        btrim(p_domain),
        NULLIF(btrim(p_title), ''),
        btrim(p_value_text),
        'user_explicit',
        v_user_id,
        'li',
        NULLIF(btrim(p_source_reference), ''),
        1.000,
        'confirmed',
        'current',
        p_sensitivity,
        p_private_to_li,
        TRUE
    )
    RETURNING id
    INTO v_memory_id;


    INSERT INTO li_memory.memory_audit_log (
        owner_user_id,
        actor_type,
        actor_id,
        action,
        resource_type,
        resource_id,
        purpose,
        permission_basis,
        sensitivity,
        success
    )
    VALUES (
        v_user_id,
        'agent',
        'li',
        'create_explicit_memory',
        'memory_record',
        v_memory_id,
        'Store explicit user-provided memory',
        'li_direct_low_risk_explicit_memory',
        p_sensitivity,
        TRUE
    );


    RETURN v_memory_id;

END;
$$;


ALTER FUNCTION li_api.store_explicit_memory(
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    BOOLEAN,
    TEXT
)
OWNER TO li_memory_function_owner;


REVOKE ALL
ON FUNCTION li_api.store_explicit_memory(
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    BOOLEAN,
    TEXT
)
FROM PUBLIC, anon, authenticated, service_role;


GRANT EXECUTE
ON FUNCTION li_api.store_explicit_memory(
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    BOOLEAN,
    TEXT
)
TO li_memory_api;


-- ============================================================
-- 4. PROPOSE MEMORY FOR THEO
-- ============================================================

-- Specialists and Li may propose memories.
--
-- A proposal is NOT canonical memory.
-- Theo must review it before canonicalization.

CREATE OR REPLACE FUNCTION li_api.propose_memory(
    p_proposed_by_agent TEXT,
    p_memory_class TEXT,
    p_domain TEXT,
    p_value_text TEXT,
    p_reason TEXT DEFAULT NULL,
    p_truth_status TEXT DEFAULT NULL,
    p_temporal_status TEXT DEFAULT NULL,
    p_sensitivity TEXT DEFAULT 'personal',
    p_source_reference TEXT DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_proposal_id UUID;
BEGIN

    IF p_proposed_by_agent NOT IN (
        'li',
        'sofia',
        'marco',
        'elena',
        'amelia',
        'freja',
        'oliver',
        'james',
        'victor',
        'nora',
        'milo',
        'iris',
        'clara',
        'ada',
        'theo',
        'heimdall'
    ) THEN
        RAISE EXCEPTION
            'Unknown Li OS agent: %',
            p_proposed_by_agent;
    END IF;


    IF p_memory_class NOT IN (
        'explicit_fact',
        'explicit_preference',
        'explicit_opinion',
        'observation',
        'inference',
        'historical_fact',
        'outcome',
        'commitment',
        'open_loop',
        'temporary_context'
    ) THEN
        RAISE EXCEPTION
            'Invalid memory class: %',
            p_memory_class;
    END IF;


    IF p_domain IS NULL
       OR btrim(p_domain) = '' THEN
        RAISE EXCEPTION
            'Memory domain is required';
    END IF;


    IF p_value_text IS NULL
       OR btrim(p_value_text) = '' THEN
        RAISE EXCEPTION
            'Memory value is required';
    END IF;


    IF p_truth_status IS NOT NULL
       AND p_truth_status NOT IN (
            'confirmed',
            'likely',
            'inferred',
            'disputed',
            'outdated',
            'unknown'
       ) THEN
        RAISE EXCEPTION
            'Invalid truth status: %',
            p_truth_status;
    END IF;


    IF p_temporal_status IS NOT NULL
       AND p_temporal_status NOT IN (
            'current',
            'historical',
            'planned',
            'temporary',
            'unresolved'
       ) THEN
        RAISE EXCEPTION
            'Invalid temporal status: %',
            p_temporal_status;
    END IF;


    IF p_sensitivity NOT IN (
        'low',
        'personal',
        'sensitive',
        'highly_sensitive'
    ) THEN
        RAISE EXCEPTION
            'Invalid sensitivity: %',
            p_sensitivity;
    END IF;


    SELECT id
    INTO v_user_id
    FROM li_memory.users
    WHERE user_key = 'christoffer'
      AND status = 'active'
    LIMIT 1;


    IF v_user_id IS NULL THEN
        RAISE EXCEPTION
            'Active primary user not found';
    END IF;


    INSERT INTO li_memory.memory_write_proposals (
        owner_user_id,
        proposed_by_agent,
        proposed_class,
        proposed_domain,
        proposed_value_text,
        proposed_truth_status,
        proposed_temporal_status,
        proposed_sensitivity,
        reason,
        source_reference,
        status
    )
    VALUES (
        v_user_id,
        p_proposed_by_agent,
        p_memory_class,
        btrim(p_domain),
        btrim(p_value_text),
        p_truth_status,
        p_temporal_status,
        p_sensitivity,
        NULLIF(btrim(p_reason), ''),
        NULLIF(btrim(p_source_reference), ''),
        'pending'
    )
    RETURNING id
    INTO v_proposal_id;


    INSERT INTO li_memory.memory_audit_log (
        owner_user_id,
        actor_type,
        actor_id,
        action,
        resource_type,
        resource_id,
        purpose,
        permission_basis,
        sensitivity,
        success
    )
    VALUES (
        v_user_id,
        'agent',
        p_proposed_by_agent,
        'create_memory_proposal',
        'memory_write_proposal',
        v_proposal_id,
        'Propose memory for Theo review',
        'specialist_memory_proposal',
        p_sensitivity,
        TRUE
    );


    RETURN v_proposal_id;

END;
$$;


ALTER FUNCTION li_api.propose_memory(
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT
)
OWNER TO li_memory_function_owner;


REVOKE ALL
ON FUNCTION li_api.propose_memory(
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT
)
FROM PUBLIC, anon, authenticated, service_role;


GRANT EXECUTE
ON FUNCTION li_api.propose_memory(
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT
)
TO li_memory_api;


-- ============================================================
-- 5. RECALL MEMORY FOR LI
-- ============================================================

-- This is Li's initial canonical-memory retrieval function.
--
-- It is NOT intended for direct specialist use.
--
-- Specialists will later receive filtered context through Li
-- according to memory/permissions.yaml.

CREATE OR REPLACE FUNCTION li_api.recall_memory(
    p_query TEXT,
    p_domains TEXT[] DEFAULT NULL,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    memory_id UUID,
    memory_class TEXT,
    domain TEXT,
    title TEXT,
    value_text TEXT,
    truth_status TEXT,
    temporal_status TEXT,
    sensitivity TEXT,
    private_to_li BOOLEAN,
    confidence NUMERIC,
    source_type TEXT,
    source_reference TEXT,
    confirmed_by_user BOOLEAN,
    valid_from TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    relevance REAL
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_limit INTEGER;
BEGIN

    IF p_query IS NULL
       OR btrim(p_query) = '' THEN
        RAISE EXCEPTION
            'Search query is required';
    END IF;


    v_limit := LEAST(
        GREATEST(
            COALESCE(p_limit, 10),
            1
        ),
        50
    );


    SELECT id
    INTO v_user_id
    FROM li_memory.users
    WHERE user_key = 'christoffer'
      AND status = 'active'
    LIMIT 1;


    IF v_user_id IS NULL THEN
        RAISE EXCEPTION
            'Active primary user not found';
    END IF;


    INSERT INTO li_memory.memory_audit_log (
        owner_user_id,
        actor_type,
        actor_id,
        action,
        resource_type,
        purpose,
        permission_basis,
        sensitivity,
        success,
        metadata
    )
    VALUES (
        v_user_id,
        'agent',
        'li',
        'recall_memory',
        'memory_search',
        'Retrieve relevant canonical memory for Li',
        'li_broad_memory_access',
        'personal',
        TRUE,
        jsonb_build_object(
            'domains',
            p_domains,
            'limit',
            v_limit
        )
    );


    RETURN QUERY

    WITH search_query AS (
        SELECT plainto_tsquery(
            'simple',
            btrim(p_query)
        ) AS ts_query
    )

    SELECT
        m.id,
        m.memory_class,
        m.domain,
        m.title,
        m.value_text,
        m.truth_status,
        m.temporal_status,
        m.sensitivity,
        m.private_to_li,
        m.confidence,
        m.source_type,
        m.source_reference,
        m.confirmed_by_user,
        m.valid_from,
        m.valid_until,
        m.created_at,

        ts_rank(
            to_tsvector(
                'simple',
                COALESCE(m.title, '')
                || ' '
                || COALESCE(m.value_text, '')
            ),
            sq.ts_query
        )::REAL AS relevance

    FROM li_memory.memory_records m
    CROSS JOIN search_query sq

    WHERE m.owner_user_id = v_user_id

      AND m.deleted_at IS NULL

      AND (
          p_domains IS NULL
          OR m.domain = ANY(p_domains)
      )

      AND (
          to_tsvector(
              'simple',
              COALESCE(m.title, '')
              || ' '
              || COALESCE(m.value_text, '')
          ) @@ sq.ts_query

          OR COALESCE(m.title, '') ILIKE
             '%' || btrim(p_query) || '%'

          OR COALESCE(m.value_text, '') ILIKE
             '%' || btrim(p_query) || '%'
      )

    ORDER BY
        relevance DESC,
        m.confirmed_by_user DESC,
        m.confidence DESC,
        m.updated_at DESC

    LIMIT v_limit;

END;
$$;


ALTER FUNCTION li_api.recall_memory(
    TEXT,
    TEXT[],
    INTEGER
)
OWNER TO li_memory_function_owner;


REVOKE ALL
ON FUNCTION li_api.recall_memory(
    TEXT,
    TEXT[],
    INTEGER
)
FROM PUBLIC, anon, authenticated, service_role;


GRANT EXECUTE
ON FUNCTION li_api.recall_memory(
    TEXT,
    TEXT[],
    INTEGER
)
TO li_memory_api;


-- ============================================================
-- 6. LIST PENDING MEMORY PROPOSALS
-- ============================================================

-- This function is intended for Theo's future review workflow.
--
-- It returns proposals but does not approve them.

CREATE OR REPLACE FUNCTION li_api.get_pending_memory_proposals(
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    proposal_id UUID,
    proposed_by_agent TEXT,
    proposed_class TEXT,
    proposed_domain TEXT,
    proposed_value_text TEXT,
    proposed_truth_status TEXT,
    proposed_temporal_status TEXT,
    proposed_sensitivity TEXT,
    reason TEXT,
    source_reference TEXT,
    created_at TIMESTAMPTZ
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_limit INTEGER;
BEGIN

    v_limit := LEAST(
        GREATEST(
            COALESCE(p_limit, 20),
            1
        ),
        100
    );


    SELECT id
    INTO v_user_id
    FROM li_memory.users
    WHERE user_key = 'christoffer'
      AND status = 'active'
    LIMIT 1;


    IF v_user_id IS NULL THEN
        RAISE EXCEPTION
            'Active primary user not found';
    END IF;


    RETURN QUERY

    SELECT
        p.id,
        p.proposed_by_agent,
        p.proposed_class,
        p.proposed_domain,
        p.proposed_value_text,
        p.proposed_truth_status,
        p.proposed_temporal_status,
        p.proposed_sensitivity,
        p.reason,
        p.source_reference,
        p.created_at

    FROM li_memory.memory_write_proposals p

    WHERE p.owner_user_id = v_user_id
      AND p.status = 'pending'

    ORDER BY p.created_at ASC

    LIMIT v_limit;

END;
$$;


ALTER FUNCTION li_api.get_pending_memory_proposals(
    INTEGER
)
OWNER TO li_memory_function_owner;


REVOKE ALL
ON FUNCTION li_api.get_pending_memory_proposals(
    INTEGER
)
FROM PUBLIC, anon, authenticated, service_role;


GRANT EXECUTE
ON FUNCTION li_api.get_pending_memory_proposals(
    INTEGER
)
TO li_memory_api;


-- ============================================================
-- 7. RECONFIRM API ROLE HAS NO DIRECT TABLE ACCESS
-- ============================================================

REVOKE ALL PRIVILEGES
ON ALL TABLES IN SCHEMA li_memory
FROM li_memory_api;


REVOKE ALL PRIVILEGES
ON ALL SEQUENCES IN SCHEMA li_memory
FROM li_memory_api;


REVOKE EXECUTE
ON ALL FUNCTIONS IN SCHEMA li_memory
FROM li_memory_api;


-- ============================================================
-- 8. RECONFIRM API FUNCTION ACCESS
-- ============================================================

GRANT USAGE
ON SCHEMA li_api
TO li_memory_api;


GRANT EXECUTE
ON FUNCTION li_api.health_check()
TO li_memory_api;


GRANT EXECUTE
ON FUNCTION li_api.get_primary_user()
TO li_memory_api;


GRANT EXECUTE
ON FUNCTION li_api.store_explicit_memory(
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    BOOLEAN,
    TEXT
)
TO li_memory_api;


GRANT EXECUTE
ON FUNCTION li_api.propose_memory(
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    TEXT
)
TO li_memory_api;


GRANT EXECUTE
ON FUNCTION li_api.recall_memory(
    TEXT,
    TEXT[],
    INTEGER
)
TO li_memory_api;


GRANT EXECUTE
ON FUNCTION li_api.get_pending_memory_proposals(
    INTEGER
)
TO li_memory_api;


-- ============================================================
-- 9. REMOVE TEMPORARY FUNCTION CREATION AUTHORITY
-- ============================================================

REVOKE CREATE
ON SCHEMA li_api
FROM li_memory_function_owner;


GRANT USAGE
ON SCHEMA li_api
TO li_memory_function_owner;


-- ============================================================
-- 10. REMOVE TEMPORARY POSTGRES ROLE MEMBERSHIP
-- ============================================================

REVOKE li_memory_function_owner
FROM postgres;


-- ============================================================
-- 11. RECORD MIGRATION
-- ============================================================

INSERT INTO li_memory.schema_versions (
    version,
    description
)
VALUES (
    '0.4',
    'Add initial controlled Li OS memory API functions'
)
ON CONFLICT (version) DO NOTHING;


-- ============================================================
-- 12. FINAL STATE
-- ============================================================

-- Li OS now has controlled operations for:
--
-- get_primary_user
-- store_explicit_memory
-- propose_memory
-- recall_memory
-- get_pending_memory_proposals
--
-- The application role still has no direct canonical-memory
-- table privileges.
--
-- Sensitive canonical writes still require Theo review.
--
-- Multi-user access is intentionally not implemented yet.
--
-- Elias remains a future inactive secondary user.
--
-- No real personal memory should be added until these
-- functions have been tested with synthetic data.


COMMIT;
