BEGIN;

-- ============================================================
-- Li OS Memory API Boundary
-- Migration: 003
-----------------

-- Purpose:
-- Establish a controlled database security boundary between
-- Li OS applications/agents and the canonical memory tables.
-------------------------------------------------------------

## -- Design:

| --   Li / Theo                                                  |
| --------------------------------------------------------------- |
| --       v                                                      |
| --   Li OS Memory API                                           |
| --                                                              |
| --       v                                                      |
| --   li_memory_api role                                         |
| --                                                              |
| --       v                                                      |
| --   approved li_api functions                                  |
| --                                                              |
| --       v                                                      |
| --   li_memory_function_owner                                   |
| --                                                              |
| --       v                                                      |
| --   canonical li_memory tables                                 |
| --                                                              |
| -- Li and application services must NOT receive unrestricted    |
| -- direct table access.                                         |
| -- ============================================================ |

-- ============================================================
-- 1. CREATE INTERNAL DATABASE ROLES
-- ============================================================

DO $$
BEGIN

```
IF NOT EXISTS (
    SELECT 1
    FROM pg_roles
    WHERE rolname = 'li_memory_function_owner'
) THEN
    EXECUTE '
        CREATE ROLE li_memory_function_owner
        NOLOGIN
        NOSUPERUSER
        NOCREATEDB
        NOCREATEROLE
        NOINHERIT
        NOREPLICATION
        NOBYPASSRLS
    ';
END IF;


IF NOT EXISTS (
    SELECT 1
    FROM pg_roles
    WHERE rolname = 'li_memory_api'
) THEN
    EXECUTE '
        CREATE ROLE li_memory_api
        NOLOGIN
        NOSUPERUSER
        NOCREATEDB
        NOCREATEROLE
        NOINHERIT
        NOREPLICATION
        NOBYPASSRLS
    ';
END IF;
```

END
$$;

-- ============================================================
-- 2. FUNCTION OWNER ACCESS
-- ============================================================

## -- This role cannot log in.

## -- It exists only to own approved SECURITY DEFINER functions.

-- The application role will NOT inherit this role.

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
-- 3. RLS POLICY FOR FUNCTION OWNER
-- ============================================================

## -- RLS remains enabled and forced on the canonical tables.

-- The special function-owner role receives access because
-- approved API functions execute under this identity.
------------------------------------------------------

-- The application role itself does NOT receive this access.

DO $$
DECLARE
table_record RECORD;
BEGIN

```
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
```

END
$$;

-- ============================================================
-- 4. CREATE API SCHEMA
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
-- 5. HEALTH CHECK FUNCTION
-- ============================================================

## -- This intentionally exposes no personal memory.

## -- It lets the future Li OS backend prove that:

--   1. authentication works;
--   2. the approved API boundary works;
--   3. canonical memory is reachable;
--   4. direct table access is unnecessary.

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

```
    (
        SELECT version
        FROM li_memory.schema_versions
        ORDER BY applied_at DESC
        LIMIT 1
    ),

    (
        SELECT COUNT(*)::BIGINT
        FROM pg_catalog.pg_tables
        WHERE schemaname = 'li_memory'
    );
```

$$;

ALTER FUNCTION li_api.health_check()
OWNER TO li_memory_function_owner;

-- Functions receive PUBLIC EXECUTE privileges by default in
-- PostgreSQL, so explicitly remove them.

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
-- 6. ENSURE APPLICATION ROLE HAS NO TABLE ACCESS
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

-- The API role deliberately receives access to li_api only.

GRANT USAGE
ON SCHEMA li_api
TO li_memory_api;

-- ============================================================
-- 7. RECORD MIGRATION
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
-- 8. SECURITY RULE
-- ============================================================

-- li_memory_api must NEVER be granted unrestricted access to
-- the canonical li_memory tables.
----------------------------------

-- Future Memory API capabilities should be implemented through
-- narrowly scoped functions in li_api.
---------------------------------------

## -- Examples:

--   li_api.recall_memory(...)
--   li_api.store_memory(...)
--   li_api.propose_memory(...)
--   li_api.get_person(...)
--   li_api.get_goals(...)
--   li_api.get_open_loops(...)
-------------------------------

## -- Each function must:

--   * validate its inputs;
--   * enforce the intended user scope;
--   * return only necessary information;
--   * respect sensitivity and permissions;
--   * avoid exposing raw secrets.
----------------------------------

-- A future runtime LOGIN role will be created separately.
-- Its password or credential must NEVER be committed to GitHub.

COMMIT;
