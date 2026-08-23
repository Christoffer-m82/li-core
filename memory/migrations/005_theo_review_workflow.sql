BEGIN;

-- ============================================================
-- Li OS Theo Memory Review Workflow
-- Migration: 005
--
-- Purpose:
-- Create a dedicated Theo capability and controlled workflow
-- for reviewing specialist memory proposals.
--
-- Workflow:
--
-- Specialist or Li
--     proposes memory
--
-- Theo
--     reviews proposal
--
-- Theo may:
--     approve
--     reject
--     request user confirmation
--
-- Approved proposals become canonical memory.
--
-- Duplicate proposals are merged with existing canonical
-- memory rather than creating unnecessary duplicate records.
--
-- Ordinary li_memory_api access cannot approve proposals.
-- ============================================================


-- ============================================================
-- 1. CREATE THEO CAPABILITY ROLE
-- ============================================================

DO $$
BEGIN

    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'li_memory_theo'
    ) THEN

        CREATE ROLE li_memory_theo
        NOLOGIN
        NOSUPERUSER
        NOCREATEDB
        NOCREATEROLE
        NOINHERIT
        NOREPLICATION
        NOBYPASSRLS;

    END IF;

END
$$;


-- ============================================================
-- 2. THEO MUST NOT HAVE DIRECT CANONICAL TABLE ACCESS
-- ============================================================

REVOKE ALL
ON SCHEMA li_memory
FROM li_memory_theo;


REVOKE ALL PRIVILEGES
ON ALL TABLES IN SCHEMA li_memory
FROM li_memory_theo;


REVOKE ALL PRIVILEGES
ON ALL SEQUENCES IN SCHEMA li_memory
FROM li_memory_theo;


REVOKE EXECUTE
ON ALL FUNCTIONS IN SCHEMA li_memory
FROM li_memory_theo;


-- ============================================================
-- 3. ALLOW THEO TO USE CONTROLLED API SCHEMA
-- ============================================================

REVOKE ALL
ON SCHEMA li_api
FROM li_memory_theo;


GRANT USAGE
ON SCHEMA li_api
TO li_memory_theo;


-- ============================================================
-- 4. DEFAULT-DENY FUTURE API FUNCTIONS FOR THEO
-- ============================================================

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA li_api
REVOKE EXECUTE
ON FUNCTIONS
FROM li_memory_theo;


-- ============================================================
-- 5. TEMPORARY MIGRATION OWNERSHIP PERMISSIONS
-- ============================================================

GRANT li_memory_function_owner
TO postgres;


GRANT USAGE, CREATE
ON SCHEMA li_api
TO li_memory_function_owner;


