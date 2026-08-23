BEGIN;

-- ============================================================
-- Li OS Memory Security Baseline
-- Migration: 002
--
-- Purpose:
-- 1. Move canonical Li OS memory out of the public schema.
-- 2. Remove access from Supabase client/API roles.
-- 3. Establish default-deny privileges for future objects.
-- 4. Ensure RLS remains enabled and forced.
--
-- No personal memory is added by this migration.
-- ============================================================


-- ============================================================
-- 1. CREATE PRIVATE MEMORY SCHEMA
-- ============================================================

CREATE SCHEMA IF NOT EXISTS li_memory
AUTHORIZATION postgres;


-- Do not allow ordinary roles to use this schema.

REVOKE ALL ON SCHEMA li_memory FROM PUBLIC;
REVOKE ALL ON SCHEMA li_memory FROM anon;
REVOKE ALL ON SCHEMA li_memory FROM authenticated;
REVOKE ALL ON SCHEMA li_memory FROM service_role;


-- ============================================================
-- 2. MOVE LI OS MEMORY TABLES OUT OF PUBLIC
-- ============================================================

ALTER TABLE public.schema_versions
SET SCHEMA li_memory;

ALTER TABLE public.users
SET SCHEMA li_memory;

ALTER TABLE public.people
SET SCHEMA li_memory;

ALTER TABLE public.memory_records
SET SCHEMA li_memory;

ALTER TABLE public.memory_relations
SET SCHEMA li_memory;

ALTER TABLE public.memory_person_links
SET SCHEMA li_memory;

ALTER TABLE public.goals
SET SCHEMA li_memory;

ALTER TABLE public.decisions
SET SCHEMA li_memory;

ALTER TABLE public.commitments
SET SCHEMA li_memory;

ALTER TABLE public.open_loops
SET SCHEMA li_memory;

ALTER TABLE public.timeline_events
SET SCHEMA li_memory;

ALTER TABLE public.documents
SET SCHEMA li_memory;

ALTER TABLE public.memory_document_links
SET SCHEMA li_memory;

ALTER TABLE public.memory_write_proposals
SET SCHEMA li_memory;

ALTER TABLE public.memory_access_grants
SET SCHEMA li_memory;

ALTER TABLE public.memory_audit_log
SET SCHEMA li_memory;

ALTER TABLE public.experience_records
SET SCHEMA li_memory;

ALTER TABLE public.tags
SET SCHEMA li_memory;

ALTER TABLE public.memory_tags
SET SCHEMA li_memory;


-- ============================================================
-- 3. MOVE LI OS HELPER FUNCTION
-- ============================================================

ALTER FUNCTION public.set_updated_at()
SET SCHEMA li_memory;


-- ============================================================
-- 4. REMOVE CLIENT/API ROLE ACCESS
-- ============================================================

REVOKE ALL PRIVILEGES
ON ALL TABLES IN SCHEMA li_memory
FROM PUBLIC, anon, authenticated, service_role;

REVOKE ALL PRIVILEGES
ON ALL SEQUENCES IN SCHEMA li_memory
FROM PUBLIC, anon, authenticated, service_role;

REVOKE EXECUTE
ON ALL FUNCTIONS IN SCHEMA li_memory
FROM PUBLIC, anon, authenticated, service_role;


-- ============================================================
-- 5. DEFAULT-DENY FUTURE OBJECTS IN LI_MEMORY
-- ============================================================

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA li_memory
REVOKE ALL ON TABLES
FROM PUBLIC, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA li_memory
REVOKE ALL ON SEQUENCES
FROM PUBLIC, anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA li_memory
REVOKE EXECUTE ON FUNCTIONS
FROM PUBLIC, anon, authenticated, service_role;


-- ============================================================
-- 6. KEEP PUBLIC DEFAULT-DENY TOO
-- ============================================================

-- If we create future objects in public, they should not
-- automatically become available to API roles.

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA public
REVOKE ALL ON TABLES
FROM anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA public
REVOKE ALL ON SEQUENCES
FROM anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES
FOR ROLE postgres
IN SCHEMA public
REVOKE EXECUTE ON FUNCTIONS
FROM PUBLIC, anon, authenticated, service_role;


-- ============================================================
-- 7. ENFORCE ROW LEVEL SECURITY
-- ============================================================

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
            'ALTER TABLE li_memory.%I ENABLE ROW LEVEL SECURITY',
            table_record.tablename
        );

        EXECUTE format(
            'ALTER TABLE li_memory.%I FORCE ROW LEVEL SECURITY',
            table_record.tablename
        );
    END LOOP;
END
$$;


-- ============================================================
-- 8. RECORD SCHEMA VERSION
-- ============================================================

INSERT INTO li_memory.schema_versions (
    version,
    description
)
VALUES (
    '0.2',
    'Move Li OS memory into private schema and establish security baseline'
)
ON CONFLICT (version) DO NOTHING;


-- ============================================================
-- 9. FINAL SECURITY STATE
-- ============================================================

-- At the end of this migration:
--
-- * Li OS memory tables live in li_memory, not public.
-- * Data API roles have no access.
-- * Future objects are default-deny.
-- * RLS is enabled and forced.
-- * No application/API role has yet been granted memory access.
--
-- Li and Theo will later access memory through a deliberately
-- designed Li OS Memory API using dedicated credentials and
-- narrowly scoped authorization.
--
-- DO NOT expose li_memory through Supabase's Data API settings.


COMMIT;
