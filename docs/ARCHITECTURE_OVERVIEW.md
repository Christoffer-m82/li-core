# Architecture overview

## Purpose and authority

This document is a repository-oriented map for maintainers. The authoritative design remains
[Li OS Architecture](../ARCHITECTURE.md), supplemented by the implementation and policy documents
linked below. This overview records what is present in this repository; it does not prove live
deployment state.

## Runtime shape

```text
Browser ──> Web BFF ───────────────┐
                                   │ Cloud Run IAM + Li authority token
Native app ──> Native Gateway ─────┤
                                   v
                              Private Backend
                         ┌─────────┼──────────┐
                         v         v          v
                    PostgreSQL  Providers  Private objects
                    role APIs   / models    in Cloud Storage

Cloud Scheduler ──> private rhythm endpoint
Retention Scheduler ──> private retention job ──> scoped DB API + private objects
```

The diagram shows logical trust paths, not a guarantee that every component is deployed or enabled.

## Components

| Component | Repository location | Responsibility | Primary source |
| --- | --- | --- | --- |
| Li definition and routing | `CONSTITUTION.md`, `li/`, `agents/` | Identity, operating rules, delegation, permissions, and registry | [Constitution](../CONSTITUTION.md), [operating rules](../li/operating-rules.md) |
| Private backend | `backend/` | FastAPI API, orchestration, governed actions, provider adapters, runtime data, and health/readiness | [README](../README.md) |
| Browser BFF and UI | `frontend/` | Google-authenticated session boundary, server-side backend credentials, and static mobile-first UI | [Frontend README](../frontend/README.md) |
| Native Gateway | `native-gateway/` | Native bootstrap/session boundary and scoped calls to private backend routes | [Native Gateway ADR](../system/NATIVE_GATEWAY_ARCHITECTURE.md) |
| Native place clients | `native/android/`, `native/ios/` | Coarse-place proof-of-concept providers and token storage abstractions | [Mobile location ADR](../system/MOBILE_LOCATION_ARCHITECTURE.md) |
| Canonical and runtime data | `memory/` | Baseline schema, immutable SQL migrations, permissions, and storage policy | [Memory Storage Policy](../memory/storage-policy.md) |
| Private artifact retention | `backend/app/artifacts.py`, `backend/app/retention_job.py`, deployment assets | Governed object storage lifecycle and least-privilege cleanup | [Artifact retention](../deployment/cloud-run/artifact-retention.md) |
| Deployment assets | `deployment/cloud-run/` | Reviewable Cloud Run templates and narrowly scoped provisioning scripts | [Deployment workflow](DEPLOYMENT_WORKFLOW.md) |

## Data and control planes

The repository separates these concerns:

- **Definition plane:** Git-tracked constitution, policies, registries, code, schemas, and templates.
- **Data plane:** PostgreSQL-backed canonical memory, conversations, tasks, runtime governance data,
  and private object bytes. The repository does not establish the live database provider or state.
  See [Memory Storage Policy](../memory/storage-policy.md).
- **Secret plane:** deployment secret manager and runtime secret references; secrets do not belong in
  Git or agent context. See [Security & Privacy Policy](../system/security-policy.md).
- **Operator plane:** owner-controlled migrations, deployment, IAM, scheduler activation, rotation,
  rollback, backup, and recovery.

## Important implementation boundaries

- The browser receives neither Cloud Run invocation credentials nor Li backend tokens; the BFF owns
  that hop. See the [frontend security architecture](../frontend/README.md#security-architecture).
- The Native Gateway has no database credential and uses a dedicated backend token. See the
  [Native Gateway deployment gate](../deployment/cloud-run/native-gateway.md).
- The backend uses distinct database connections for application, Theo, and owner-confirmation
  authority in `backend/app/database.py`.
- Provider capabilities are held by the backend and exposed through Li-owned policy boundaries;
  specialists do not receive raw provider credentials.
- Browser and Native Gateway chat contracts can carry a stable owner-supplied turn identifier.
  Migration 038 prepares owner/payload-bound claim, replay, uncertainty, and replay-content-expiry
  functions; repository presence does not prove that this migration is applied externally.
- Migration 037 prepares conversation privacy metadata in the history API. The backend preserves those
  labels and selects whole permitted messages and explicitly disclosed temporary uploads for each
  specialist, while Li retains the private full-conversation role defined by the Constitution.
- The retention job uses a dedicated database capability and object role. See
  [artifact-retention identities](../deployment/cloud-run/artifact-retention.md#identities-and-least-privilege).
- Governed native capabilities are catalogued in
  [ADR-0035](../system/GOVERNED_LI_NATIVE_SYSTEMS.md), while voice is currently described as a
  foundation in [VOICE_ARCHITECTURE.md](../VOICE_ARCHITECTURE.md).

## Change routing

| Change | Read before editing | Required companion review |
| --- | --- | --- |
| Identity, routing, agent, or permission | Constitution, architecture, `li/`, relevant YAML | Regression and permission-integrity review |
| Backend or provider | README, relevant module and tests | Auth, least privilege, failure mode, and provider-data review |
| Browser or session | Frontend README and security tests | BFF credential isolation and session review |
| Native or gateway | Native ADRs and platform README | Token lifecycle, revocation, privacy, and gateway-boundary review |
| Schema or database authority | Storage policy and migration workflow | Owner, grants, RLS, version gate, backup, and rollback review |
| Deployment | Relevant deployment doc and template | Environment evidence, pinned inputs, IAM diff, smoke test, and rollback |