-- ============================================================
-- 6. CREATE THEO REVIEW FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION li_api.review_memory_proposal(
    p_proposal_id UUID,
    p_decision TEXT,
    p_review_note TEXT DEFAULT NULL,
    p_final_truth_status TEXT DEFAULT NULL,
    p_final_temporal_status TEXT DEFAULT NULL,
    p_final_confidence NUMERIC DEFAULT NULL
)
RETURNS TABLE (
    proposal_id UUID,
    proposal_status TEXT,
    memory_id UUID,
    outcome TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;

    v_proposal li_memory.memory_write_proposals%ROWTYPE;

    v_existing_memory_id UUID;
    v_memory_id UUID;

    v_truth_status TEXT;
    v_temporal_status TEXT;
    v_sensitivity TEXT;

    v_confidence NUMERIC(4,3);

    v_source_type TEXT;
    v_source_user_id UUID;

    v_confirmed_by_user BOOLEAN;
BEGIN

    -- ========================================================
    -- VALIDATE DECISION
    -- ========================================================

    IF p_decision NOT IN (
        'approve',
        'reject',
        'needs_user_confirmation'
    ) THEN

        RAISE EXCEPTION
            'Invalid Theo review decision: %',
            p_decision;

    END IF;


    -- ========================================================
    -- VALIDATE OPTIONAL CONFIDENCE
    -- ========================================================

    IF p_final_confidence IS NOT NULL
       AND (
            p_final_confidence < 0
            OR p_final_confidence > 1
       ) THEN

        RAISE EXCEPTION
            'Confidence must be between 0 and 1';

    END IF;


    -- ========================================================
    -- FIND ACTIVE PRIMARY USER
    -- ========================================================

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


    -- ========================================================
    -- LOCK AND LOAD PROPOSAL
    -- ========================================================

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


    -- ========================================================
    -- VERIFY USER SCOPE
    -- ========================================================

    IF v_proposal.owner_user_id <> v_user_id THEN

        RAISE EXCEPTION
            'Memory proposal does not belong to active primary user';

    END IF;


    -- ========================================================
    -- VERIFY PROPOSAL CAN STILL BE REVIEWED
    -- ========================================================

    IF v_proposal.status NOT IN (
        'pending',
        'needs_user_confirmation'
    ) THEN

        RAISE EXCEPTION
            'Memory proposal has already been resolved with status: %',
            v_proposal.status;

    END IF;


    -- ========================================================
    -- REQUEST USER CONFIRMATION
    -- ========================================================

    IF p_decision = 'needs_user_confirmation' THEN

        UPDATE li_memory.memory_write_proposals

        SET
            status = 'needs_user_confirmation',
            reviewed_by_agent = 'theo',
            reviewed_at = NOW(),

            metadata =
                COALESCE(metadata, '{}'::jsonb)
                ||
                jsonb_build_object(
                    'theo_review_note',
                    p_review_note
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
            v_user_id,
            'agent',
            'theo',
            'request_memory_confirmation',
            'memory_write_proposal',
            p_proposal_id,
            'Request user confirmation before canonical memory write',
            'theo_memory_review',
            COALESCE(
                v_proposal.proposed_sensitivity,
                'personal'
            ),
            TRUE,
            jsonb_build_object(
                'review_note',
                p_review_note
            )
        );


        RETURN QUERY
        SELECT
            p_proposal_id,
            'needs_user_confirmation'::TEXT,
            NULL::UUID,
            'user_confirmation_required'::TEXT;


        RETURN;

    END IF;


    -- ========================================================
    -- REJECT PROPOSAL
    -- ========================================================

    IF p_decision = 'reject' THEN

        UPDATE li_memory.memory_write_proposals

        SET
            status = 'rejected',
            reviewed_by_agent = 'theo',
            reviewed_at = NOW(),

            metadata =
                COALESCE(metadata, '{}'::jsonb)
                ||
                jsonb_build_object(
                    'theo_review_note',
                    p_review_note
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
            v_user_id,
            'agent',
            'theo',
            'reject_memory_proposal',
            'memory_write_proposal',
            p_proposal_id,
            'Reject proposed canonical memory',
            'theo_memory_review',
            COALESCE(
                v_proposal.proposed_sensitivity,
                'personal'
            ),
            TRUE,
            jsonb_build_object(
                'review_note',
                p_review_note
            )
        );


        RETURN QUERY
        SELECT
            p_proposal_id,
            'rejected'::TEXT,
            NULL::UUID,
            'rejected'::TEXT;


        RETURN;

    END IF;


    -- ========================================================
    -- DETERMINE FINAL TRUTH STATUS
    -- ========================================================

    v_truth_status :=
        COALESCE(
            p_final_truth_status,
            v_proposal.proposed_truth_status,

            CASE
                WHEN v_proposal.proposed_class = 'inference'
                    THEN 'inferred'

                WHEN v_proposal.proposed_class = 'observation'
                    THEN 'likely'

                WHEN v_proposal.proposed_class = 'historical_fact'
                    THEN 'likely'

                WHEN v_proposal.proposed_class = 'outcome'
                    THEN 'likely'

                WHEN v_proposal.proposed_class IN (
                    'explicit_fact',
                    'explicit_preference',
                    'explicit_opinion'
                )
                    THEN 'confirmed'

                ELSE 'likely'
            END
        );


    IF v_truth_status NOT IN (
        'confirmed',
        'likely',
        'inferred',
        'disputed',
        'outdated',
        'unknown'
    ) THEN

        RAISE EXCEPTION
            'Invalid final truth status: %',
            v_truth_status;

    END IF;


    -- ========================================================
    -- DETERMINE FINAL TEMPORAL STATUS
    -- ========================================================

    v_temporal_status :=
        COALESCE(
            p_final_temporal_status,
            v_proposal.proposed_temporal_status,

            CASE
                WHEN v_proposal.proposed_class = 'historical_fact'
                    THEN 'historical'

                WHEN v_proposal.proposed_class = 'open_loop'
                    THEN 'unresolved'

                WHEN v_proposal.proposed_class = 'commitment'
                    THEN 'planned'

                WHEN v_proposal.proposed_class = 'temporary_context'
                    THEN 'temporary'

                ELSE 'current'
            END
        );


    IF v_temporal_status NOT IN (
        'current',
        'historical',
        'planned',
        'temporary',
        'unresolved'
    ) THEN

        RAISE EXCEPTION
            'Invalid final temporal status: %',
            v_temporal_status;

    END IF;


    -- ========================================================
    -- DETERMINE FINAL SENSITIVITY
    -- ========================================================

    v_sensitivity :=
        COALESCE(
            v_proposal.proposed_sensitivity,
            'personal'
        );


    IF v_sensitivity NOT IN (
        'low',
        'personal',
        'sensitive',
        'highly_sensitive'
    ) THEN

        RAISE EXCEPTION
            'Invalid proposal sensitivity: %',
            v_sensitivity;

    END IF;


    -- ========================================================
    -- DETERMINE CONFIDENCE
    -- ========================================================

    v_confidence :=
        COALESCE(
            p_final_confidence,

            CASE
                WHEN v_proposal.proposed_class = 'inference'
                    THEN 0.650

                WHEN v_proposal.proposed_class = 'observation'
                    THEN 0.750

                WHEN v_proposal.proposed_class = 'historical_fact'
                    THEN 0.800

                WHEN v_proposal.proposed_class = 'outcome'
                    THEN 0.800

                WHEN v_proposal.proposed_class IN (
                    'commitment',
                    'open_loop'
                )
                    THEN 0.900

                WHEN v_proposal.proposed_by_agent = 'li'
                     AND v_proposal.proposed_class IN (
                         'explicit_fact',
                         'explicit_preference',
                         'explicit_opinion'
                     )
                    THEN 1.000

                WHEN v_proposal.proposed_class IN (
                    'explicit_fact',
                    'explicit_preference',
                    'explicit_opinion'
                )
                    THEN 0.850

                ELSE 0.700
            END
        );


    -- ========================================================
    -- DETERMINE PROVENANCE
    -- ========================================================

    IF v_proposal.proposed_class = 'inference' THEN

        v_source_type := 'agent_inference';
        v_source_user_id := NULL;
        v_confirmed_by_user := FALSE;


    ELSIF v_proposal.proposed_by_agent = 'li'
          AND v_proposal.proposed_class IN (
              'explicit_fact',
              'explicit_preference',
              'explicit_opinion'
          ) THEN

        v_source_type := 'user_explicit';
        v_source_user_id := v_user_id;
        v_confirmed_by_user := TRUE;


    ELSE

        v_source_type := 'agent_observation';
        v_source_user_id := NULL;
        v_confirmed_by_user := FALSE;

    END IF;


    -- ========================================================
    -- DUPLICATE DETECTION
    -- ========================================================

    SELECT m.id
    INTO v_existing_memory_id

    FROM li_memory.memory_records m

    WHERE m.owner_user_id = v_user_id

      AND m.deleted_at IS NULL

      AND m.memory_class =
          v_proposal.proposed_class

      AND m.domain =
          v_proposal.proposed_domain

      AND lower(
            btrim(
                COALESCE(
                    m.value_text,
                    ''
                )
            )
          )
          =
          lower(
            btrim(
                COALESCE(
                    v_proposal.proposed_value_text,
                    ''
                )
            )
          )

    ORDER BY m.created_at DESC

    LIMIT 1;


    -- ========================================================
    -- MERGE DUPLICATE
    -- ========================================================

    IF v_existing_memory_id IS NOT NULL THEN

        UPDATE li_memory.memory_write_proposals

        SET
            status = 'merged',
            reviewed_by_agent = 'theo',
            reviewed_at = NOW(),
            resulting_memory_id = v_existing_memory_id,

            metadata =
                COALESCE(metadata, '{}'::jsonb)
                ||
                jsonb_build_object(
                    'theo_review_note',
                    p_review_note,
                    'duplicate_of',
                    v_existing_memory_id
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
            v_user_id,
            'agent',
            'theo',
            'merge_duplicate_memory_proposal',
            'memory_write_proposal',
            p_proposal_id,
            'Avoid duplicate canonical memory',
            'theo_memory_review',
            v_sensitivity,
            TRUE,
            jsonb_build_object(
                'existing_memory_id',
                v_existing_memory_id,
                'review_note',
                p_review_note
            )
        );


        RETURN QUERY
        SELECT
            p_proposal_id,
            'merged'::TEXT,
            v_existing_memory_id,
            'duplicate_existing_memory'::TEXT;


        RETURN;

    END IF;


    -- ========================================================
    -- CREATE CANONICAL MEMORY
    -- ========================================================

    INSERT INTO li_memory.memory_records (
        owner_user_id,
        memory_class,
        domain,
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
        v_proposal.proposed_class,
        v_proposal.proposed_domain,
        v_proposal.proposed_value_text,
        v_source_type,
        v_source_user_id,
        v_proposal.proposed_by_agent,
        v_proposal.source_reference,
        v_confidence,
        v_truth_status,
        v_temporal_status,
        v_sensitivity,
        FALSE,
        v_confirmed_by_user
    )
    RETURNING id
    INTO v_memory_id;


    -- ========================================================
    -- MARK PROPOSAL APPROVED
    -- ========================================================

    UPDATE li_memory.memory_write_proposals

    SET
        status = 'approved',
        reviewed_by_agent = 'theo',
        reviewed_at = NOW(),
        resulting_memory_id = v_memory_id,

        metadata =
            COALESCE(metadata, '{}'::jsonb)
            ||
            jsonb_build_object(
                'theo_review_note',
                p_review_note,
                'final_truth_status',
                v_truth_status,
                'final_temporal_status',
                v_temporal_status,
                'final_confidence',
                v_confidence
            )

    WHERE id = p_proposal_id;


    -- ========================================================
    -- AUDIT CANONICALIZATION
    -- ========================================================

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
        v_user_id,
        'agent',
        'theo',
        'approve_memory_proposal',
        'memory_record',
        v_memory_id,
        'Create canonical memory from reviewed proposal',
        'theo_memory_review',
        v_sensitivity,
        TRUE,
        jsonb_build_object(
            'proposal_id',
            p_proposal_id,
            'proposed_by_agent',
            v_proposal.proposed_by_agent,
            'review_note',
            p_review_note
        )
    );


    -- ========================================================
    -- RETURN APPROVAL RESULT
    -- ========================================================

    RETURN QUERY
    SELECT
        p_proposal_id,
        'approved'::TEXT,
        v_memory_id,
        'canonical_memory_created'::TEXT;


