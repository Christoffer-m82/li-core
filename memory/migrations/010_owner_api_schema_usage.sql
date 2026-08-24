BEGIN;

-- ============================================================
-- Li OS Owner API Schema Access
-- Migration: 010
--
-- Purpose:
-- Allow the owner-confirmation capability to reach approved
-- functions in li_api without granting direct memory-table
-- access or schema creation privileges.
-- ============================================================


GRANT USAGE
ON SCHEMA li_api
TO li_memory_owner_confirmation;


REVOKE CREATE
ON SCHEMA li_api
FROM li_memory_owner_confirmation;


REVOKE CREATE
ON SCHEMA li_api
FROM li_owner_runtime;


INSERT INTO li_memory.schema_versions (
    version,
    description
)
VALUES (
    '0.10',
    'Grant owner confirmation capability usage of li_api schema'
)
ON CONFLICT (version) DO NOTHING;


COMMIT;