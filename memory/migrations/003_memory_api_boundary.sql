BEGIN;

-- ============================================================
-- Li OS Memory API Boundary
-- Migration: 003
--
-- Purpose:
-- Establish a controlled database security boundary between
-- Li OS applications and the canonical memory tables.
--
-- Li and Theo will use a future Li OS Memory API.
-- The Memory API will call approved database functions.
-- Application roles will not receive unrestricted direct
-- access to canonical personal-memory tables.
-- ============================================================


-- ============================================================
-- 1. CREATE INTERNAL DATABASE ROLES
-- ============================================================

DO $$
BEGIN

    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'li_memory_function_owner'
    ) THEN
        CREATE ROLE li_memory_function_owner
        NOLOGIN
        NOSUPERUSER
        NOCREATEDB
        NOCREATEROLE
        NOINHERIT
        NOREPLICATION
        NOBYPASSRLS;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'li_memory_api'
    ) THEN
        CREATE ROLE li_memory_api
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
-- 2. FUNCTION OWNER ACCESS
-- ============================================================

-- li_memory_function_owner cannot log in.
-- It exists only to own approved SECURITY DEFINER functions.

GRANT USAGE
ON SCHEMA li_memory
TO li_memory_function_owner;


GRANT
    SELECT,
    INSERT,
    UPDATE,
    DELETE
ON ALL TABLES IN SCHEMA li_memory
TO li_memory_function_owner;


GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA li_memory
TO li_memory_function_owner;


-- ============================================================
-- 3. DEFAULT PRIVILEGES FOR FUNCTION OWNER
-- ============================================================

-- Future canonical tables and sequences created by postgres
-- should also be usable by the controlled function-owner role.

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA li_memory
GRANT
    SELECT,
    INSERT,
    UPDATE,
    DELETE
ON TABLES
TO li_memory_function_owner;


ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA li_memory
GRANT USAGE, SELECT
ON SEQUENCES
TO li_memory_function_owner;


-- ============================================================
-- 4. RLS POLICIES FOR FUNCTION OWNER
-- ============================================================

-- Canonical tables already have Row Level Security enabled.
--
-- Create an explicit policy allowing the controlled
-- function-owner role to work with canonical memory.
--
-- The application API role itself does not receive this access.

DO $$
DECLARE
    table_record RECORD;
BEGIN

    FOR table_record IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'li_memory'
    LOOP

        EXECUTE format(
            'DROP POLICY IF EXISTS li_memory_function_owner_access ON li_memory.%I',
            table_record.tablename
        );

        EXECUTE format(
            'CREATE POLICY li_memory_function_owner_access
             ON li_memory.%I
             FOR ALL
             TO li_memory_function_owner
             USING (true)
             WITH CHECK (true)',
            table_record.tablename
        );

    END LOOP;

END
$$;


-- ============================================================
-- 5. CREATE CONTROLLED API SCHEMA
-- ============================================================

CREATE SCHEMA IF NOT EXISTS li_api
AUTHORIZATION postgres;


REVOKE ALL
ON SCHEMA li_api
FROM PUBLIC;


REVOKE ALL
ON SCHEMA li_api
FROM anon;


REVOKE ALL
ON SCHEMA li_api
FROM authenticated;


REVOKE ALL
ON SCHEMA li_api
FROM service_role;


GRANT USAGE
ON SCHEMA li_api
TO li_memory_api;


-- ============================================================
-- 6. DEFAULT-DENY FUTURE API FUNCTIONS
-- ============================================================

-- PostgreSQL normally grants EXECUTE on new functions to PUBLIC.
-- Remove that default for future functions created by postgres
-- inside the li_api schema.

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA li_api
REVOKE EXECUTE
ON FUNCTIONS
FROM PUBLIC;


ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA li_api
REVOKE EXECUTE
ON FUNCTIONS
FROM anon;


ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA li_api
REVOKE EXECUTE
ON FUNCTIONS
FROM authenticated;


ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA li_api
REVOKE EXECUTE
ON FUNCTIONS
FROM service_role;


-- ============================================================
-- 7. HEALTH CHECK FUNCTION
-- ============================================================

-- This function exposes no personal memory.
--
-- It proves that the API role can call an approved function
-- without receiving direct access to canonical memory tables.

CREATE OR REPLACE FUNCTION li_api.health_check()
RETURNS TABLE (
    status TEXT,
    schema_version TEXT,
    canonical_tables BIGINT
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = li_memory, pg_catalog, pg_temp
AS $$
    SELECT
        'ok'::TEXT,

        (
            SELECT version
            FROM li_memory.schema_versions
            ORDER BY applied_at DESC
            LIMIT 1
        )::TEXT,

        (
            SELECT COUNT(*)::BIGINT
            FROM pg_catalog.pg_tables
            WHERE schemaname = 'li_memory'
        );
$$;


ALTER FUNCTION li_api.health_check()
OWNER TO li_memory_function_owner;


-- ============================================================
-- 8. REMOVE DEFAULT FUNCTION ACCESS
-- ============================================================

REVOKE ALL
ON FUNCTION li_api.health_check()
FROM PUBLIC;


REVOKE ALL
ON FUNCTION li_api.health_check()
FROM anon;


REVOKE ALL
ON FUNCTION li_api.health_check()
FROM authenticated;


REVOKE ALL
ON FUNCTION li_api.health_check()
FROM service_role;


-- Only the dedicated API capability role may execute it.

GRANT EXECUTE
ON FUNCTION li_api.health_check()
TO li_memory_api;


-- ============================================================
-- 9. ENSURE API ROLE HAS NO DIRECT MEMORY TABLE ACCESS
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
-- 10. ENSURE SUPABASE CLIENT ROLES CANNOT USE LI_API
-- ============================================================

REVOKE ALL
ON SCHEMA li_api
FROM anon;


REVOKE ALL
ON SCHEMA li_api
FROM authenticated;


REVOKE ALL
ON SCHEMA li_api
FROM service_role;


REVOKE ALL
ON FUNCTION li_api.health_check()
FROM anon;


REVOKE ALL
ON FUNCTION li_api.health_check()
FROM authenticated;


REVOKE ALL
ON FUNCTION li_api.health_check()
FROM service_role;


-- Reconfirm the intended API role access.

GRANT USAGE
ON SCHEMA li_api
TO li_memory_api;


GRANT EXECUTE
ON FUNCTION li_api.health_check()
TO li_memory_api;


-- ============================================================
-- 11. RECORD MIGRATION
-- ============================================================

INSERT INTO li_memory.schema_versions (
    version,
    description
)
VALUES (
    '0.3',
    'Create controlled Li OS Memory API database boundary'
)
ON CONFLICT (version) DO NOTHING;


-- ============================================================
-- 12. SECURITY NOTES
-- ============================================================

-- Final intended state:
--
-- li_memory_function_owner:
--   No login.
--   No superuser.
--   No bypass RLS.
--   Can access canonical memory only so approved SECURITY
--   DEFINER functions can perform controlled operations.
--
-- li_memory_api:
--   No login.
--   No superuser.
--   No bypass RLS.
--   No direct access to canonical memory tables.
--   May execute specifically approved li_api functions.
--
-- anon:
--   No access.
--
-- authenticated:
--   No access.
--
-- service_role:
--   No access to the Li OS private memory schemas.
--
-- A future runtime LOGIN role will be created separately and
-- granted only the li_memory_api capability.
--
-- Runtime credentials must never be committed to GitHub.
--
-- Future Memory API functions should be narrowly scoped and
-- should validate user identity, purpose, permissions,
-- sensitivity, and requested operation before accessing
-- canonical memory.


COMMIT;
