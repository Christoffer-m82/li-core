# Known risks

## Scope

This register contains risks supported by tracked repository evidence as of 2026-09-05. It does not
assert live exploitability or external configuration. Severity and acceptance require owner and,
where applicable, Heimdall review.

## KR-001: Duplicate migration number and schema version

- **Evidence:** `memory/migrations/021_artifact_library.sql` and
  `memory/migrations/021_private_conversation_deletion.sql` both use the `021` prefix and record
  `0.21`. Migration 025 states that it restores private conversation deletion after the collision.
- **Impact:** A filename-driven runner or operator may assume a total order that the logical version
  table cannot represent, skip one file, or misread target state.
- **Current control:** Later migrations have explicit schema prerequisites; migration 025 restores the
  deletion capability. The [migration workflow](MIGRATION_WORKFLOW.md) requires reading dependencies
  and verifying database state rather than trusting prefixes.
- **Next review:** Any migration automation or baseline rebuild must define and test the canonical
  handling of both historical 021 files without modifying them.

## KR-002: Some deployment assets reference `latest` secret versions

- **Evidence:** `deployment/cloud-run/web-service.template.yaml`,
  `deployment/cloud-run/retention-job.template.yaml`, and
  `deployment/cloud-run/provision-retention.ps1` contain `latest` secret references, while the Native
  Gateway guide explicitly requires pinned numeric versions.
- **Impact:** A new secret version may alter a future revision or job rollout without the reviewed
  version being obvious in the repository release record.
- **Current control:** Secret values stay outside Git; the deployment workflow requires inspected
  references and an explicit release record.
- **Next review:** Standardize a pinned-version rollout and rotation policy across services, then
  update the authoritative deployment guides and templates together.

## KR-003: In-memory backend rate limiting is per instance

- **Evidence:** The [backend deployment guide](../README.md#one-time-google-cloud-setup) describes the
  limiter as a basic abuse control rather than a distributed quota.
- **Impact:** Limits are not globally consistent across instances and are not a complete abuse or
  denial-of-service control.
- **Current control:** Initial maximum instance guidance is bounded, and the tracked deployment
  guidance requires the service to remain IAM-private. Live enforcement requires operator evidence.
- **Next review:** Reassess before multi-user or materially higher-volume operation; see
  [OM-007](OPEN_MILESTONES.md).

## KR-004: Native attestation is not configured in the documented deployment state

- **Evidence:** The [Native Gateway deployment guide](../deployment/cloud-run/native-gateway.md)
  instructs operators to report attestation as `not_configured`.
- **Impact:** Authentication and installation revocation exist, but the gateway cannot rely on a
  configured platform-attestation signal.
- **Current control:** Owner allowlisting, Google OIDC bootstrap, short-lived access tokens, refresh
  rotation/revocation, scoped backend token, and gateway rate controls are documented in the
  [Native Gateway ADR](../system/NATIVE_GATEWAY_ARCHITECTURE.md).
- **Next review:** Complete or explicitly accept [OM-002](OPEN_MILESTONES.md).

## KR-006: Android checksum refreshes require a trusted review

- **Evidence:** The Android dependency graph is version-locked and verified against tracked SHA-256
  metadata, but signature verification is not enabled. Gradle-generated checksums originate from the
  configured artifact repositories during an intentional refresh.
- **Impact:** A compromised artifact first encountered during an approved refresh could be accepted
  if its lock and checksum changes are committed without adequate provenance review.
- **Current control:** CI resolves all Android configurations in strict verification mode before
  compiling and testing. The [testing procedure](TESTING_AND_AUDIT.md#native-checks) requires explicit
  regeneration and review of every dependency version and checksum change.
- **Next review:** Evaluate PGP signature verification and independently published checksums for
  critical dependencies before the native proof of concept becomes a distributed product.

## KR-007: Live backup, IAM, scheduler, and migration state is not repository-verifiable

- **Evidence:** The repository contains desired-state templates, policies, and operator guides but no
  safe captured attestation of current external state.
- **Impact:** Maintainers may mistake documented intent or a commit message for an applied migration,
  healthy backup, paused scheduler, private service, or least-privilege binding.
- **Current control:** [CODEX.md](../CODEX.md) requires evidence labels; deployment and migration
  workflows require dated authorized checks. The
  [2026-09-05 staging release](releases/2026-09-05-a864076-staging.md) records redacted schema,
  backup, deployment, rollback, IAM-continuity and smoke evidence without treating Git as the source
  of live truth.
- **Next review:** Maintain redacted, non-secret operational evidence in an approved system and link
  it from release records rather than embedding sensitive state here.

## KR-008: Proactivity is safe only while activation state stays coordinated

- **Evidence:** The [proactivity guide](../deployment/cloud-run/governed-proactivity.md) separates a
  paused scheduler job from database `preview_only`/enabled state and requires operators to resume or
  pause the matching job.
- **Impact:** Drift between scheduler and durable rhythm state can create missed runs, unexpected
  invocations, or confusing operator status even though database checks reject disabled execution.
- **Current control:** Dedicated invoker identity, database-side rejection, durable idempotency,
  quiet hours, and owner approval.
- **Next review:** Activation and stand-down procedures should verify both planes and retain evidence
  per rhythm.

## KR-009: Recoverable-turn provider outcomes still need live fault validation

- **Evidence:** Migrations 037 through 039 and the recoverable-turn runtime are deployed together in
  the [2026-09-05 staging release](releases/2026-09-05-a864076-staging.md). Deterministic and disposable
  database tests cover uncertain action state, turn claims, replay denial and stale-worker fencing;
  an authenticated live provider fault was not intentionally induced during rollout.
- **Impact:** A provider that neither supports idempotency nor exposes reconciliation can still leave
  an externally dispatched write uncertain. Li must report that uncertainty instead of repeating the
  action or claiming success.
- **Current control:** The target schema is 0.39, the matching backend image is deployed, role and
  invalid-credential denials passed, and rollback remains available. Application tests fail closed
  for unobserved provider outcomes.
- **Next review:** Run a controlled, no-additional-charge, authenticated fault-injection smoke test
  against a non-destructive provider fixture and record reconciliation behavior for the deployed
  release.

## Review cadence

Review this register before releases that touch a listed boundary and during significant security,
architecture, migration, or provider changes. Close a risk only when the evidence and control have
changed; link the authoritative decision or test result that justifies closure.
