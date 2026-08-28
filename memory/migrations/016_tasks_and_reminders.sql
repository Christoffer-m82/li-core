BEGIN;

-- Commitments are operational state, deliberately separate from canonical memory.
CREATE SCHEMA IF NOT EXISTS li_tasks;
REVOKE ALL ON SCHEMA li_tasks FROM PUBLIC, anon, authenticated, service_role,
    li_memory_api, li_backend_runtime, li_memory_theo, li_memory_owner_confirmation;

CREATE TABLE li_tasks.tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
    title TEXT NOT NULL CHECK (btrim(title) <> '' AND length(title) <= 500),
    notes TEXT CHECK (notes IS NULL OR length(notes) <= 4000),
    due_at TIMESTAMPTZ,
    timezone TEXT CHECK (timezone IS NULL OR length(timezone) <= 100),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'completed', 'cancelled')),
    idempotency_key TEXT NOT NULL CHECK (
        btrim(idempotency_key) <> '' AND length(idempotency_key) <= 200
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    UNIQUE (owner_user_id, idempotency_key)
);

CREATE TABLE li_tasks.audit_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES li_tasks.tasks(id) ON DELETE CASCADE,
    owner_user_id UUID NOT NULL REFERENCES li_memory.users(id),
    operation TEXT NOT NULL CHECK (operation IN ('created', 'completed', 'cancelled')),
    previous_status TEXT,
    resulting_status TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_owner_open_due
    ON li_tasks.tasks(owner_user_id, due_at NULLS LAST, created_at) WHERE status = 'open';
CREATE INDEX idx_task_audit_task_time ON li_tasks.audit_log(task_id, occurred_at);

ALTER TABLE li_tasks.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_tasks.tasks FORCE ROW LEVEL SECURITY;
ALTER TABLE li_tasks.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE li_tasks.audit_log FORCE ROW LEVEL SECURITY;

CREATE POLICY li_tasks_function_owner_access ON li_tasks.tasks
FOR ALL TO li_memory_function_owner USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY li_task_audit_function_owner_access ON li_tasks.audit_log
FOR ALL TO li_memory_function_owner USING (TRUE) WITH CHECK (TRUE);

GRANT USAGE ON SCHEMA li_tasks TO li_memory_function_owner;
GRANT SELECT, INSERT, UPDATE ON li_tasks.tasks TO li_memory_function_owner;
GRANT SELECT, INSERT, DELETE ON li_tasks.audit_log TO li_memory_function_owner;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA li_tasks TO li_memory_function_owner;

GRANT li_memory_function_owner TO postgres;
GRANT USAGE, CREATE ON SCHEMA li_api TO li_memory_function_owner;
SET LOCAL ROLE li_memory_function_owner;

CREATE FUNCTION li_api.create_task(
    p_title TEXT, p_notes TEXT, p_due_at TIMESTAMPTZ, p_timezone TEXT,
    p_idempotency_key TEXT
) RETURNS TABLE (
    task_id UUID, title TEXT, notes TEXT, due_at TIMESTAMPTZ, timezone TEXT,
    status TEXT, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ, cancelled_at TIMESTAMPTZ
) LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_tasks, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user_id UUID; v_task_id UUID;
BEGIN
    SELECT u.id INTO v_user_id FROM li_memory.users AS u
    WHERE u.user_key = 'christoffer' AND u.status = 'active' LIMIT 1;
    IF v_user_id IS NULL THEN RAISE EXCEPTION 'Active primary user not found'; END IF;
    INSERT INTO li_tasks.tasks(owner_user_id, title, notes, due_at, timezone, idempotency_key)
    VALUES (v_user_id, btrim(p_title), NULLIF(btrim(p_notes), ''), p_due_at,
            NULLIF(btrim(p_timezone), ''), btrim(p_idempotency_key))
    ON CONFLICT (owner_user_id, idempotency_key) DO NOTHING RETURNING id INTO v_task_id;
    IF v_task_id IS NOT NULL THEN
        INSERT INTO li_tasks.audit_log(task_id, owner_user_id, operation, resulting_status)
        VALUES (v_task_id, v_user_id, 'created', 'open');
    ELSE
        SELECT id INTO v_task_id FROM li_tasks.tasks
        WHERE owner_user_id = v_user_id AND idempotency_key = btrim(p_idempotency_key);
    END IF;
    RETURN QUERY SELECT t.id, t.title, t.notes, t.due_at, t.timezone, t.status,
        t.created_at, t.updated_at, t.completed_at, t.cancelled_at
        FROM li_tasks.tasks t WHERE t.id = v_task_id AND t.owner_user_id = v_user_id;
END; $$;

CREATE FUNCTION li_api.list_open_tasks(
    p_due_before TIMESTAMPTZ DEFAULT NULL, p_include_undated BOOLEAN DEFAULT TRUE,
    p_limit INTEGER DEFAULT 50
) RETURNS TABLE (
    task_id UUID, title TEXT, notes TEXT, due_at TIMESTAMPTZ, timezone TEXT,
    status TEXT, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ, cancelled_at TIMESTAMPTZ
) LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_tasks, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user_id UUID;
BEGIN
    SELECT u.id INTO v_user_id FROM li_memory.users AS u
    WHERE u.user_key = 'christoffer' AND u.status = 'active' LIMIT 1;
    RETURN QUERY SELECT t.id, t.title, t.notes, t.due_at, t.timezone, t.status,
        t.created_at, t.updated_at, t.completed_at, t.cancelled_at
    FROM li_tasks.tasks t WHERE t.owner_user_id = v_user_id AND t.status = 'open'
      AND (p_due_before IS NULL OR t.due_at <= p_due_before OR (p_include_undated AND t.due_at IS NULL))
      AND (p_include_undated OR t.due_at IS NOT NULL)
    ORDER BY t.due_at NULLS LAST, t.created_at
    LIMIT LEAST(GREATEST(COALESCE(p_limit, 50), 1), 100);
