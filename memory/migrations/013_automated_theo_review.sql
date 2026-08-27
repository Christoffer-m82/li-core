BEGIN;

-- Theo receives relevant canonical context only through this audited,
-- SECURITY DEFINER function. The runtime role retains no table access.
CREATE OR REPLACE FUNCTION li_api.recall_memory_for_theo(
    p_query TEXT,
    p_domains TEXT[] DEFAULT NULL,
    p_limit INTEGER DEFAULT 8
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
    confidence NUMERIC,
    confirmed_by_user BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_limit INTEGER;
BEGIN
    IF p_query IS NULL OR btrim(p_query) = '' THEN
        RAISE EXCEPTION 'Search query is required';
    END IF;

    v_limit := LEAST(GREATEST(COALESCE(p_limit, 8), 1), 20);

    SELECT id INTO v_user_id
    FROM li_memory.users
    WHERE user_key = 'christoffer' AND status = 'active'
    LIMIT 1;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Active primary user not found';
    END IF;

    INSERT INTO li_memory.memory_audit_log (
        owner_user_id, actor_type, actor_id, action, resource_type,
        purpose, permission_basis, sensitivity, success, metadata
    ) VALUES (
        v_user_id, 'agent', 'theo', 'recall_memory', 'memory_search',
        'Retrieve canonical context for proposal review',
        'theo_memory_review', 'personal', TRUE,
        jsonb_build_object('domains', p_domains, 'limit', v_limit)
    );

    RETURN QUERY
    WITH search_query AS (
        SELECT plainto_tsquery('simple', btrim(p_query)) AS ts_query
    )
    SELECT
        m.id, m.memory_class, m.domain, m.title, m.value_text,
        m.truth_status, m.temporal_status, m.sensitivity,
        m.confidence, m.confirmed_by_user
    FROM li_memory.memory_records m
    CROSS JOIN search_query sq
    WHERE m.owner_user_id = v_user_id
      AND m.deleted_at IS NULL
      AND (p_domains IS NULL OR m.domain = ANY(p_domains))
      AND (
          to_tsvector('simple', COALESCE(m.title, '') || ' ' ||
              COALESCE(m.value_text, '')) @@ sq.ts_query
          OR COALESCE(m.title, '') ILIKE '%' || btrim(p_query) || '%'
          OR COALESCE(m.value_text, '') ILIKE '%' || btrim(p_query) || '%'
      )
    ORDER BY m.confirmed_by_user DESC, m.confidence DESC, m.updated_at DESC
    LIMIT v_limit;
END;
$$;

ALTER FUNCTION li_api.recall_memory_for_theo(TEXT, TEXT[], INTEGER)
OWNER TO li_memory_function_owner;

REVOKE ALL
ON FUNCTION li_api.recall_memory_for_theo(TEXT, TEXT[], INTEGER)
FROM PUBLIC, anon, authenticated, service_role, li_memory_api,
     li_memory_owner_confirmation;

GRANT EXECUTE
ON FUNCTION li_api.recall_memory_for_theo(TEXT, TEXT[], INTEGER)
TO li_memory_theo;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA li_memory FROM li_memory_theo;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA li_memory FROM li_memory_theo;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA li_memory FROM li_memory_theo;

INSERT INTO li_memory.schema_versions (version, description)
VALUES ('0.13', 'Add automated Theo memory review context access')
ON CONFLICT (version) DO NOTHING;

COMMIT;
