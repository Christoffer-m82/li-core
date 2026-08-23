BEGIN;

-- ============================================================
-- Li OS Explicit Memory Deduplication
-- Migration: 007
--
-- Purpose:
-- Prevent repeated identical explicit memories from creating
-- duplicate canonical records.
--
-- Exact duplicates are identified using:
--
-- owner
-- memory class
-- normalized domain
-- normalized memory text
-- temporal status
--
-- This is exact/normalized deduplication only.
-- Semantic similarity will be handled separately by Theo later.
-- ============================================================


-- ============================================================
-- 1. DATABASE-LEVEL DUPLICATE PROTECTION
-- ============================================================

CREATE UNIQUE INDEX IF NOT EXISTS
    uq_memory_records_active_explicit_value
ON li_memory.memory_records (
    owner_user_id,
    memory_class,
    lower(btrim(domain)),
    lower(btrim(value_text)),
    temporal_status
)
WHERE deleted_at IS NULL
  AND value_text IS NOT NULL
  AND memory_class IN (
      'explicit_fact',
      'explicit_preference',
      'explicit_opinion'
  );


-- ============================================================
-- 2. TEMPORARY MIGRATION ROLE ACCESS
-- ============================================================

GRANT li_memory_function_owner
TO postgres;


GRANT USAGE, CREATE
ON SCHEMA li_api
TO li_memory_function_owner;


-- ============================================================
-- 3. REPLACE DIRECT EXPLICIT MEMORY FUNCTION
-- ============================================================

SET LOCAL ROLE li_memory_function_owner;


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
    v_created BOOLEAN := FALSE;
BEGIN

    -- ========================================================
    -- VALIDATE MEMORY CLASS
    -- ========================================================

    IF p_memory_class NOT IN (
        'explicit_fact',
        'explicit_preference',
        'explicit_opinion'
    ) THEN

        RAISE EXCEPTION
            'Direct memory write is not allowed for memory class: %',
            p_memory_class;

    END IF;


    -- ========================================================
    -- VALIDATE DOMAIN
    -- ========================================================

    IF p_domain IS NULL
       OR btrim(p_domain) = '' THEN

        RAISE EXCEPTION
            'Memory domain is required';

    END IF;


    -- ========================================================
    -- VALIDATE VALUE
    -- ========================================================

    IF p_value_text IS NULL
       OR btrim(p_value_text) = '' THEN

        RAISE EXCEPTION
            'Memory value is required';

    END IF;


    -- ========================================================
    -- VALIDATE SENSITIVITY
    -- ========================================================

    IF p_sensitivity NOT IN (
        'low',
        'personal'
    ) THEN

        RAISE EXCEPTION
            'Sensitivity % requires Theo review',
            p_sensitivity;

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
    -- ATTEMPT CANONICAL INSERT
    -- ========================================================

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
    ON CONFLICT DO NOTHING
    RETURNING id
    INTO v_memory_id;


    -- ========================================================
    -- NEW MEMORY CREATED
    -- ========================================================

    IF v_memory_id IS NOT NULL THEN

        v_created := TRUE;

    ELSE

        -- ====================================================
        -- EXISTING EXACT MEMORY
        -- ====================================================

        SELECT m.id
        INTO v_memory_id

        FROM li_memory.memory_records m

        WHERE m.owner_user_id = v_user_id

          AND m.deleted_at IS NULL

          AND m.memory_class = p_memory_class

          AND lower(btrim(m.domain))
              =
              lower(btrim(p_domain))

          AND lower(btrim(m.value_text))
              =
              lower(btrim(p_value_text))

          AND m.temporal_status = 'current'

        ORDER BY m.created_at DESC

        LIMIT 1;


        IF v_memory_id IS NULL THEN

            RAISE EXCEPTION
                'Duplicate protection triggered but existing memory could not be located';

        END IF;


        -- ====================================================
        -- PRIVACY MAY INCREASE, NEVER DECREASE
        -- ====================================================

        UPDATE li_memory.memory_records

        SET
            sensitivity =
                CASE
                    WHEN sensitivity = 'personal'
                         OR p_sensitivity = 'personal'
                        THEN 'personal'
                    ELSE 'low'
                END,

            private_to_li =
                private_to_li
                OR p_private_to_li,

            title =
                COALESCE(
                    title,
                    NULLIF(btrim(p_title), '')
                )

        WHERE id = v_memory_id;

    END IF;


    -- ========================================================
    -- AUDIT
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
        'li',

        CASE
            WHEN v_created
                THEN 'create_explicit_memory'
            ELSE 'reuse_existing_explicit_memory'
        END,

        'memory_record',
        v_memory_id,

        CASE
            WHEN v_created
                THEN 'Store explicit user-provided memory'
            ELSE 'Avoid duplicate explicit canonical memory'
        END,

        'li_direct_low_risk_explicit_memory',

        p_sensitivity,

        TRUE,

        jsonb_build_object(
            'new_memory_created',
            v_created
        )
    );


    RETURN v_memory_id;

END;
$$;


RESET ROLE;


-- ============================================================
-- 4. RECONFIRM FUNCTION SECURITY
-- ============================================================

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
FROM PUBLIC;


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
FROM anon;


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
FROM authenticated;


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
FROM service_role;


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
-- 5. REMOVE TEMPORARY MIGRATION ACCESS
-- ============================================================

REVOKE CREATE
ON SCHEMA li_api
FROM li_memory_function_owner;


REVOKE li_memory_function_owner
FROM postgres;


-- ============================================================
-- 6. RECORD MIGRATION
-- ============================================================

INSERT INTO li_memory.schema_versions (
    version,
    description
)
VALUES (
    '0.7',
    'Add exact duplicate protection for explicit canonical memory'
)
ON CONFLICT (version) DO NOTHING;


-- ============================================================
-- 7. FINAL BEHAVIOR
-- ============================================================

-- First request:
--
-- "Remember X."
--
-- Result:
-- New canonical memory.
--
--
-- Repeated identical request:
--
-- "Remember X."
--
-- Result:
-- Existing canonical memory returned.
-- No duplicate record created.
--
--
-- If the repeated request asks for stronger privacy:
--
-- Existing memory privacy may become stricter.
-- Privacy is never silently reduced.
--
--
-- Semantic duplicates such as:
--
-- "I really like boutique hotels."
--
-- and:
--
-- "Boutique hotels are my preference."
--
-- are not considered exact duplicates by this migration.
--
-- Theo will later handle semantic consolidation.


COMMIT;