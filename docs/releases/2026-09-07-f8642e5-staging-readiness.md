# Finance and Calendar staging readiness: `f8642e5`

## Status and scope

**Prepared, not authorized for external execution.** Source commit
`f8642e5a6aad15ad0c4d0a83ef32e8cf51d1bd4f` contains the private Finance and Calendar foundation.
Relative to the currently deployed web revision, it also includes the already reviewed Specialist
Workspace composer from PR #89. Migration 042, backend deployment, web deployment, provider-backed
Calendar display, Specialist composer staging acceptance, and physical-device acceptance have not
been performed by this readiness work.

Follow the [migration workflow](../MIGRATION_WORKFLOW.md),
[deployment workflow](../DEPLOYMENT_WORKFLOW.md), and
[Finance and Calendar architecture](../../system/FINANCE_CALENDAR_ARCHITECTURE.md). This record does
not authorize a backup, migration, deployment, provider call, personal-data read, or additional
charge.

## Repository evidence

- PR #90 merged the exact source into `main`; all 12 pull-request and all 12 post-merge checks passed.
- PR #89, also included in the prospective web image but not the currently serving web revision,
  passed its pull-request and post-merge checks. Its composer keeps Li visible, supports bounded
  single-file selection/drop, and does not broaden specialist or action authority.
- The complete disposable migration manifest passed through schema 0.42, including synthetic create,
  update, duplicate, archive, owner scoping, runtime allow, and denied-authority cases.
- Backend validation passed Ruff, compile validation, and 1,121 tests with four opt-in provider cases
  skipped. Frontend validation passed Ruff, compile validation, 97 Python tests, and 93 dependency-
  free browser tests. The existing upstream Starlette/AnyIO warnings remained visible.
- Static responsive checks cover phone, tablet, and desktop contracts. They do not establish physical
  Android or installed-Windows behavior.
- Migration `042_private_portfolio_workspace.sql` has SHA-256
  `6b8f905bc0d3bb2b2a9355d37e8ad6c330f63ea7f22d8ff51a06aed9f2dbe0c0`.

## Read-only external snapshot — 2026-09-07

Google Cloud Run reported backend `li-os-release-0fc39a7` and web
`li-os-web-release-7527434` Ready and each serving 100% of its service traffic. The backend retained
`li-os-runtime@li-os-staging.iam.gserviceaccount.com`, 18 numeric secret-version references, and no
`allUsers` binding. The web retained `li-os-web-runtime@li-os-staging.iam.gserviceaccount.com`, five
numeric secret-version references, and its intended public browser sign-in boundary. No secret
value, personal record, provider response, traffic setting, IAM policy, or billing control was
changed.

Schema 0.41 is the last recorded staging database evidence; it was not independently queried in this
read-only snapshot because that requires private database credentials. Current Google Cloud credit
coverage and forecast were not remeasured. They must be verified immediately before any metered
build or deployment.

## Ordered release gates

1. Obtain exact owner authorization for the named staging backup, isolated restore, migration-042
   rehearsal, staging migration, backend candidate, and web candidate. Verify the bounded work is
   covered without purchase, upgrade, paid overage, or additional charge.
2. Recheck `main`, CI, the complete release diff, migration checksum, current Cloud Run identities,
   pinned numeric secret references, IAM and traffic. Query staging privately and require schema
   0.41, no later schema, one active owner, and absent portfolio objects.
3. Create a fresh uniquely named encrypted backup with `-RequirePre042`. Authenticate its complete
   framed archive, record only path, size, SHA-256 and catalogue count, and keep its passphrase outside
   Git, chat, logs, and command arguments.
4. Restore that backup into a new dedicated localhost-only disposable PostgreSQL cluster at schema
   0.41. Record bounded counts and retrieval evidence, then rehearse the exact migration-042 hash.
5. Prove schema 0.42, function ownership, Li/backend execution, synthetic portfolio behavior, and all
   documented denied roles and direct-table paths. Remove only the exactly named disposable target
   after review and separate authorization.
6. Re-run the staging preflight, apply migration 042 once, and repeat the version, ownership, behavior,
   count, and authority checks without reading personal portfolio values.
7. Build backend and web from a tracked-only archive of the same reviewed commit. Publish immutable
   image digests, create separate zero-normal-traffic candidates, and preserve current traffic until
   both components pass their applicable checks.
8. Validate public denial/private IAM for the backend, authenticated health/readiness, schema 0.42,
   runtime identities, exact numeric secret references, web sign-in boundary, signed-in navigation,
   Specialist composer placement and safe attachment handling, unavailable-provider behavior, and
   bounded logs. Promote backend, recheck the live web against it, then promote the tested web
   candidate.
9. Perform one bounded owner-approved Calendar read and synthetic portfolio create/edit/archive
   journey only after privacy and cost gates pass. Do not connect a broker, fetch market quotes, place
   a trade, expose credentials, or inspect unrelated personal history.
10. Record final revisions, immutable digests, traffic, logs, deviations, acceptance evidence and
    residual limitations. Physical Android phone/tablet and installed-Windows PWA acceptance remain
    separate owner steps.

## Stop and rollback rules

Stop before promotion on schema mismatch, backup or restore failure, checksum mismatch, authority
drift, nonnumeric secret reference, unexpected identity/IAM change, sensitive logging, unexplained
data/count change, unavailable safe rollback, or uncertain cost coverage.

The immediate application rollback baselines are backend `li-os-release-0fc39a7` and web
`li-os-web-release-7527434`, subject to a fresh safety and compatibility check at rollout time. A
traffic rollback does not remove schema 0.42 or portfolio rows. Database recovery requires a
separately reviewed restore or corrective migration that preserves legitimate writes; never edit or
rerun migration 042 as a down migration.

## Remaining acceptance

This preparation does not close OM-010. Staging migration and coordinated application rollout,
provider-backed Calendar display, manual-price owner usability, Specialist composer staging
acceptance, physical Android phone/tablet and installed-Windows PWA checks, and a stability
observation remain outstanding. Automatic quotes, currency conversion, realized gain/loss, tax
reporting, broker synchronization, and trading remain outside this foundation.