END;
$$;


-- ============================================================
-- 7. TRANSFER FUNCTION OWNERSHIP
-- ============================================================

ALTER FUNCTION li_api.review_memory_proposal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
OWNER TO li_memory_function_owner;


-- ============================================================
-- 8. REMOVE ALL DEFAULT FUNCTION ACCESS
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
FROM anon;


REVOKE ALL
ON FUNCTION li_api.review_memory_proposal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
FROM authenticated;


REVOKE ALL
ON FUNCTION li_api.review_memory_proposal(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT,
    NUMERIC
)
FROM service_role;


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


-- ============================================================
-- 9. GRANT REVIEW CAPABILITY ONLY TO THEO
-- ============================================================

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


-- Theo also needs to inspect the pending proposal queue.

GRANT EXECUTE
ON FUNCTION li_api.get_pending_memory_proposals(
    INTEGER
)
TO li_memory_theo;


-- ============================================================
-- 10. RECONFIRM THEO HAS NO DIRECT MEMORY ACCESS
-- ============================================================

REVOKE ALL
ON SCHEMA li_memory
FROM li_memory_theo;


REVOKE ALL PRIVILEGES
ON ALL TABLES IN SCHEMA li_memory
FROM li_memory_theo;


REVOKE ALL PRIVILEGES
ON ALL SEQUENCES IN SCHEMA li_memory
FROM li_memory_theo;


