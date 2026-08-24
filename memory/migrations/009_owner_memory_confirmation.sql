BEGIN;

-- ============================================================
-- Li OS Owner Memory Confirmation
-- Migration: 009
--
-- Purpose:
-- Add a separate owner authority for proposals that Theo has
-- marked as requiring explicit user confirmation.
--
-- Security model:
--
-- Li:
--   may propose
--
-- Theo:
--   may review ordinary proposals
--   may request owner confirmation
--   may NOT bypass a request for owner confirmation
--
-- Owner:
--   may confirm or reject a proposal that is specifically
--   waiting for owner confirmation
--
-- Confirmed proposals return to the Theo queue for final
-- canonical-memory promotion.
-- ============================================================


-- ============================================================
-- 1. CREATE OWNER CONFIRMATION CAPABILITY ROLE
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'li_memory_owner_confirmation'
    ) THEN
        CREATE ROLE li_memory_owner_confirmation
            NOLOGIN;
    END IF;
END
$$;


-- ============================================================
-- 2. CREATE OWNER RUNTIME LOGIN
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'li_owner_runtime'
    ) THEN
        CREATE ROLE li_owner_runtime
            LOGIN
            INHERIT
            CONNECTION LIMIT 3
            PASSWORD NULL;
    END IF;
END
$$;


ALTER ROLE li_owner_runtime
    SET statement_timeout = '30s';

ALTER ROLE li_owner_runtime
    SET lock_timeout = '5s';

ALTER ROLE li_owner_runtime
    SET idle_in_transaction_session_timeout = '60s';

ALTER ROLE li_owner_runtime
    SET search_path TO li_api, pg_catalog;


GRANT li_memory_owner_confirmation
TO li_owner_runtime;


-- Owner confirmation runtime must not inherit either Li's
-- ordinary capability or Theo's review capability.

REVOKE li_memory_api
FROM li_owner_runtime;

REVOKE li_memory_theo
FROM li_owner_runtime;


-- ============================================================
-- 3. DENY DIRECT CANONICAL ACCESS
-- ============================================================

REVOKE ALL
ON SCHEMA li_memory
FROM li_memory_owner_confirmation;

REVOKE ALL
ON SCHEMA li_memory
FROM li_owner_runtime;


REVOKE ALL PRIVILEGES
ON ALL TABLES IN SCHEMA li_memory
FROM li_memory_owner_confirmation;

REVOKE ALL PRIVILEGES
ON ALL TABLES IN SCHEMA li_memory
FROM li_owner_runtime;


REVOKE ALL PRIVILEGES
ON ALL SEQUENCES IN SCHEMA li_memory
FROM li_memory_owner_confirmation;

REVOKE ALL PRIVILEGES
ON ALL SEQUENCES IN SCHEMA li_memory
FROM li_owner_runtime;


-- ============================================================
-- 4. TEMPORARY MIGRATION ACCESS FOR FUNCTION OWNER
-- ============================================================

GRANT li_memory_function_owner
TO postgres;


GRANT USAGE, CREATE
ON SCHEMA li_api
TO li_memory_function_owner;


-- ============================================================
-- 5. PRESERVE THE EXISTING THEO REVIEW IMPLEMENTATION
-- ============================================================

-- The existing reviewed and tested implementation becomes an
-- internal function. A new public wrapper will enforce the
-- owner-confirmation boundary before calling it.

ALTER FUNCTION li_api.review_memory_proposal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
RENAME TO review_memory_proposal_internal;


-- Nobody except the SECURITY DEFINER owner should call the
-- internal function directly.

REVOKE ALL
ON FUNCTION li_api.review_memory_proposal_internal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
FROM PUBLIC;


REVOKE ALL
ON FUNCTION li_api.review_memory_proposal_internal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
FROM li_memory_api;


REVOKE ALL
ON FUNCTION li_api.review_memory_proposal_internal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
FROM li_memory_theo;


REVOKE ALL
ON FUNCTION li_api.review_memory_proposal_internal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
FROM li_memory_owner_confirmation;


-- ============================================================
-- 6. CREATE GUARDED THEO REVIEW WRAPPER
-- ============================================================

SET LOCAL ROLE li_memory_function_owner;


