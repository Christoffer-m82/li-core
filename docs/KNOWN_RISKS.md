# Known risks

## Scope

This register contains risks supported by tracked repository evidence as of 2026-09-02. It does not
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

## KR-005: Migration validation is largely static in the repository

- **Evidence:** Several backend tests assert migration text and invariants, but there is no tracked
  general migration runner, disposable PostgreSQL/Supabase test harness, or CI workflow.
- **Impact:** SQL syntax, upgrade behavior, RLS, ownership, grants, trigger behavior, and data
  preservation may fail only during manual rehearsal or application.
- **Current control:** Transactional migrations include explicit guards and assertions; policy
  requires backup, non-production rehearsal, integrity checks, and independent review.
- **Next review:** Implement [OM-008](OPEN_MILESTONES.md) without granting CI production authority.

## KR-006: Dependency resolution is not fully reproducible

- **Evidence:** Python project dependencies use bounded ranges in three `pyproject.toml` files; no
  lock file is tracked. Android dependencies are versioned, but no Gradle wrapper is tracked.
- **Impact:** A clean build can resolve newer transitive packages or depend on host tooling, creating
  build drift and supply-chain review gaps.
- **Current control:** Major-version bounds, container builds, and explicit minimum tool versions.
- **Next review:** Adopt reviewed lock/constraint and build-tool pinning with an update process that
  preserves dependency security review.

## KR-007: Live backup, IAM, scheduler, and migration state is not repository-verifiable

- **Evidence:** The repository contains desired-state templates, policies, and operator guides but no
  safe captured attestation of current external state.
- **Impact:** Maintainers may mistake documented intent or a commit message for an applied migration,
  healthy backup, paused scheduler, private service, or least-privilege binding.
- **Current control:** [CODEX.md](../CODEX.md) requires evidence labels; deployment and migration
  workflows require dated authorized checks.
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

## Review cadence

Review this register before releases that touch a listed boundary and during significant security,
architecture, migration, or provider changes. Close a risk only when the evidence and control have
changed; link the authoritative decision or test result that justifies closure.
