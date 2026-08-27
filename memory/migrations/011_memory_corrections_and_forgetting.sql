BEGIN;

-- Li OS Memory Corrections and Forgetting
-- Migration 011

-- Adds controlled correction and forgetting of canonical memory.
-- Existing schema fields are used rather than adding new columns.

GRANT li_memory_function_owner TO postgres;

GRANT USAGE, CREATE
ON SCHEMA li_api
TO li_memory_function_owner;

SET LOCAL ROLE li_memory_function_owner;

-- Correct an existing low-risk explicit memory.
-- The old memory is preserved as historical/outdated.
-- The replacement becomes the current canonical memory.

CREATE OR REPLACE FUNCTION li_api.correct_explicit_memory(
    p_memory_id UUID,
    p_new_value_text TEXT,
    p_new_domain TEXT DEFAULT NULL,
    p_new_title TEXT DEFAULT NULL,
    p_source_reference TEXT DEFAULT NULL
)
RETURNS TABLE (
    previous_memory_id UUID,
    memory_id UUID,
    outcome TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_target li_memory.memory_records%ROWTYPE;
    v_existing_memory_id UUID;
    v_replacement_memory_id UUID;
    v_domain TEXT;
    v_title TEXT;
    v_now TIMESTAMPTZ := NOW();
    v_outcome TEXT;
BEGIN

    IF p_memory_id IS NULL THEN
        RAISE EXCEPTION 'Memory ID is required';
    END IF;

    IF p_new_value_text IS NULL
       OR btrim(p_new_value_text) = '' THEN
        RAISE EXCEPTION 'Replacement memory value is required';
    END IF;

    SELECT id
    INTO v_user_id
    FROM li_memory.users
    WHERE user_key = 'christoffer'
      AND status = 'active'
    LIMIT 1;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Active primary user not found';
    END IF;

    SELECT m.*
    INTO v_target
    FROM li_memory.memory_records m
    WHERE m.id = p_memory_id
      AND m.owner_user_id = v_user_id
      AND m.deleted_at IS NULL
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Active memory not found';
    END IF;

    IF v_target.memory_class NOT IN (
        'explicit_fact',
        'explicit_preference',
        'explicit_opinion'
    ) THEN
        RAISE EXCEPTION
            'Direct correction is not allowed for memory class: %',
            v_target.memory_class;
    END IF;

    IF v_target.sensitivity NOT IN (
        'low',
        'personal'
    ) THEN
        RAISE EXCEPTION
            'Sensitivity % requires Theo review for correction',
            v_target.sensitivity;
    END IF;

    IF v_target.temporal_status <> 'current'
       OR v_target.truth_status = 'outdated' THEN
        RAISE EXCEPTION
            'Only active current explicit memory can be directly corrected';
    END IF;

    v_domain := COALESCE(
        NULLIF(btrim(p_new_domain), ''),
        v_target.domain
    );

    v_title :=
        CASE
            WHEN p_new_title IS NULL
                THEN v_target.title
            ELSE NULLIF(btrim(p_new_title), '')
        END;

    -- If the new memory says exactly the same thing,
    -- simply reconfirm the existing record.

    IF lower(btrim(COALESCE(v_target.value_text, '')))
       = lower(btrim(p_new_value_text))
       AND lower(btrim(v_target.domain))
       = lower(btrim(v_domain)) THEN

        UPDATE li_memory.memory_records
        SET
            title = v_title,
            source_reference = COALESCE(
                NULLIF(btrim(p_source_reference), ''),
                source_reference
            ),
            confidence = 1.000,
            truth_status = 'confirmed',
            temporal_status = 'current',
            confirmed_by_user = TRUE,
            updated_at = v_now
        WHERE id = v_target.id;

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
            'confirm_existing_explicit_memory',
            'memory_record',
            v_target.id,
            'User reconfirmed an existing explicit memory',
            'explicit_user_memory_correction',
            v_target.sensitivity,
            TRUE,
            jsonb_build_object(
                'outcome',
                'unchanged'
            )
        );

        RETURN QUERY
        SELECT
            v_target.id,
            v_target.id,
            'unchanged'::TEXT;

        RETURN;
    END IF;

    -- Check whether the corrected value already exists as another
    -- current canonical memory.

    SELECT m.id
    INTO v_existing_memory_id
    FROM li_memory.memory_records m
    WHERE m.owner_user_id = v_user_id
      AND m.id <> v_target.id
      AND m.deleted_at IS NULL
      AND m.memory_class = v_target.memory_class
      AND lower(btrim(m.domain)) = lower(btrim(v_domain))
      AND lower(btrim(COALESCE(m.value_text, '')))
          = lower(btrim(p_new_value_text))
      AND m.temporal_status = 'current'
      AND m.truth_status <> 'outdated'
    ORDER BY
        m.confirmed_by_user DESC,
        m.confidence DESC,
        m.updated_at DESC
    LIMIT 1
    FOR UPDATE;

    IF v_existing_memory_id IS NOT NULL THEN

        IF EXISTS (
            SELECT 1
            FROM li_memory.memory_records m
            WHERE m.id = v_existing_memory_id
              AND m.sensitivity NOT IN (
                  'low',
                  'personal'
              )
        ) THEN
            RAISE EXCEPTION
                'Matching replacement memory requires Theo review';
        END IF;

        UPDATE li_memory.memory_records m
        SET
            sensitivity =
                CASE
                    WHEN m.sensitivity = 'personal'
                         OR v_target.sensitivity = 'personal'
                        THEN 'personal'
                    ELSE 'low'
                END,
            private_to_li =
                m.private_to_li
                OR v_target.private_to_li,
            title = COALESCE(
                m.title,
                v_title
            ),
            confidence = 1.000,
            truth_status = 'confirmed',
            temporal_status = 'current',
            confirmed_by_user = TRUE,
            supersedes_memory_id = COALESCE(
                m.supersedes_memory_id,
                v_target.id
            ),
            updated_at = v_now
        WHERE m.id = v_existing_memory_id;

        v_replacement_memory_id := v_existing_memory_id;
        v_outcome := 'reused_existing_memory';

    ELSE

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
            confirmed_by_user,
            valid_from,
            supersedes_memory_id
        )
        VALUES (
            v_user_id,
            v_target.memory_class,
            v_domain,
            v_title,
            btrim(p_new_value_text),
            'user_explicit',
            v_user_id,
            'li',
            NULLIF(btrim(p_source_reference), ''),
            1.000,
            'confirmed',
            'current',
            v_target.sensitivity,
            v_target.private_to_li,
            TRUE,
            v_now,
            v_target.id
        )
        RETURNING id
        INTO v_replacement_memory_id;

        v_outcome := 'created_replacement';

    END IF;

    -- Preserve the old memory as historical information.

    UPDATE li_memory.memory_records
    SET
        truth_status = 'outdated',
        temporal_status = 'historical',
        valid_until = v_now,
        updated_at = v_now
    WHERE id = v_target.id;

    -- Record an explicit relationship between the replacement
    -- and the old memory.

    INSERT INTO li_memory.memory_relations (
        source_memory_id,
        target_memory_id,
        relation_type,
        metadata
    )
    VALUES (
        v_replacement_memory_id,
        v_target.id,
        'supersedes',
        jsonb_build_object(
            'reason',
            'explicit_user_correction'
        )
    )
    ON CONFLICT (
        source_memory_id,
        target_memory_id,
        relation_type
    )
    DO NOTHING;

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
        'correct_explicit_memory',
        'memory_record',
        v_replacement_memory_id,
        'Replace an explicit memory after user correction',
        'explicit_user_memory_correction',
        v_target.sensitivity,
        TRUE,
        jsonb_build_object(
            'previous_memory_id',
            v_target.id,
            'replacement_memory_id',
            v_replacement_memory_id,
            'outcome',
            v_outcome
        )
    );

    RETURN QUERY
    SELECT
        v_target.id,
        v_replacement_memory_id,
        v_outcome;

