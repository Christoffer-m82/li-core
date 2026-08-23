BEGIN;

-- ============================================================
-- Li OS Backend Runtime Role
-- Migration: 006
--
-- Purpose:
-- Create the restricted PostgreSQL login used by the Li OS
-- backend application.
--
-- Security model:
--
-- Backend runtime login
--     ->
-- li_memory_api capability
--     ->
-- approved li_api functions
--     ->
-- SECURITY DEFINER function owner
--     ->
-- canonical li_memory tables
--
-- The backend runtime must never operate as postgres.
-- ============================================================


-- ============================================================
-- 1. CREATE BACKEND RUNTIME LOGIN
-- ============================================================

DO $$
BEGIN

    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'li_backend_runtime'
    ) THEN

        CREATE ROLE li_backend_runtime
        LOGIN
        INHERIT
        NOSUPERUSER
        NOCREATEDB
        NOCREATEROLE
        NOREPLICATION
        NOBYPASSRLS
        CONNECTION LIMIT 10
        PASSWORD NULL;

    END IF;

END
$$;


-- ============================================================
-- 2. REMOVE UNNECESSARY DIRECT ACCESS
-- ============================================================

REVOKE ALL
ON SCHEMA li_memory
FROM li_backend_runtime;


REVOKE ALL PRIVILEGES
ON ALL TABLES IN SCHEMA li_memory
FROM li_backend_runtime;


REVOKE ALL PRIVILEGES
ON ALL SEQUENCES IN SCHEMA li_memory
FROM li_backend_runtime;


REVOKE EXECUTE
ON ALL FUNCTIONS IN SCHEMA li_memory
FROM li_backend_runtime;


-- ============================================================
-- 3. REMOVE DIRECT LI_API PRIVILEGES FIRST
-- ============================================================

-- The runtime should receive its API capability through
-- li_memory_api rather than through ad-hoc individual grants.

REVOKE ALL
ON SCHEMA li_api
FROM li_backend_runtime;


-- ============================================================
-- 4. GRANT ONLY THE MEMORY API CAPABILITY
-- ============================================================

GRANT li_memory_api
TO li_backend_runtime;


-- ============================================================
-- 5. RUNTIME SESSION SAFETY SETTINGS
-- ============================================================

-- Keep runtime queries reasonably bounded.

ALTER ROLE li_backend_runtime
SET statement_timeout = '30s';


ALTER ROLE li_backend_runtime
SET lock_timeout = '5s';


ALTER ROLE li_backend_runtime
SET idle_in_transaction_session_timeout = '60s';


-- Prefer controlled API functions and system catalog objects.

ALTER ROLE li_backend_runtime
SET search_path = li_api, pg_catalog;


-- ============================================================
-- 6. VERIFY NO THEO CAPABILITY
-- ============================================================

-- Ordinary Li backend operations must not be able to review
-- and approve their own memory proposals.

REVOKE li_memory_theo
FROM li_backend_runtime;


-- ============================================================
-- 7. RECORD MIGRATION
-- ============================================================

INSERT INTO li_memory.schema_versions (
    version,
    description
)
VALUES (
    '0.6',
    'Create restricted Li OS backend runtime database role'
)
ON CONFLICT (version) DO NOTHING;


-- ============================================================
-- 8. FINAL SECURITY STATE
-- ============================================================

-- li_backend_runtime:
--
-- LOGIN enabled.
-- Password intentionally unset.
-- No superuser.
-- No database creation.
-- No role creation.
-- No RLS bypass.
-- No direct canonical-memory table privileges.
-- No Theo review capability.
-- Inherits only li_memory_api.
--
-- A real password must be assigned separately and must never
-- be committed to GitHub.
--
-- The resulting credential will later be stored in:
--
-- LI_OS_DATABASE_URL
--
-- through a private .env file or deployment secrets manager.


COMMIT;
