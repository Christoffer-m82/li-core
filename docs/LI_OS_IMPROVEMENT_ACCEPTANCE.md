# Li OS improvement blueprint acceptance

This record tracks implementation of the six packages in the
[Li OS improvement blueprint](LI_OS_IMPROVEMENT_BLUEPRINT.md). It supplements the
[personal-use v1 acceptance checklist](PERSONAL_V1_ACCEPTANCE.md); it does not replace the
[Constitution](../CONSTITUTION.md), security policy, memory policy, or release controls.

## Reviewed change set

- **Date:** 2026-09-05
- **Implementation branch:** `codex/li-os-improvement-blueprint`
- **Review baseline:** `f66993d`
- **Evaluation conditions:** synthetic fixtures and local services only; no live model, personal
  memory, external database, deployment, provider write, or metered call was used.
- **Permanent regression manifest:**
  [`li_improvement_benchmark_v1`](../backend/evaluations/improvement-benchmark-v1.json), mapping
  every required scenario R1–R18 to executable tests. R1–R14 retain the original blueprint
  coverage; R15–R18 add the Phase 2 correction paths.

The original findings were reproduced against the reviewed baseline and then covered by regression
tests. Where an existing interface already met part of a package, it was preserved and incorporated
into the acceptance scenario rather than replaced.

## Package evidence

| Package | Finding disposition and implemented guarantee | Local validation | State and remaining evidence |
| --- | --- | --- | --- |
| 1. Response safety | Reproduced. Invalid final output is never returned as accepted raw text; rejected attribution cannot leak action proposals; bounded repair retains evidence restrictions and mandatory context; current-world evidence policy runs for equivalent English and Swedish requests. | R1–R4 and R11; backend suite | **Locally verified.** Live-provider behavior remains unverified. |
| 2. Context privacy and continuity | Reproduced. Conversation messages retain explicit privacy metadata; specialist context is selected as whole, relevant, permitted messages; temporary uploads stay private to Li unless the specialist is explicitly permitted; legacy/missing privacy metadata fails closed; memory domains use exact identifiers; complete requests reserve output and mandatory-instruction capacity. | R5, R6 and R10; migrations 037–038 history rehearsal; backend suite | **Locally verified.** Migration 037 is prepared but not applied to any external database. |
| 3. Recoverable turns and actions | Reproduced. Clients supply a stable turn identity and reuse it on retry; durable turns replay completed responses, reject payload mismatch, expose in-progress/uncertain states, and do not blindly retry an uncertain effect; provider write failures resolve to explicit reconciliation-required uncertainty. | R8–R9; migration rehearsal including replay rejection; frontend and gateway retry tests | **Locally verified.** Migration 038 is prepared but not applied externally. Exactly-once behavior is not claimed for providers without reconciliation or idempotency support. |
| 4. Coherent delegation | Reproduced. Explicit requests and exclusions remain deterministic; quoted examples do not route; permitted recent context resolves English/Swedish follow-ups; relevance scoring replaces registry-order selection; simple stable questions stay with Li while current/high-risk questions still receive evidence governance; specialist packets carry objective, focused question, facts, evidence needs and success criteria. | R3, R7 and R11; bilingual/routing suites | **Locally verified.** Natural-language coverage remains bounded by tests and does not claim universal semantic understanding. |
| 5. Evaluation and observability | Reproduced. Provider calls record stage, status, elapsed time, token usage, stop reason and structured-output status without routine message content; incomplete generations fail closed; turn diagnostics expose privacy-minimized stage traces; the voice evaluator records provider metadata and preserves incomplete-run truth. | R13; benchmark-manifest validation; backend suite | **Locally verified for synthetic evaluation.** Live-model quality comparison is deliberately unrun because covered metered entitlement was not established. |
| 6. Personal-use journeys | Revised from “finish everything” to evidence-backed local completion. Chat and Specialist Workspace retries reuse stable identities; offline launch displays the public shell without caching private/auth/API responses; sign-in/photo failures remain honest; existing chat/history, files, themes, CM fallback, specialist conversations and proactive controls remain covered. | R10–R14; frontend Python and browser suites; gateway/profile suites | **Locally verified only.** Deployment, migrations, provider smoke tests, Android phone/tablet checks, Windows installed-app checks, restore drill and stable-use observation remain pending protected/operator evidence. |

## Validation record

All results below were produced on 2026-09-05 from the branch above.

| Result | Command or environment | Evidence |
| --- | --- | --- |
| PASS | Backend `python -m pytest -q` | 999 passed; two upstream Starlette/httpx deprecation warnings |
| PASS | Frontend `python -m pytest -q` | 79 passed; two upstream Starlette/httpx deprecation warnings |
| PASS | Frontend `node --test tests-js/*.test.mjs` | 74 passed |
| PASS | Native Gateway `python -m pytest -q` | 13 passed; two upstream Starlette/httpx deprecation warnings |
| PASS | Profile service `python -m pytest -q` | 103 passed, 2 skipped; skips retain their existing explicit conditions |
| PASS | Ruff and Python compilation for backend, frontend, Native Gateway and profile service | All checks passed; all application modules compiled |
| PASS | `memory/tests/validate_migrations.py` against a fresh isolated PostgreSQL 18 cluster | Versions 0.1–0.38 applied; data/RLS/ownership/role/API-denial invariants passed; migration 038 replay failed closed; replay content expiry retained a tombstone; conversation deletion cascaded |
| NOT RUN | Live model comparison | No verified included/prepaid API entitlement; a subscription alone is not proof of covered API usage |
| NOT RUN | External database, deployment and physical devices | Separately protected or owner-operated evidence; repository state cannot prove them |

The disposable PostgreSQL cluster was created inside a temporary repository directory, bound only to
localhost, and removed after the rehearsal. No Supabase or other external database was contacted.