END;
$$;


-- Forget a canonical memory after an explicit user request.
-- The live memory content is tombstoned so normal recall can no
-- longer return it.

CREATE OR REPLACE FUNCTION li_api.forget_memory(
    p_memory_id UUID,
    p_source_reference TEXT DEFAULT NULL
)
RETURNS TABLE (
    memory_id UUID,
    outcome TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_target li_memory.memory_records%ROWTYPE;
    v_now TIMESTAMPTZ := NOW();
BEGIN

    IF p_memory_id IS NULL THEN
        RAISE EXCEPTION 'Memory ID is required';
    END IF;

    SELECT id
    INTO v_user_id
    FROM li_memory.users
    WHERE user_key = 'christoffer'
      AND status = 'active'
    LIMIT 1;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Active primary user not found';
    END IF;

    SELECT m.*
    INTO v_target
    FROM li_memory.memory_records m
    WHERE m.id = p_memory_id
      AND m.owner_user_id = v_user_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Memory not found';
    END IF;

    IF v_target.deleted_at IS NOT NULL THEN

        RETURN QUERY
        SELECT
            v_target.id,
            'already_forgotten'::TEXT;

        RETURN;
    END IF;

    DELETE FROM li_memory.memory_relations
    WHERE source_memory_id = v_target.id
       OR target_memory_id = v_target.id;

    UPDATE li_memory.memory_records
    SET
        supersedes_memory_id = NULL,
        updated_at = v_now
    WHERE owner_user_id = v_user_id
      AND supersedes_memory_id = v_target.id;

    UPDATE li_memory.memory_records
    SET
        memory_key = NULL,
        domain = 'forgotten',
        title = NULL,
        value_text = '[forgotten by user]',
        value_json = NULL,
        source_reference = NULL,
        confidence = 0.000,
        truth_status = 'outdated',
        temporal_status = 'historical',
        private_to_li = TRUE,
        confirmed_by_user = FALSE,
        valid_from = NULL,
        valid_until = v_now,
        review_after = NULL,
        supersedes_memory_id = NULL,
        deleted_at = v_now,
        updated_at = v_now,
        metadata = jsonb_build_object(
            'forgotten_by_user',
            TRUE,
            'forgotten_at',
            v_now
        )
    WHERE id = v_target.id;

    -- Do not copy forgotten content into the audit log.

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
        'forget_memory',
        'memory_record',
        v_target.id,
        'Remove user-requested memory content from active canonical memory',
        'explicit_user_forget_request',
        v_target.sensitivity,
        TRUE,
        jsonb_build_object(
            'content_tombstoned',
            TRUE,
            'source_reference',
            NULLIF(btrim(p_source_reference), '')
        )
    );

    RETURN QUERY
    SELECT
        v_target.id,
        'forgotten'::TEXT;

