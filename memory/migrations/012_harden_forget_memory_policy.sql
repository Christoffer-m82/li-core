BEGIN;

-- Li OS Forgetting Policy Hardening
-- Migration 012
--
-- Enforce the Li runtime forgetting policy at the database boundary.
-- Direct forgetting is limited to low/personal memory. More sensitive
-- memory must remain unchanged until a governed Theo/owner path exists.

GRANT li_memory_function_owner TO postgres;

GRANT USAGE, CREATE
ON SCHEMA li_api
TO li_memory_function_owner;

SET LOCAL ROLE li_memory_function_owner;

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

    -- Check sensitivity before either returning success or mutating state.
    -- This fails closed even if a sensitive record was already tombstoned.

    IF v_target.sensitivity NOT IN (
        'low',
        'personal'
    ) THEN
        RAISE EXCEPTION
            'Sensitivity % requires Theo review for forgetting',
            v_target.sensitivity;
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

RESET ROLE;

-- Keep the SECURITY DEFINER function restricted to the Li memory API role.

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

-- Li runtime receives no direct access to private memory objects.

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
    '0.12',
    'Restrict direct Li runtime forgetting to low and personal memory'
)
ON CONFLICT (version) DO NOTHING;

COMMIT;