## Security and data-integrity review

- Provider and orchestration telemetry contains stage/status/timing/usage metadata, not prompts,
  replies, hidden reasoning, personal memory, tokens, or credentials.
- Missing conversation privacy metadata is treated as non-shareable; only explicit task-share
  metadata can disclose a message to a selected specialist.
- Durable identity is bound to the request payload. Reusing an identity with different content is
  rejected, and an uncertain execution cannot be silently replayed. Replay response content expires
  after 30 days while a content-free tombstone continues to prevent duplicate execution; deleting the
  linked conversation cascades to its turn records.
- Specialists remain stateless advisers without direct tools, databases, memory mutation, registry
  authority, or action authority.
- The service worker may cache only the public application shell and approved static assets; private,
  authentication, mutation, cross-origin, and query-bearing requests remain network-only.
- The three new migrations are immutable additions and were not applied outside disposable rehearsals.

## Phase 2 correction record

- **Date:** 2026-09-05
- **Implementation branch:** `codex/li-os-phase-2-corrections`
- **Review baseline:** `1b91e70`
- **Evaluation conditions:** synthetic fixtures and a disposable localhost PostgreSQL 18 cluster;
  no live model, personal data, external database, deployment, provider write, or metered call.

| Package | Disposition and correction | Acceptance evidence | Residual limitation |
| --- | --- | --- | --- |
| A. Disclosure restrictions and memory truth | **Reproduced and corrected.** Assistant messages now derive disclosure from every used source instead of inheriting the current request's recipients; automatic memory captures retain source privacy; specialist memory packets carry provenance; Theo and the database boundary reject promotion of inferred content to confirmed truth. | R15; conversation, memory-capture and Theo regressions; migration 039 database rehearsal | Migration 039 is not applied externally. Existing records are not reclassified by this change. |
| B. Response safety and bilingual intent | **Reproduced and corrected.** Current-world evidence requirements are enforced before a direct or specialist fallback; invalid attribution cannot preserve actions; failed evidence repair is deterministic; English and Swedish negation, references, quotations and unsupported-verification claims receive matching outcomes. | R1–R4, R7, R11 and R16; orchestration and bilingual routing regressions | Deterministic tests do not establish universal natural-language understanding or live-model quality. |
| C. Durable recovery and retry | **Reproduced and corrected.** Migration 039 adds fenced attempts, monotonic action-prepared/provider-dispatched/provider-completed progress, access-time replay expiry and safe resume after a stored message. Read-only failure is not mislabelled as an external effect; an unobserved dispatch remains uncertain. Home and Workspace retain only a request fingerprint plus turn ID across refresh and issue a new ID for an edited envelope. | R8–R9, R14 and R17; actual fresh-database duplicate/conflict/lease/stale-worker rehearsal; provider-idempotency and browser retry tests | Provider operations without supported idempotency/reconciliation still remain uncertain rather than being repeated. Migration 039 is not applied externally. |
| D. Usable continuity and evaluation | **Reproduced and corrected.** The runtime prompt is compacted through a reviewed derived contract; complete estimates include schema and output reserve; conversation selection preserves whole relevant corrections under load; each specialist receives a distinct role-specific question and success constraints; the benchmark runner executes behavior paths rather than only checking test names; diagnostics contain decisions and counts, not content. | R6, R13 and R18; executable benchmark; request-budget, relevance and specialist-packet tests | Subjective live-model comparison remains unrun because covered metered entitlement was not established. |

**Layer status:** implemented locally and locally tested. CI, merge, external migration, deployment,
live-provider behavior, physical Android/Windows devices, restore drills and stable-use observation are
not established by this local record unless a later release record supplies that evidence.

### Phase 2 validation record

| Result | Command or environment | Evidence |
| --- | --- | --- |
| PASS | Backend `python -m pytest -q` | 1,028 passed; two upstream Starlette/httpx deprecation warnings |
| PASS | Frontend `python -m pytest -q` | 79 passed; two upstream Starlette/httpx deprecation warnings |
| PASS | Frontend `node --test tests-js/*.test.mjs` | 78 passed |
| PASS | Native Gateway `python -m pytest -q` | 13 passed; two upstream Starlette/httpx deprecation warnings |
| PASS | Profile service `python -m pytest -q` | 113 passed, one intentionally conditional test skipped |
| PASS | Ruff and Python compilation for all four Python components | All checks passed; application and benchmark modules compiled |
| PASS | `backend/evaluations/run_improvement_benchmark.py` | 39 backend behavior checks and 30 browser checks passed |
| PASS | `memory/tests/validate_migrations.py` against fresh disposable PostgreSQL 18 | Versions 0.1–0.39 applied; duplicate, conflict, lease, attempt-fence, progress, owner-confirmed inference, privacy, role, replay and cascade checks passed; migration 039 replay failed closed |
| NOT RUN | Live-model/provider comparison | Covered metered entitlement was not established; deterministic results do not prove subjective quality |
| NOT RUN | External migration, deployment and physical devices | Separately protected/operator evidence; local repository state cannot prove these layers |

## Remaining release work

This change set closes the six packages at the **local implementation** level. It does not establish a
deployed release or “100% complete” product. The next protected/operator stages are:

1. Review and authorize external application of migrations 037 through 039 using the
   [migration workflow](MIGRATION_WORKFLOW.md).
2. Review and authorize deployment using the [deployment workflow](DEPLOYMENT_WORKFLOW.md).
3. Run controlled live provider checks only after coverage is established without additional charge.
4. Complete the Android phone/tablet and Windows installed-app checklist, an authorized restore drill,
   and the stable-use observation required by [personal-use acceptance](PERSONAL_V1_ACCEPTANCE.md).
