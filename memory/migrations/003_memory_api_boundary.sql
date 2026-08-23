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
-- 2. TEMPORARILY ALLOW POSTGRES TO ASSUME FUNCTION OWNER
-- ============================================================

-- Supabase migrations run through postgres.
-- PostgreSQL requires the migration role to be able to SET ROLE
-- to a new function owner before ownership can be transferred.
--
-- This membership is removed again before the migration ends.

GRANT li_memory_function_owner TO postgres;


-- ============================================================
-- 3. FUNCTION OWNER ACCESS TO CANONICAL MEMORY
-- ============================================================

-- li_memory_function_owner cannot log in.
--
-- It exists only so approved SECURITY DEFINER functions can
-- interact with canonical memory.

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
-- 4. DEFAULT PRIVILEGES FOR FUTURE MEMORY OBJECTS
-- ============================================================

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
-- 5. RLS POLICIES FOR FUNCTION OWNER
-- ============================================================

-- RLS remains enabled and forced.
--
-- The controlled function-owner role receives explicit access.
-- The application API role does not receive this access.

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
-- 6. CREATE CONTROLLED API SCHEMA
-- ============================================================

CREATE SCHEMA IF NOT EXISTS li_api
AUTHORIZATION postgres;


-- No ordinary or Supabase API role should receive access.

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


-- The capability role may call approved API functions.

GRANT USAGE
ON SCHEMA li_api
TO li_memory_api;


-- The function-owner role temporarily needs CREATE permission
-- because PostgreSQL requires a new function owner to have
-- CREATE privilege on the function's schema.

GRANT USAGE, CREATE
ON SCHEMA li_api
TO li_memory_function_owner;


-- ============================================================
-- 7. DEFAULT-DENY FUTURE API FUNCTIONS
-- ============================================================

-- PostgreSQL normally grants function EXECUTE permission to
-- PUBLIC by default.
--
-- Remove that behavior for functions created by postgres in
-- the li_api schema.

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
-- 8. CREATE HEALTH CHECK FUNCTION
-- ============================================================

-- This function intentionally returns no personal information.
--
-- It proves that an approved API function can reach canonical
-- memory without giving the application role direct access to
-- memory tables.

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


-- ============================================================
-- 9. TRANSFER FUNCTION OWNERSHIP
-- ============================================================

ALTER FUNCTION li_api.health_check()
OWNER TO li_memory_function_owner;


-- ============================================================
-- 10. REMOVE DEFAULT FUNCTION ACCESS
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
-- 11. ENSURE API ROLE HAS NO DIRECT MEMORY TABLE ACCESS
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
-- 12. RECONFIRM SUPABASE CLIENT ROLE RESTRICTIONS
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


-- Reconfirm the intended capability-role permissions.

GRANT USAGE
ON SCHEMA li_api
TO li_memory_api;


GRANT EXECUTE
ON FUNCTION li_api.health_check()
TO li_memory_api;


-- ============================================================
-- 13. REMOVE TEMPORARY FUNCTION-OWNER CREATE AUTHORITY
-- ============================================================

-- The role required CREATE only so PostgreSQL could transfer
-- ownership of the function to it.
--
-- It no longer needs permission to create arbitrary API
-- functions.

REVOKE CREATE
ON SCHEMA li_api
FROM li_memory_function_owner;


-- Keep USAGE because the role owns and executes approved
-- functions inside this schema.

GRANT USAGE
ON SCHEMA li_api
TO li_memory_function_owner;


-- ============================================================
-- 14. REMOVE TEMPORARY POSTGRES ROLE MEMBERSHIP
-- ============================================================

-- The migration is finished transferring ownership.
-- postgres no longer needs membership in the function-owner
-- role.

REVOKE li_memory_function_owner
FROM postgres;


-- ============================================================
-- 15. RECORD MIGRATION VERSION
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
-- 16. FINAL SECURITY STATE
-- ============================================================

-- li_memory_function_owner:
--
-- No login.
-- No superuser.
-- No database creation.
-- No role creation.
-- No RLS bypass.
-- Has controlled canonical-memory privileges.
-- Owns approved SECURITY DEFINER functions.
-- Cannot create arbitrary new li_api functions.
--
--
-- li_memory_api:
--
-- No login.
-- No superuser.
-- No database creation.
-- No role creation.
-- No RLS bypass.
-- No direct canonical table access.
-- May execute only explicitly approved li_api functions.
--
--
-- anon:
--
-- No Li OS private-memory access.
--
--
-- authenticated:
--
-- No Li OS private-memory access.
--
--
-- service_role:
--
-- No Li OS private-memory table privileges.
--
--
-- Future runtime services:
--
-- A dedicated runtime LOGIN role will be created separately.
-- It will receive only the li_memory_api capability.
--
-- Runtime passwords, tokens, and credentials must never be
-- committed to GitHub.
--
--
-- Future Memory API functions:
--
-- Functions should be narrowly scoped.
-- Functions should validate inputs.
-- Functions should enforce user scope.
-- Functions should respect sensitivity and permissions.
-- Functions should return only necessary information.
-- Functions should never expose raw secrets.


COMMIT;
