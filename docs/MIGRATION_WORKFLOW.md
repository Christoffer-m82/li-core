# Migration workflow

## Scope and authority

The authoritative principles are [Memory Storage Policy: Database Migrations](../memory/storage-policy.md#57-database-migrations),
[Migration Safety](../memory/storage-policy.md#58-migration-safety), and
[Rollback](../memory/storage-policy.md#59-rollback). This document maps those principles to the
repository's SQL migration layout. It does not authorize applying a migration to Supabase or any
other database.

## Repository facts

- The baseline is `memory/database-schema.sql`; ordered changes live in `memory/migrations/`.
- Migration files are transactional SQL (`BEGIN`/`COMMIT`) and record logical versions in
  `li_memory.schema_versions`.
- Later migrations contain explicit prerequisite and duplicate-version guards.
- Application tests inspect important migration text and authority invariants. The explicit historical
  manifest in `memory/tests/validate_migrations.py` applies the supported sequence to a disposable
  PostgreSQL database and verifies representative data, RLS, ownership, allowed/denied access and
  replay rejection. It is a local/CI rehearsal, not an external migration runner or target-state proof.
- Two historical files share the `021` prefix and both record schema version `0.21`:
  `021_artifact_library.sql` and `021_private_conversation_deletion.sql`. Migration 025 explains that
  the private-deletion capability is restored at schema version `0.25`. See
  [Known risks](KNOWN_RISKS.md#kr-001-duplicate-migration-number-and-schema-version).

## Create or review a migration

1. Identify the exact current schema version from the target database through an authorized,
   read-only owner check. A filename list is not proof of applied state.
2. Read every migration from the verified version through the proposed dependency; do not rely only
   on numeric prefixes.
3. Add a new, uniquely numbered SQL file. Never rewrite a historical migration that may have been
   applied.
4. Begin a transaction and fail closed on a missing prerequisite, a claimed target version, or an
   invalid owner/authority precondition.
5. Create or alter objects under the intended owner context. Keep temporary `SET ROLE`, schema
   `CREATE`, and other elevated authority bounded and assert that it is removed before commit.
6. Enable and verify RLS where applicable. Revoke broad/default privileges, grant only required
   function execution, and assert no direct table or sequence authority leaked to runtime roles.
7. Keep owner, Theo, backend, native-gateway, retention, `anon`, `authenticated`, and `service_role`
   boundaries explicit.
8. Make retry and idempotency behavior deliberate. Do not hide a partial data conversion behind
   `ON CONFLICT DO NOTHING` without proving the resulting state.
9. Insert one new logical version and description only after all migration assertions pass, then
   commit the transaction.
10. Add focused static contract tests and, when a database harness is available, behavioral tests
    for success, denial, replay, ownership, grants, RLS, and data preservation.

## Pre-application gate

Before any external write:

- obtain explicit authorization for the exact environment and SQL file;
- capture and verify a restorable backup using the environment's approved process;
- rehearse on a non-production copy with representative synthetic/anonymized data;
- record pre-migration schema versions, object ownership, grants, policies, record counts, and
  integrity checks;
- review forward compatibility with the currently deployed application and backward compatibility
  with the rollback revision;
- define stop conditions and a data-preserving recovery plan; and
- have independent memory-integrity and security reviews for significant changes, as required by
  the storage policy.

## Application and validation

Apply the complete reviewed file once through the owner-controlled process. Do not paste fragments
into an interactive console, automatically apply from application startup, or run against an
environment inferred from a default CLI profile.

Afterward verify:

- exactly the expected schema version was added;
- the transaction completed with no partial objects;
- owners, grants, RLS policies, triggers, and function search paths match the review;
- runtime roles can perform allowed function calls and cannot perform representative forbidden
  table/function calls;
- counts, relationships, retrieval, correction/deletion, and audit behavior remain valid; and
- the intended application revision passes readiness and focused smoke tests.

Record operator, time, environment identifier, commit, file checksum, before/after versions, backup
reference, validation evidence, and exceptions without recording credentials or personal data.

## Failure and recovery

Stop application rollout on any failed assertion or unexplained data/authority change. Because the
repository contains forward migrations rather than generic down migrations, recovery may require a
new corrective migration, restoring a verified backup, or temporarily running a compatible
application revision. Choose the path that preserves legitimate writes made after migration start;
never modify an applied file or assume traffic rollback reverses the database.