CREATE FUNCTION li_api.review_memory_proposal(
    p_proposal_id UUID,
    p_decision TEXT,
    p_review_note TEXT DEFAULT NULL,
    p_final_truth_status TEXT DEFAULT NULL,
    p_final_temporal_status TEXT DEFAULT NULL,
    p_final_confidence NUMERIC DEFAULT NULL
)
RETURNS TABLE(
    proposal_id UUID,
    proposal_status TEXT,
    memory_id UUID,
    outcome TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_memory, li_api, pg_catalog, pg_temp
AS $$
DECLARE
    v_status TEXT;
BEGIN

    SELECT p.status
    INTO v_status
    FROM li_memory.memory_write_proposals p
    WHERE p.id = p_proposal_id
    FOR UPDATE;


    IF v_status IS NULL THEN
        RAISE EXCEPTION
            'Memory proposal not found: %',
            p_proposal_id;
    END IF;


    -- Theo may not bypass an explicit request for owner
    -- confirmation.

    IF p_decision = 'approve'
       AND v_status = 'needs_user_confirmation' THEN

        RAISE EXCEPTION
            'Owner confirmation is required before this proposal can be approved';

    END IF;


    RETURN QUERY
    SELECT *
    FROM li_api.review_memory_proposal_internal(
        p_proposal_id,
        p_decision,
        p_review_note,
        p_final_truth_status,
        p_final_temporal_status,
        p_final_confidence
    );

END;
$$;


-- ============================================================
-- 7. CREATE OWNER CONFIRMATION FUNCTION
-- ============================================================

CREATE FUNCTION li_api.confirm_memory_proposal(
    p_proposal_id UUID,
    p_decision TEXT,
    p_note TEXT DEFAULT NULL
)
RETURNS TABLE(
    proposal_id UUID,
    proposal_status TEXT,
    outcome TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_proposal li_memory.memory_write_proposals%ROWTYPE;
BEGIN

    IF p_decision NOT IN (
        'confirm',
        'reject'
    ) THEN

        RAISE EXCEPTION
            'Invalid owner confirmation decision: %',
            p_decision;

    END IF;


    SELECT *
    INTO v_proposal
    FROM li_memory.memory_write_proposals
    WHERE id = p_proposal_id
    FOR UPDATE;


    IF NOT FOUND THEN

        RAISE EXCEPTION
            'Memory proposal not found: %',
            p_proposal_id;

    END IF;


    IF v_proposal.status <> 'needs_user_confirmation' THEN

        RAISE EXCEPTION
            'Proposal is not waiting for owner confirmation';

    END IF;


    -- ========================================================
    -- OWNER REJECTS
    -- ========================================================

    IF p_decision = 'reject' THEN

        UPDATE li_memory.memory_write_proposals

        SET
            status = 'rejected',

            resulting_memory_id = NULL,

            metadata =
                COALESCE(metadata, '{}'::jsonb)
                ||
                jsonb_build_object(
                    'owner_confirmation_status',
                    'rejected',
                    'owner_confirmed_by',
                    'christoffer',
                    'owner_confirmed_at',
                    NOW(),
                    'owner_confirmation_note',
                    p_note
                )

        WHERE id = p_proposal_id;


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
            success,
            metadata
        )
        VALUES (
            v_proposal.owner_user_id,
            'user',
            'christoffer',
            'reject_memory_proposal',
            'memory_write_proposal',
            p_proposal_id,
            'Explicit owner rejection of proposed memory',
            'explicit_owner_confirmation',
            COALESCE(
                v_proposal.proposed_sensitivity,
                'personal'
            ),
            TRUE,
            jsonb_build_object(
                'owner_decision',
                'reject',
                'note',
                p_note
            )
        );


        RETURN QUERY
        SELECT
            p_proposal_id,
            'rejected'::TEXT,
            'owner_rejected'::TEXT;


        RETURN;

    END IF;


    -- ========================================================
    -- OWNER CONFIRMS
    -- ========================================================

    -- Confirmation does not itself write canonical memory.
    --
    -- It authorizes the proposal to return to Theo's queue.
    -- Theo performs the final canonical-memory promotion using
    -- the existing reviewed memory logic.

    UPDATE li_memory.memory_write_proposals

    SET
        status = 'pending',

        resulting_memory_id = NULL,

        metadata =
            COALESCE(metadata, '{}'::jsonb)
            ||
            jsonb_build_object(
                'owner_confirmation_status',
                'confirmed',
                'owner_confirmed_by',
                'christoffer',
                'owner_confirmed_at',
                NOW(),
                'owner_confirmation_note',
                p_note
            )

    WHERE id = p_proposal_id;


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
        success,
        metadata
    )
    VALUES (
        v_proposal.owner_user_id,
        'user',
        'christoffer',
        'confirm_memory_proposal',
        'memory_write_proposal',
        p_proposal_id,
        'Explicit owner confirmation of proposed memory',
        'explicit_owner_confirmation',
        COALESCE(
            v_proposal.proposed_sensitivity,
            'personal'
        ),
        TRUE,
        jsonb_build_object(
            'owner_decision',
            'confirm',
            'note',
            p_note
        )
    );


    RETURN QUERY
    SELECT
        p_proposal_id,
        'pending'::TEXT,
        'owner_confirmed_pending_theo'::TEXT;

END;
$$;


RESET ROLE;


-- ============================================================
-- 8. LOCK DOWN PUBLIC FUNCTIONS
-- ============================================================

REVOKE ALL
ON FUNCTION li_api.review_memory_proposal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
FROM PUBLIC;


REVOKE ALL
ON FUNCTION li_api.review_memory_proposal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
FROM li_memory_api;


REVOKE ALL
ON FUNCTION li_api.review_memory_proposal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
FROM li_memory_owner_confirmation;


GRANT EXECUTE
ON FUNCTION li_api.review_memory_proposal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
TO li_memory_theo;


REVOKE ALL
ON FUNCTION li_api.confirm_memory_proposal(
    UUID,
    TEXT,
    TEXT
)
FROM PUBLIC;


REVOKE ALL
ON FUNCTION li_api.confirm_memory_proposal(
    UUID,
    TEXT,
    TEXT
)
FROM li_memory_api;


REVOKE ALL
ON FUNCTION li_api.confirm_memory_proposal(
    UUID,
    TEXT,
    TEXT
)
FROM li_memory_theo;


GRANT EXECUTE
ON FUNCTION li_api.confirm_memory_proposal(
    UUID,
    TEXT,
    TEXT
)
TO li_memory_owner_confirmation;


-- ============================================================
-- 9. REMOVE TEMPORARY MIGRATION ACCESS
-- ============================================================

REVOKE CREATE
ON SCHEMA li_api
FROM li_memory_function_owner;


REVOKE li_memory_function_owner
FROM postgres;


-- ============================================================
-- 10. RECORD MIGRATION
-- ============================================================

INSERT INTO li_memory.schema_versions (
    version,
    description
)
VALUES (
    '0.9',
    'Add separate owner authority for memory proposal confirmation'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;