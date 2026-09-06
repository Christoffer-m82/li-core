# Encrypted backup creation and restore drills

## Create an encrypted backup

[`create-encrypted-backup.ps1`](create-encrypted-backup.ps1) streams a PostgreSQL custom archive
from `pg_dump` directly into a framed `LIOSBKP1` AES-256-GCM file. It then authenticates every
encrypted frame and validates the archive catalogue with `pg_restore --list` before promoting the
`.partial` file to the requested final path. No plaintext dump is written.

The tool refuses to overwrite an existing backup or partial output. Database and encryption
passphrases are entered at masked prompts and are never accepted as command-line parameters. Use a
new, unique encryption passphrase for every replacement backup and keep it outside the repository.

```powershell
pwsh -NoProfile -File .\memory\backup-tools\create-encrypted-backup.ps1 `
  -HostName '<source-database-host>' `
  -Port 5432 `
  -DatabaseName '<source-database-name>' `
  -UserName '<approved-backup-user>' `
  -OutputPath '.\output\backups\li-os-memory-yyyyMMddTHHmmssZ.pgdump.liosenc'
```

Creating a backup is a database read and may consume provider egress. Confirm authorization and
no-additional-charge coverage before running it. Never record its passphrase in Git, chat, logs, or
the release evidence.

## Operator cadence

For the personal-use system, run an authenticated creation-and-restore drill at least once each
calendar month and before every authorized staging migration, whichever comes first. Also run one
after a material database or backup-tool change. The 2026-09-06 drill is the current baseline, so
the next routine drill is due by 2026-10-06 unless a staging migration requires it sooner.

Each occurrence must use a fresh dated backup path and an independently chosen passphrase, restore
into a newly created disposable database, record the checks listed below, and remove the disposable
target after review. Keep at least one independently encrypted, fully validated current backup until
its successor has passed the same checks. This is an operator procedure only: it does not authorize
a cloud scheduler, paid storage, migration, or external deletion.

## Restore an encrypted backup

This tool implements the controlled restore sequence required by the
[Memory Storage Policy](../storage-policy.md#41-restore-testing). It restores the Li-owned schemas
from a `LIOSBKP1` AES-256-GCM encrypted PostgreSQL custom archive into an already-created, empty,
isolated database, then verifies the schema version and representative canonical retrieval counts.
Supabase platform schemas and extensions are deliberately excluded so the portability drill can run
on standard PostgreSQL without recreating Supabase itself.

It does not create or delete a database, obtain credentials, calculate RPO from an incident, or
declare a backup strategy complete. The operator must supply the expected SHA-256 from an
independent release record and enter both passwords privately at masked prompts.

## Safety gates

- Use only a disposable non-production database whose name begins with `li_os_restore_`,
  `li_os_recovery_`, or `li_os_drill_`.
- Create the isolated target through an approved operator process. Never point this tool at the Li
  staging or production database.
- The target must contain no non-system schemas or public relations. The tool fails closed before
  decryption if a previous or partial restore used it.
- The independently recorded SHA-256 must match before either password is requested.
- The tool verifies that `pgcrypto` is available, then enables it in the isolated target for the Li
  schema objects that require it.
- The tool creates only the five empty Li-owned schema containers before streaming their archived
  contents. Supabase platform schemas are never selected.
- The tool creates the Li runtime and API roles referenced by row-level-security policies as
  credential-free restore roles. PostgreSQL roles are cluster-wide, so the target must be a fresh,
  dedicated, disposable cluster rather than merely an empty database on a shared cluster. The tool
  recreates each capability and runtime role's authoritative login, inheritance, connection-limit,
  and timeout properties, but assigns no password. It refuses to continue if any expected Li or
  compatibility role already exists. If the source archive's `postgres` owner role is absent, the
  tool creates it as a restricted `NOLOGIN` placeholder.
- PostgreSQL database dumps do not contain cluster-level role memberships. The tool reconstructs
  the four governed capability-to-runtime memberships and the minimum schema-level `USAGE` grants
  established by the immutable migrations before restoring archive contents.
- The Supabase API role names `anon`, `authenticated`, and `service_role` are created as equally
  restricted `NOLOGIN` compatibility placeholders. They receive no Li access; their presence lets
  restored and subsequent migrations execute explicit deny-list revocations on standard PostgreSQL.
- Li object ownership and access-control entries are restored along with schema objects and data so
  immutable migrations can verify and extend the original authority boundaries.
- Decrypted archive bytes stream directly to `pg_restore`; the tool does not write a plaintext dump.
- The target remains after validation for inspection. Removing it is a separate destructive action.
- A failed target may contain a partial restore. Do not reuse it.

## Prerequisites

- PowerShell 7 or later.
- PostgreSQL client tools `psql` and `pg_restore` on `PATH`.
- Standard PostgreSQL with the `pgcrypto` extension available to restored Li objects.
- Permission to create restricted `NOLOGIN` roles and their governed memberships in the dedicated
  disposable PostgreSQL cluster.
- Network access and credentials for the isolated target.
- The backup passphrase held separately by the owner.

## Run

From the repository root, substitute only the isolated target details and the hash from the dated
release record:

```powershell
pwsh -NoProfile -File .\memory\backup-tools\restore-encrypted-backup.ps1 `
  -BackupPath .\output\backups\example.pgdump.liosenc `
  -ExpectedSha256 '<64-character recorded SHA-256>' `
  -HostName '<isolated-database-host>' `
  -Port 5432 `
  -DatabaseName 'li_os_restore_yyyymmdd' `
  -UserName '<isolated-database-user>' `
  -ExpectedSchemaVersion '0.39' `
  -ConfirmIsolatedTarget
```

The expected schema version is deliberately operator-supplied. Do not infer it from the current
repository: a valid older backup may intentionally restore an older schema that must then be
advanced through the immutable migration sequence.

Record start/end time, the backup hash, schema version, validation result, RTO, separately calculated
RPO, and cleanup disposition in a dated release or recovery record. Do not record passwords,
passphrases, private memory values, or provider tokens.
