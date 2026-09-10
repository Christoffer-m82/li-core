# Known risks

## Scope

This register contains risks supported by tracked repository evidence as of 2026-09-06. It does not
assert live exploitability or external configuration. Severity and acceptance require owner and,
where applicable, Heimdall review.

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

## KR-011: Chat privacy and memory-retry live acceptance remains incomplete

- **Evidence:** The [2026-09-06 acceptance corrections](PERSONAL_V1_ACCEPTANCE.md#historical-recall-privacy-correction--2026-09-06)
  reproduced historical-snippet disclosure and a separate memory-write/retry gap with synthetic
  regressions. Migration 041 and the matching application corrections are now deployed together in
  the [schema-0.41 release](releases/2026-09-06-8831381-staging.md), after a fresh authenticated
  backup, full isolated restore, migration rehearsal, authority checks, and zero-traffic candidates.
- **Impact:** The corrected staging runtime is no longer the older affected release, but provider-
  backed bilingual privacy and uncertain-effect journeys are locally verified with synthetic records,
  while applicable staging reconciliation and wider coverage remain incomplete. Previously
  affected personal records were not inspected or reclassified. A bounded live routing check also
  found that a prefixed English `Ask Nora` request invoked Nora while its Swedish `Be Nora`
  equivalent did not. That narrow routing failure is now corrected and live-retested in the
  [backend-only release](releases/2026-09-06-e46b509-staging.md); see the original
  [dated acceptance finding](PERSONAL_V1_ACCEPTANCE.md#live-bilingual-specialist-routing-finding--2026-09-06).
- **Current control:** Historical recall fails closed, memory writes are attempt-fenced, uncertain
  effects are never automatically retried. Retained `release-2746421` is schema-compatible but
  predates these fixes; it is not a safe automatic fallback for affected chat/memory traffic. Follow
  the [rollback safety gate](../README.md#rotation-and-rollback), without pretending that application
  rollback removes schema 0.41.
- **Additional rollout finding:** The existing Theo proposal API cannot preserve private-source
  metadata and its approval function creates shareable canonical memory. The
  [private-proposal guard](PERSONAL_V1_ACCEPTANCE.md#private-proposal-rollout-review--2026-09-06)
  blocks automatic proposals from private sources rather than silently dropping that restriction.
  Private-source proposal support remains unavailable; the fail-closed guard is now deployed.
  Existing proposals and memories were not inspected or changed.
- **Next review:** The prefixed Swedish routing retest passed, without closing this risk.
  The [2026-09-07 specialist-language retest](releases/2026-09-07-0fc39a7-staging.md) also passed
  narrowly. The opt-in local acceptance harness now adds EN/SV packet-boundary and integrated
  post-write uncertainty/replay evidence against a disposable schema-0.41 database with fake
  providers; it did not access staging or personal data. Use the
  [bounded acceptance procedure](TESTING_AND_AUDIT.md#kr-011-bounded-privacy-and-recovery-acceptance)
  to separate this local synthetic coverage, provider-backed isolated testing and retrospective
  owner-record assessment.
  The [bounded provider-trial preparation](TESTING_AND_AUDIT.md#provider-trial-preparation--2026-09-07)
  now adds a local write-ahead budget and rehearsed synthetic runner, but has made no live calls.
  Do not treat guard implementation or a fake-provider rehearsal as closing this risk.
  The [2026-09-09 readiness review](TESTING_AND_AUDIT.md#readiness-review--2026-09-09)
  corrected the local runner's stale schema-0.41 gate and passed the same four synthetic cases
  against schema 0.42. Real-provider execution, subsequent Workspace/capture provider coverage,
  production reconciliation and the historical-record decision remain outstanding.
  A later [bounded provider-backed result](TESTING_AND_AUDIT.md#pr-104-provider-validation-result--2026-09-09)
  passed English historical privacy but stopped before the injected recovery failure because exactly
  one governed correction dispatch could not be proven. English recovery and both Swedish cases
  remain outstanding; the retained result is not proof of no effect or permission to retry.
  The later [content-free diagnostic hardening](TESTING_AND_AUDIT.md#content-free-recovery-diagnostic-hardening--2026-09-09)
  records only allowlisted booleans at classifier, target-resolution, apply and dispatch boundaries;
  its local EN/SV fake-provider rehearsal passed. It does not resolve the retained live result and
  adds no permission or identity for another provider attempt.
  The later [unresolved-case continuation preparation](TESTING_AND_AUDIT.md#unresolved-case-continuation-preparation--2026-09-09)
  adds an exclusive one-use identity that preserves all three earlier ledgers and skips the already
  passed English privacy case. Its three-case fake-provider rehearsal passed; no live execution is
  authorized or claimed.
  The [content-free trial result](TESTING_AND_AUDIT.md#content-free-trial-result-and-explicit-recovery-fixture--2026-09-09)
  subsequently isolated an empty parsed classifier result before any governed correction dispatch.
  One real call settled; recovery and both Swedish cases remain unproven. Local fixture clarification
  and a precise pre-apply stop are fake-provider verified, not a live fix. All four live ledgers
  remain preserved; that fixture correction added no new trial identity. A separately owner-authorized
  [recovery-fixture trial preparation](TESTING_AND_AUDIT.md#authorized-recovery-fixture-trial-preparation--2026-09-09)
  now adds one exclusive identity, verified locally with all four predecessor hashes and the same
  strict limits. Its later [provider-backed result](TESTING_AND_AUDIT.md#recovery-fixture-provider-backed-result--2026-09-09)
  passed both recovery cases and Swedish privacy with seven calls. The four baseline cases now have
  local provider-backed evidence, not staging or universal-model acceptance. All five live ledgers
  remain preserved; earlier inconclusive effects are not retroactively resolved. This does not close
  the risk: subsequent Workspace/capture provider coverage, deployed reconciliation and the separate
  historical-record decision remain outstanding.
  Existing prepaid API coverage and disabled auto-reload were owner-verified for the
  bounded check; recheck coverage before later provider calls. Run the remaining bounded
  coverage without repeating the passed baseline cases. Assess previously affected records only
  through a separately authorized privacy-preserving process, without automatic deletion or retry.
  Keep voice and final acceptance gated until the remaining relevant core evidence is complete.
  The [2026-09-10 remaining-acceptance review](TESTING_AND_AUDIT.md#remaining-acceptance-review--2026-09-10)
  separates mocked later-Workspace coverage, first-turn disposable capture and baseline provider
  evidence. It proposes a bounded chained privacy/capture continuation and a separate deployed
  reconciliation gate; it does not authorize live execution or historical-record inspection. The
  local continuation now passes two connected Workspace turns per language against real disposable
  schema-0.42 storage and fake providers, including a genuinely Swedish follow-up, private answer
  propagation, specialist-packet exclusion, private capture provenance and exact-replay invariants.
  This narrows the gap but does not provide the separately gated provider-backed chained observation,
  deployed reconciliation, historical-record decision, owner/device acceptance or stability evidence.

## KR-012: Portfolio values are owner-entered and may become stale

- **Evidence:** The [Finance and Calendar workspace design](../system/FINANCE_CALENDAR_ARCHITECTURE.md)
  deliberately excludes unofficial brokerage access and unreviewed or chargeable market-data
  activation. Schema 0.42 stores an optional owner-entered current price and its timestamp.
- **Impact:** Current value and unrealized gain/loss are estimates as of the displayed entry time, not
  a live brokerage balance, tax record, or guaranteed market price. Mixed currencies cannot be
  aggregated without a reviewed FX source.
- **Current control:** The UI labels the valuation mode, timestamp, missing prices, unlike currencies,
  and unrealized result. It never claims live quotes and cannot place trades.
- **Next review:** Follow the proposed weekly-cached direction in the
  [market-data provider position](../system/FINANCE_CALENDAR_ARCHITECTURE.md#market-data-provider-position),
  then select a normalized instrument model and a source that exposes freshness, exchange, currency,
  permission/licensing, and bounded no-additional-charge coverage before implementing automatic
  quotes. Keep manual entry as the fail-safe fallback.

## KR-013: Provider transport log privacy

- **Status:** Open; correction deployed to the staging backend, historical assessment unresolved.
- **Evidence:** Synthetic Calendar tests on 2026-09-07 reproduced HTTPX INFO logs containing
  request URLs and search query text. The generic formatter's credential-name replacement does
  not remove arbitrary private queries. No historical logs or personal records were inspected;
  actual historical exposure is not established or ruled out.
- **Impact:** Provider request URLs may reveal calendar identifiers or query contents in transport
  logs. Do not retrieve raw transport logs for diagnosis or broaden access to them.
- **Mitigation:** Backend `li-os-release-db1d17c` suppresses verbose HTTPX/HTTPCore messages, replaces
  remaining transport bodies with a fixed privacy notice while retaining severity, and supplies
  allowlisted Calendar failure diagnostics. Synthetic redaction and full-backend tests passed.
- **Closure:** The reviewed rollout and bounded post-promotion controls passed. Assessment or handling
  of historical logs remains a separate privacy-preserving, exactly authorized owner decision.
  No log deletion, retention change, credential rotation or historical inspection was performed.
- **Live diagnostic evidence:** The single authorized Calendar read on 2026-09-08 produced only the
  fixed `calendar.search`, `authentication`, `oauth` and HTTP 400 fields for its exact correlation
  ID. No raw provider material or Calendar content was inspected, and no retry was made. This
  validates the corrected live diagnostic path; it does not determine historical exposure.
- **Follow-up live evidence:** The [Calendar configuration release](releases/2026-09-09-calendar-v2-staging.md)
  retained the same privacy-corrected image and completed one bounded provider-backed read after the
  matching OAuth credential references were deployed. It returned zero events; no event content was
  printed or saved, and no ERROR-or-higher log entry was found. This confirms the live transport-log
  mitigation remained compatible with a successful read; it still does not determine historical
  exposure.
- **Evidence and rollout gate:** [Calendar diagnosis](TESTING_AND_AUDIT.md#calendar-sanitized-diagnosis--2026-09-07)
  plus the [diagnostic](releases/2026-09-08-db1d17c-staging.md) and
  [successful configuration](releases/2026-09-09-calendar-v2-staging.md) releases.

## Closed risks

### KR-001: Duplicate migration number and schema version — resolved 2026-09-06

- **Previous evidence:** `021_artifact_library.sql` and `021_private_conversation_deletion.sql` both
  use the `021` prefix and claim logical version `0.21`.
- **Resolution:** `memory/migrations/manifest.json` is now the canonical machine-readable sequence.
  It applies the artifact-library migration, records the private-conversation deletion file as an
  intentional historical skip, and points to migration 025 as the restoring migration. The disposable
  database validation consumes the manifest and fails on unlisted files, duplicate applied versions,
  incomplete skip evidence or an unknown restoring migration. No historical SQL was modified.
- **Residual rule:** Migration tooling and baseline rebuilds must consume the manifest instead of
  sorting filenames. External target state must still be verified from `schema_versions`.

### KR-002: Mutable deployment secret references — resolved 2026-09-06

- **Previous evidence:** Web and retention deployment assets referenced `latest`, while the Native
  Gateway guidance required pinned numeric versions.
- **Resolution:** All deployable Cloud Run YAML uses explicit `PINNED_*_VERSION` placeholders. The
  retention and Native Gateway provisioning scripts accept only positive numeric version identifiers,
  and the deployment workflow requires a reviewed new revision for rotation. A repository regression
  test rejects `latest` from deployable YAML and PowerShell assets.
- **Residual rule:** Repository templates do not prove the currently deployed version. Each release
  record must still verify and record the rendered numeric references without exposing secret values.

### KR-010: Superseded pre-migration backup — resolved 2026-09-06

- **Evidence:** During the [2026-09-06 isolated restore drill](releases/2026-09-06-isolated-restore-drill.md),
  the passphrase protecting the existing pre-037 encrypted backup was exposed outside the repository.
  The passphrase and backup are not tracked in Git.
- **Impact:** Anyone who obtains both that superseded encrypted file and the exposed passphrase could
  decrypt it. Successful restoration does not restore confidentiality to that copy.
- **Resolution:** A new independently encrypted backup passed authentication, catalogue
  validation, a full isolated schema-0.39 restore, and authority-boundary checks in the
  [2026-09-06 drill](releases/2026-09-06-isolated-restore-drill.md). With owner authorization, the
  exact superseded local file was deleted after its replacement's hash and presence were checked.
  A follow-up existence check confirmed the old file was absent and the replacement remained.
- **Residual rule:** Never reuse the exposed passphrase. Keep the validated replacement until the
  backup retention policy or a separately authorized replacement process says otherwise.

## Review cadence

Review this register before releases that touch a listed boundary and during significant security,
architecture, migration, or provider changes. Close a risk only when the evidence and control have
changed; link the authoritative decision or test result that justifies closure.
