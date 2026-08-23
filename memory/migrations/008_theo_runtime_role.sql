BEGIN;

-- ============================================================
-- Li OS Theo Runtime Role
-- Migration: 008
--
-- Purpose:
-- Create a dedicated login role for Theo's memory-review
-- workflow without granting Theo direct canonical table access
-- or Li's ordinary runtime capability role.
-- ============================================================


-- ============================================================
-- 1. CREATE DEDICATED THEO LOGIN ROLE
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'li_theo_runtime'
    ) THEN
        CREATE ROLE li_theo_runtime
            LOGIN
            INHERIT
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOBYPASSRLS
            CONNECTION LIMIT 5
            PASSWORD NULL;
    END IF;
END
$$;


-- Reassert the intended security properties even if the role
-- already existed before this migration.

ALTER ROLE li_theo_runtime
    LOGIN
    INHERIT
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS
    CONNECTION LIMIT 5;


ALTER ROLE li_theo_runtime
    SET statement_timeout = '30s';


ALTER ROLE li_theo_runtime
    SET lock_timeout = '5s';


ALTER ROLE li_theo_runtime
    SET idle_in_transaction_session_timeout = '60s';


ALTER ROLE li_theo_runtime
    SET search_path TO li_api, pg_catalog;


-- ============================================================
-- 2. CAPABILITY SEPARATION
-- ============================================================

-- Theo receives the dedicated review capability.

GRANT li_memory_theo
TO li_theo_runtime;


-- Theo must not inherit Li's normal runtime capability.

REVOKE li_memory_api
FROM li_theo_runtime;


-- ============================================================
-- 3. NO DIRECT CANONICAL MEMORY ACCESS
-- ============================================================

REVOKE ALL
ON SCHEMA li_memory
FROM li_theo_runtime;


REVOKE ALL PRIVILEGES
ON ALL TABLES IN SCHEMA li_memory
FROM li_theo_runtime;


REVOKE ALL PRIVILEGES
ON ALL SEQUENCES IN SCHEMA li_memory
FROM li_theo_runtime;


-- Theo reaches memory only through approved li_api functions
-- inherited from li_memory_theo.


-- ============================================================
-- 4. RECORD MIGRATION
-- ============================================================

INSERT INTO li_memory.schema_versions (
    version,
    description
)
VALUES (
    '0.8',
    'Add dedicated restricted Theo runtime database role'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;