END; $$;

CREATE FUNCTION li_api.set_task_status(p_task_id UUID, p_status TEXT)
RETURNS TABLE (
    task_id UUID, title TEXT, notes TEXT, due_at TIMESTAMPTZ, timezone TEXT,
    status TEXT, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ, cancelled_at TIMESTAMPTZ
) LANGUAGE plpgsql SECURITY DEFINER
SET search_path = li_tasks, li_memory, pg_catalog, pg_temp AS $$
DECLARE v_user_id UUID; v_previous TEXT;
BEGIN
    IF p_status NOT IN ('completed', 'cancelled') THEN RAISE EXCEPTION 'Invalid task status'; END IF;
    SELECT u.id INTO v_user_id FROM li_memory.users AS u
    WHERE u.user_key = 'christoffer' AND u.status = 'active' LIMIT 1;
    SELECT t.status INTO v_previous FROM li_tasks.tasks t
    WHERE t.id = p_task_id AND t.owner_user_id = v_user_id FOR UPDATE;
    IF v_previous IS NULL THEN RAISE EXCEPTION 'Task not found'; END IF;
    IF v_previous <> p_status THEN
        IF v_previous <> 'open' THEN RAISE EXCEPTION 'Task is already closed'; END IF;
        UPDATE li_tasks.tasks t SET status = p_status, updated_at = NOW(),
            completed_at = CASE WHEN p_status = 'completed' THEN NOW() ELSE NULL END,
            cancelled_at = CASE WHEN p_status = 'cancelled' THEN NOW() ELSE NULL END
        WHERE t.id = p_task_id;
        INSERT INTO li_tasks.audit_log(task_id, owner_user_id, operation, previous_status, resulting_status)
        VALUES (p_task_id, v_user_id, p_status, v_previous, p_status);
    END IF;
    RETURN QUERY SELECT t.id, t.title, t.notes, t.due_at, t.timezone, t.status,
        t.created_at, t.updated_at, t.completed_at, t.cancelled_at
        FROM li_tasks.tasks t WHERE t.id = p_task_id AND t.owner_user_id = v_user_id;
END; $$;

CREATE FUNCTION li_api.complete_task(p_task_id UUID) RETURNS TABLE (
    task_id UUID, title TEXT, notes TEXT, due_at TIMESTAMPTZ, timezone TEXT,
    status TEXT, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ, cancelled_at TIMESTAMPTZ
) LANGUAGE sql SECURITY DEFINER SET search_path = li_api, pg_catalog, pg_temp
AS $$ SELECT * FROM li_api.set_task_status(p_task_id, 'completed') $$;

CREATE FUNCTION li_api.cancel_task(p_task_id UUID) RETURNS TABLE (
    task_id UUID, title TEXT, notes TEXT, due_at TIMESTAMPTZ, timezone TEXT,
    status TEXT, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ, cancelled_at TIMESTAMPTZ
) LANGUAGE sql SECURITY DEFINER SET search_path = li_api, pg_catalog, pg_temp
AS $$ SELECT * FROM li_api.set_task_status(p_task_id, 'cancelled') $$;

RESET ROLE;

REVOKE ALL ON FUNCTION li_api.create_task(TEXT, TEXT, TIMESTAMPTZ, TEXT, TEXT)
    FROM PUBLIC, anon, authenticated, service_role, li_memory_theo, li_memory_owner_confirmation;
REVOKE ALL ON FUNCTION li_api.list_open_tasks(TIMESTAMPTZ, BOOLEAN, INTEGER)
    FROM PUBLIC, anon, authenticated, service_role, li_memory_theo, li_memory_owner_confirmation;
REVOKE ALL ON FUNCTION li_api.set_task_status(UUID, TEXT)
    FROM PUBLIC, anon, authenticated, service_role, li_memory_api, li_backend_runtime,
    li_memory_theo, li_memory_owner_confirmation;
REVOKE ALL ON FUNCTION li_api.complete_task(UUID)
    FROM PUBLIC, anon, authenticated, service_role, li_memory_theo, li_memory_owner_confirmation;
REVOKE ALL ON FUNCTION li_api.cancel_task(UUID)
    FROM PUBLIC, anon, authenticated, service_role, li_memory_theo, li_memory_owner_confirmation;
GRANT EXECUTE ON FUNCTION li_api.create_task(TEXT, TEXT, TIMESTAMPTZ, TEXT, TEXT) TO li_memory_api;
GRANT EXECUTE ON FUNCTION li_api.list_open_tasks(TIMESTAMPTZ, BOOLEAN, INTEGER) TO li_memory_api;
GRANT EXECUTE ON FUNCTION li_api.complete_task(UUID) TO li_memory_api;
GRANT EXECUTE ON FUNCTION li_api.cancel_task(UUID) TO li_memory_api;

REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA li_tasks FROM li_backend_runtime,
    li_memory_api, li_memory_theo, li_memory_owner_confirmation;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA li_tasks FROM li_backend_runtime,
    li_memory_api, li_memory_theo, li_memory_owner_confirmation;
REVOKE CREATE ON SCHEMA li_api FROM li_memory_function_owner;
REVOKE li_memory_function_owner FROM postgres;

INSERT INTO li_memory.schema_versions(version, description)
VALUES ('0.16', 'Add isolated durable reminders and tasks') ON CONFLICT (version) DO NOTHING;

COMMIT;
