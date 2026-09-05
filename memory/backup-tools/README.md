# Encrypted backup restore drill

This tool implements the controlled restore sequence required by the
[Memory Storage Policy](../storage-policy.md#41-restore-testing). It restores a `LIOSBKP1`
AES-256-GCM encrypted PostgreSQL custom archive into an already-created, empty, isolated database,
then verifies the schema version and representative canonical retrieval counts.

It does not create or delete a database, obtain credentials, calculate RPO from an incident, or
declare a backup strategy complete. The operator must supply the expected SHA-256 from an
independent release record and enter both passwords privately at masked prompts.

## Safety gates

- Use only a disposable non-production database whose name begins with `li_os_restore_`,
  `li_os_recovery_`, or `li_os_drill_`.
- Create the isolated target through an approved operator process. Never point this tool at the Li
  staging or production database.
- The target must contain no non-system tables. The tool fails closed before decryption if it is not
  empty.
- The independently recorded SHA-256 must match before either password is requested.
- Decrypted archive bytes stream directly to `pg_restore`; the tool does not write a plaintext dump.
- The target remains after validation for inspection. Removing it is a separate destructive action.
- A failed target may contain a partial restore. Do not reuse it.

## Prerequisites

- PowerShell 7 or later.
- PostgreSQL client tools `psql` and `pg_restore` on `PATH`.
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

Record start/end time, the backup hash, schema version, validation result, RTO, separately calculated
RPO, and cleanup disposition in a dated release or recovery record. Do not record passwords,
passphrases, private memory values, or provider tokens.
