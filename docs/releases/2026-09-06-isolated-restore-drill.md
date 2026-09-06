# Isolated restore drill — 2026-09-06

## Scope

This record documents a local, disposable PostgreSQL recovery drill for the encrypted staging
backup created before migrations 037–039. It is operator evidence, not proof of production,
Supabase, deployment, scheduler, or physical-device state. No plaintext dump was written and no
personal row values were printed or recorded.

## Source evidence

| Field | Recorded value |
| --- | --- |
| Backup | `li-os-memory-dev-pre-037-20260905T122033Z.pgdump.liosenc` |
| SHA-256 | `c9a642f81adc2be2c260e3598c05aa41a813f25099bd40ebe216241cdcc96414` |
| Source schema | `0.36` |
| Target | Local disposable PostgreSQL 17 container bound to loopback only |
| Restore tool | [`memory/backup-tools/restore-encrypted-backup.ps1`](../../memory/backup-tools/restore-encrypted-backup.ps1) |

The owner entered the database and encryption passphrases only at masked local prompts. An earlier
passphrase was exposed outside the repository during troubleshooting; it is not recorded here and
must not be reused. The existing encrypted backup should be retired only after an independently
encrypted replacement has been created and validated.

## Result

The final clean run authenticated the complete encrypted stream, restored the five Li-owned schemas,
reconstructed the governed database roles and memberships without passwords, and excluded Supabase
platform schemas. The restore tool reported 2.23 seconds for decrypt, restore, and its initial
retrieval validation.

| Assertion | Result |
| --- | --- |
| Restored schema before forward migration | `0.36` |
| Active owners | `1` |
| Canonical memory records | `23` |
| Canonical tables before forward migration | `61` |
| Supabase platform schemas restored | `0` |
| Migrations 037, 038, and 039 | Passed in order |
| Final schema | `0.39` |
| Active owners after migration | `1` |
| Canonical memory records after migration | `23` |
| Canonical tables after migration | `62` |
| Li schemas owned by the expected owner role | `5 of 5` |
| Runtime roles safe and passwordless | `4 of 4` |
| Capability roles matched intended inheritance classes | `5 of 5` |
| Governed runtime-to-capability memberships | `4 of 4` |
| Backend conversation-history capability | Passed |
| Retention conversation-history denial | Passed |
| Recovery tables with row-level security enabled | `2 of 2` |
| Representative recovery functions owned by function owner | `3 of 3` |

The immutable migrations' own transactional checks also passed. Failed intermediate targets were
treated as partial and never reused. After evidence was recorded, all three loopback-only disposable
containers were removed, which removed the successful and partial drill databases with them.

## Recovery timing and limits

The measured 2.23 seconds is the tool's local restore-and-validation duration after the target and
credentials were ready. Migration and final validation commands each completed in under one second
on the same local machine. This is not an end-to-end operational RTO: target provisioning, operator
secret entry, diagnosis, and service reconnection were not measured as one uninterrupted interval.

No incident time exists for this drill, so an RPO cannot be calculated. The backup filename records
its creation time as 2026-09-05 12:20:33 UTC; that timestamp must be compared with a real recovery
event's data-loss boundary when calculating RPO.

## Remaining actions

- Establish and approve a recurring restore-test cadence.
- Create and authenticate a replacement encrypted backup using a new private passphrase, then retire
  the old encrypted backup through a separately controlled deletion step.
- Keep physical-device, stable-use, live-provider, and production rollback evidence separate from
  this local database result.