REVOKE EXECUTE
ON ALL FUNCTIONS IN SCHEMA li_memory
FROM li_memory_theo;


-- ============================================================
-- 11. REMOVE TEMPORARY FUNCTION CREATION AUTHORITY
-- ============================================================

REVOKE CREATE
ON SCHEMA li_api
FROM li_memory_function_owner;


GRANT USAGE
ON SCHEMA li_api
TO li_memory_function_owner;


-- ============================================================
-- 12. RECORD MIGRATION
-- ============================================================

INSERT INTO li_memory.schema_versions (
    version,
    description
)
VALUES (
    '0.5',
    'Add Theo memory proposal review and canonicalization workflow'
)
ON CONFLICT (version) DO NOTHING;


-- ============================================================
-- 13. REMOVE TEMPORARY POSTGRES ROLE MEMBERSHIP
-- ============================================================

REVOKE li_memory_function_owner
FROM postgres;


-- ============================================================
-- 14. FINAL SECURITY STATE
-- ============================================================

-- li_memory_api:
--
-- Can create memory proposals.
-- Can directly store only permitted low-risk explicit memory.
-- Can retrieve canonical memory through approved functions.
-- Cannot directly access canonical tables.
-- Cannot approve or reject memory proposals.
--
--
-- li_memory_theo:
--
-- Can inspect the pending proposal queue.
-- Can review proposals through review_memory_proposal().
-- Cannot directly access canonical memory tables.
--
--
-- li_memory_function_owner:
--
-- Owns controlled SECURITY DEFINER functions.
-- Cannot log in.
--
--
-- Theo review decisions:
--
-- approve
-- reject
-- needs_user_confirmation
--
--
-- Approved proposals become canonical memory.
--
-- Exact duplicate proposals are merged rather than creating
-- duplicate canonical records.
--
-- All review decisions create audit history.


COMMIT;