END;
$$;


-- Replace normal recall so superseded/outdated memories are not
-- returned as though they were current facts.

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
        RAISE EXCEPTION 'Search query is required';
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
        RAISE EXCEPTION 'Active primary user not found';
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
      AND m.truth_status <> 'outdated'
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


RESET ROLE;


-- Restrict correction function.

REVOKE ALL
ON FUNCTION li_api.correct_explicit_memory(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT
)
FROM PUBLIC, anon, authenticated, service_role;

REVOKE ALL
ON FUNCTION li_api.correct_explicit_memory(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT
)
FROM li_memory_theo, li_memory_owner_confirmation;

GRANT EXECUTE
ON FUNCTION li_api.correct_explicit_memory(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT
)
TO li_memory_api;


-- Restrict forgetting function.

REVOKE ALL
ON FUNCTION li_api.forget_memory(
    UUID,
    TEXT
)
FROM PUBLIC, anon, authenticated, service_role;

REVOKE ALL
ON FUNCTION li_api.forget_memory(
    UUID,
    TEXT
)
FROM li_memory_theo, li_memory_owner_confirmation;

GRANT EXECUTE
ON FUNCTION li_api.forget_memory(
    UUID,
    TEXT
)
TO li_memory_api;


-- Reconfirm recall access.

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


-- Li runtime still receives no direct access to private tables.

REVOKE ALL PRIVILEGES
ON ALL TABLES IN SCHEMA li_memory
FROM li_memory_api;

REVOKE ALL PRIVILEGES
ON ALL SEQUENCES IN SCHEMA li_memory
FROM li_memory_api;

REVOKE EXECUTE
ON ALL FUNCTIONS IN SCHEMA li_memory
FROM li_memory_api;

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
ON FUNCTION li_api.correct_explicit_memory(
    UUID,
    TEXT,
    TEXT,
    TEXT,
    TEXT
)
TO li_memory_api;

GRANT EXECUTE
ON FUNCTION li_api.forget_memory(
    UUID,
    TEXT
)
TO li_memory_api;


REVOKE CREATE
ON SCHEMA li_api
FROM li_memory_function_owner;

GRANT USAGE
ON SCHEMA li_api
TO li_memory_function_owner;

REVOKE li_memory_function_owner
FROM postgres;


INSERT INTO li_memory.schema_versions (
    version,
    description
)
VALUES (
    '0.11',
    'Add governed memory correction, forgetting, and outdated-memory recall filtering'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;


