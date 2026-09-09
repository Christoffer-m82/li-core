# Testing and audit

## Purpose

Use the smallest relevant checks during development and the full applicable matrix before release.
This file documents repository commands and evidence expectations; it does not claim that a check
passed unless a dated work report records the result.

## Python component checks

The four Python projects use Python 3.12+, pytest, and Ruff as declared in their `pyproject.toml`
files. Run them from their own directories because three projects expose a top-level package named
`app` and the profile service uses isolated top-level modules.

```text
cd backend
python -m ruff check app tests
python -m pytest
python -m compileall app

cd ../frontend
python -m ruff check app tests
python -m pytest
python -m compileall app
node --test tests-js/*.test.mjs

cd ../native-gateway
python -m ruff check app tests
python -m pytest
python -m compileall app

cd ../profile-service
python -m ruff check .
python -m pytest
python -m compileall -q .
```

Each component tracks a universal `uv.lock`. With uv 0.12.9, run `uv sync --locked --extra dev`
inside the component before these commands, and prefix commands with `uv run --locked` to use the
locked environment. After an intentional dependency change, regenerate that component's lock with
`uv lock`, review the resolved-version and source changes, and rerun its checks. CI rejects a stale
lock. The three deployed components' production Dockerfiles use the same locks with development
dependencies excluded; the profile-service remains a disabled foundation without a production image.
CI builds each production image from the repository root to verify that path. The uv build binary is pinned by
version and immutable image digest, as is the shared Python base image. Review and update each
readable version together with its digest, keep the CI Python patch version synchronized with the
container base, rebuild all three images, and inspect the source manifest before accepting a refresh.
Do not copy production `.env` values into a development shell; use placeholders and synthetic data.
The frontend Node tests execute the dependency-free browser voice adapter and its real Li Web event
flow against controlled DOM and Web Speech API fakes. They cover microphone-button transcription,
the single normal-chat request boundary, cancel-before-send, timeout, permission/no-speech failure,
synthesis, and language selection. They never request a microphone or transmit audio.

## Native checks

- iOS package: from `native/ios/`, run `xcodebuild build -scheme LiNativePOC -destination
  "generic/platform=iOS" CODE_SIGNING_ALLOWED=NO`, then run `xcodebuild test -scheme LiNativePOC
  -destination "platform=macOS,variant=Mac Catalyst" CODE_SIGNING_ALLOWED=NO` with Xcode 16.4.
- Android library: from `native/android/`, first run `./gradlew --no-daemon
  --dependency-verification strict :app:dependencies --quiet` to resolve and validate every
  configuration, then run `./gradlew --no-daemon --dependency-verification strict
  testDebugUnitTest`. Use JDK 17 and an Android SDK that includes compile SDK 35. On Windows, use
  `gradlew.bat` instead. The tracked wrapper pins Gradle 8.9 and verifies the downloaded distribution
  checksum. `app/gradle.lockfile` pins the resolved module versions, and
  `gradle/verification-metadata.xml` verifies artifact and metadata SHA-256 checksums.

After an intentional Android dependency or plugin change, run `./gradlew --no-daemon
--write-locks --write-verification-metadata sha256 :app:dependencies`, review every lock and checksum
change as supply-chain input, then rerun the strict dependency check and unit tests. Generated
checksums establish continuity after review; they are not by themselves proof of publisher identity.

Repository CI runs both checks on isolated macOS and Linux hosts. These checks compile the iOS and
Android proof-of-concept libraries and run their unit tests; they do not replace signed-app,
simulator/device, permission-flow, or staged Native Gateway integration testing. The macOS job
selects `/Applications/Xcode_16.4.app/Contents/Developer` explicitly and fails before compilation if
the hosted runner no longer provides Xcode 16.4.

External GitHub Actions in repository workflows are pinned to immutable 40-character commit SHAs;
the adjacent release comment keeps the intended version readable. For an intentional action update,
resolve the official upstream release tag to its commit, review the upstream release and diff, update
the SHA and comment together, and let the repository audit reject any mutable tag reference.

Workflow service and container images retain a readable version tag and append the registry's
immutable SHA-256 index digest. For an intentional image update, resolve the published multi-platform
index, review its platform manifests and provenance, update the tag and digest together, and let the
repository audit reject a tag-only image reference.

Absence of a local platform toolchain is a skipped check, not a pass.

## Documentation checks

For Li voice or language changes, also use the
[English and Swedish conversation evaluation](LI_CONVERSATION_EVALUATION.md).
Offline prompt-wiring tests do not establish real-model conversational quality.
For request-trigger changes, also run the paired checks in
[English and Swedish request handling](BILINGUAL_REQUEST_HANDLING.md).

The permanent synthetic regression manifest for the six
[Li OS improvement packages](LI_OS_IMPROVEMENT_BLUEPRINT.md) is
[`backend/evaluations/improvement-benchmark-v1.json`](../backend/evaluations/improvement-benchmark-v1.json).
Its validator requires every R1–R14 scenario to map to an existing executable test:

```text
cd backend
python -m pytest tests/test_improvement_benchmark.py
```

These fixtures prove deterministic safety, privacy, recovery and UI contracts. They do not establish
live-model conversation quality, deployed behavior or physical-device acceptance. Provider-backed
evaluation remains governed by [Li conversation evaluation](LI_CONVERSATION_EVALUATION.md).

For every Markdown change:

1. Parse all relative Markdown links, ignore URL fragments for filesystem resolution, and confirm
   each target file exists with exact path casing.
2. Check referenced headings when an anchor is used.
3. Search the changed text for stale filenames and claims of live state.
4. Prefer a source link over copied policy or deployment prose.
5. Review the rendered structure for readable tables, code blocks, and link labels.

## Migration checks

Follow [Migration workflow](MIGRATION_WORKFLOW.md). Static SQL tests are necessary but not sufficient:
they do not prove PostgreSQL syntax, transactional behavior, RLS, grants, ownership, or upgrade from
the target environment's actual state. The repository CI applies the explicit historical manifest
in `memory/tests/validate_migrations.py` to a fresh disposable PostgreSQL service and checks version
history, representative data preservation, RLS, ownership, allowed API access, denied direct table
access, and replay rejection. This isolated rehearsal does not prove the state of any external
database; record separately whether an authorized target-specific rehearsal was run.

Before an authorized migration-042 backup, add `-RequirePre042` to the encrypted-backup creation
command. The gate must pass against schema 0.41 before the encryption prompts appear. Its success is
only source preflight evidence: archive authentication, a full isolated restore at schema 0.41, the
exact migration rehearsal, post-migration authority tests, and target-specific validation remain
separate required results.

The tracked [migration-042 restore-and-rehearsal tool](../memory/backup-tools/rehearse-migration-042.ps1)
combines the full isolated restore with the exact migration hash and synthetic portfolio behavior.
It must run against a uniquely named localhost-only disposable target and retain that target for
explicit review. A pass proves only the supplied encrypted archive and isolated target; it does not
prove or authorize staging state.

## Security and privacy audit

Use [Security boundaries](SECURITY_BOUNDARIES.md) and the authoritative
[Security & Privacy Policy](../system/security-policy.md). At minimum review:

- authentication and authorization separately;
- allowed and denied role/function/table access;
- secrets in source, diff, logs, fixtures, and generated artifacts;
- prompt/tool/provider input as untrusted data;
- sensitive-data minimization, redaction, retention, deletion, and backup limitations;
- idempotency, replay, stale approval, and race behavior;
- failure modes, revocation, kill switches, and rollback; and
- dependency/supply-chain changes and container runtime privilege.

## KR-011 bounded privacy and recovery acceptance

**Reviewed 2026-09-07; local synthetic harness implemented, not live-test authorization or
completion.** Use the
[personal-use checklist](PERSONAL_V1_ACCEPTANCE.md) as the completion ledger and
[KR-011](KNOWN_RISKS.md#kr-011-chat-privacy-and-memory-retry-live-acceptance-remains-incomplete)
as the risk record. The [current release](releases/2026-09-07-0fc39a7-staging.md) proves rollout and
one Swedish specialist exchange, not the privacy/recovery cases below.

### Existing evidence and remaining gaps

| Boundary | Existing executable evidence | Still required |
| --- | --- | --- |
| Historical recall and later Workspace disclosure | `test_historical_recall_stays_private_in_workspace_and_derived_outputs` in [chat acceptance tests](../backend/tests/test_personal_v1_chat_acceptance.py), plus the opt-in [local acceptance harness](../backend/tests/test_local_acceptance_harness.py): EN/SV, real disposable database history/recall/capture paths, fake-provider packet inspection, private answer/capture metadata, and idempotent replay | Provider-backed synthetic run with the same packet-boundary observation; local fake-provider evidence does not establish provider-backed behavior |
| Private-source proposals | `test_proposal_cannot_drop_source_privacy` and `test_every_memory_mutation_is_guarded_immediately_before_write` in [capture tests](../backend/tests/test_memory_capture.py), plus HTTP capture-error tests | Preserve rejection before writes/markers; live classifier behavior is separate. Full private-proposal support remains unavailable |
| Failure after memory write | `test_memory_change_then_model_failure_is_not_safe_to_repeat`, deferred-capture and uncertain-retry tests in [recovery tests](../backend/tests/test_recoverable_turns.py), plus the opt-in [local acceptance harness](../backend/tests/test_local_acceptance_harness.py): EN/SV, real disposable database correction/write, injected post-write fake-model failure, uncertain response, and zero additional writes or fake-provider calls on exact replay | Provider-backed uncertainty wording and reconciliation remain; no live failure was induced in the owner's environment |
| Process loss and authority fencing | `validate_memory_effect_fence` in the [migration harness](../memory/tests/validate_migrations.py): invalid/stale identities, expired lease, uncertainty, permitted/denied roles | Preserve existing rehearsal evidence; do not relabel it as a live provider failure or rerun a personal backup restore solely for this check |
| Previously affected records | No retrospective assessment performed | Separate exact authorization and owner-controlled privacy-preserving assessment, or explicit residual-risk decision; new tests cannot certify old records |

The combined focused local regression run passed 117 tests; its mocked complete-request budget
subset also passed all 5 tests when run alone. The full normal backend suite passed 1,084 tests and
skipped the four deliberately opt-in database cases, with the upstream Starlette/AnyIO warning
visible:

```text
cd backend
python -m pytest tests/test_personal_v1_chat_acceptance.py tests/test_recoverable_turns.py tests/test_memory_capture.py tests/test_conversation_history.py tests/test_li_orchestration.py tests/test_governed_systems.py tests/test_context_privacy_migration.py tests/test_complete_request_budget.py -q
python -m pytest tests/test_complete_request_budget.py -q
python -m pytest -q
```

The opt-in runner then passed four integrated EN/SV cases against a dedicated localhost-only
`li_os_kr011_acceptance` database after the complete tracked migration manifest reached schema 0.41.
It used fake specialist, classifier and synthesis providers. The runner verified that selected private
history reached Li but not the complete specialist packet; derived history and memory stayed private;
one real disposable correction/write followed by a fake-model failure became uncertain; and exact
replay made no additional writes or fake-provider calls. The named disposable container and its
synthetic data were removed after the run. CI repeats this harness only after creating the dedicated
database and applying the manifest. No live provider call, personal-record read, staging migration,
deployment or backup access occurred. This is local integration evidence, not a provider-backed or
deployed-environment result.

### Entry controls for a future trial

1. Name the exact source/image, test environment, synthetic fixtures, endpoints, expiry and operator.
   Use an isolated database initialized from the tracked manifest, never a copy of personal backups.
   A new conversation in owner staging is **not** an isolation boundary: retrieval can reach other
   conversations or canonical memory. Do not use owner staging for these seeded/fault cases.
2. Verify a separate test configuration cannot access owner Supabase, personal files, Calendar,
   Gmail, research or other write providers. Keep Li, Theo and owner-confirmation authorities separate.
   Do not change live IAM or introduce a second active production user to obtain test isolation.
3. Use existing fixture concepts, with clearly fictional notebook markers and unique run IDs in
   separate EN/SV cases. Seed only the disposable store; verify its fixture IDs before any mutation.
   Capture specialist packets only inside this synthetic environment. Record marker-presence booleans,
   source hashes, status codes and counts rather than raw prompts or private content.
4. Reuse the reviewed opt-in local runner for isolation and packet/effect observations. Its fake
   providers deliberately make no network calls. The [provider trial preparation](#provider-trial-preparation--2026-09-07)
   adds a test-only per-trial call/token guard; recheck it before live use. It counts classifier, specialist, synthesis and fallback
   calls, enforces input/output ceilings, and stops before the next call would exceed the approved
   allowance. The existing complete-request budget guard and five mocked regressions cover each
   individual model request, but do not by themselves impose the proposed whole-trial call ceiling.
   No automatic network retries. Do not modify the live runtime to add diagnostic packet logging.
5. Obtain exact approval for that environment, synthetic seeding/mutations, fault point and live
   calls before execution. Verify current prepaid balance, disabled auto-reload, provider/model terms
   and bounded worst-case cost; a previous balance or chat subscription is insufficient.
   Suggested first privacy batch: at most **4 chat turns and 16 underlying model calls**, with a
   separately calculated token/cost ceiling. If normal orchestration exceeds either bound, stop;
   do not weaken behavior or silently extend the budget. This proposed ceiling is not spend approval.
6. Secret entry must use a reviewed masked local prompt; no secret values in chat, arguments, logs
   or Git. If any infrastructure provisioning or deployment is needed, obtain its exact approval
   separately. No new paid service or automatic billing is authorized by this plan.

### Provider trial preparation — 2026-09-07

The owner separately authorized one combined isolated EN/SV privacy/recovery batch with **4 new
chat identities, 16 underlying model calls and USD 0.50 maximum prepaid consumption**. This is not
standing live-test or deployment authorization. The read-only Anthropic billing page showed **USD
11.99, auto-reload off**, on 2026-09-07; remeasure before execution if that observation is stale.
No metered call was made during preparation.

The opt-in [runner](../backend/acceptance/run_provider_trial.py) reuses the tracked migration validator
and CI-pinned Supabase PostgreSQL image. It creates only `li-os-kr011-provider-trial-20260907`,
publishes PostgreSQL on `127.0.0.1:55443`, and uses `li_os_kr011_provider_acceptance` with three distinct
synthetic runtime-role passwords. It pins Docker to a local socket rather than an inherited remote
context, refuses an existing container, uses no host data mounts or
backups, ignores `.env` and inherited provider/database/proxy settings, and removes only its returned
container ID and disposable volume in `finally`. An interrupted process may require exact-ID cleanup;
never infer that cleanup ran after a hard process kill.

The [case driver](../backend/acceptance/provider_trial.py) uses the real classifier, specialist,
synthesis, HTTP and database paths. A synthetic identity prompt replaces the owner's identity;
this tests runtime privacy composition, not production personality or general language quality.
The four-turn authorization is allocated to **one historical-privacy and one recovery turn per
language**. Subsequent Workspace turns and derived capture remain covered by the existing local
harness; this smaller provider batch does not establish their provider-backed acceptance. The
recovery fault is local response-delivery failure after a real provider response and a verified
synthetic correction, not a provider outage or a staging fault. Exact replay must cause no provider
call and no canonical-schema fingerprint change, including proposal/version/audit tables. Capture
the fingerprint immediately around replay, before reconciliation reads add their legitimate audit
entries. Never reset uncertain identities to obtain a passing outcome.

The [write-ahead guard](../backend/acceptance/trial_budget.py) exclusively creates a fixed live ledger
at `output/acceptance/kr011-provider-20260907.jsonl`; an existing ledger blocks a fresh run. Preserve
it even after failure and reconcile before any further authorization. The ledger contains only
hashes, counts, reservations and usage, not keys, requests or responses. All SDK retries are disabled.
Only first-party `claude-sonnet-5` text requests are allowed; tools, streaming, caching, extended
thinking, custom endpoints and premium request options are excluded. Each call is limited to 100,000
serialized UTF-8 bytes and 2,048 output tokens. Reservations use bytes plus 16,384 envelope tokens,
at conservative USD 3/15 per million input/output tokens, and are durably recorded before dispatch.
Successful validated usage reduces a reservation; unknown outcomes retain it and stop the trial.
These are conservative client-side reservations, not an account-level billing limit or a guarantee
against future provider pricing changes. Recheck terms before live use. The provider's
[pricing table](https://platform.claude.com/docs/en/about-claude/pricing) on 2026-09-07 lists Sonnet 5
at USD 2/10 per million tokens. Existing app chars/4 estimates are not used as the trial's cost bound.

Run the default fake-provider rehearsal from the repository using the existing isolated Python:

```powershell
& "$env:TEMP\li-core-httpx2-backend\Scripts\python.exe" .\backend\acceptance\run_provider_trial.py
```

Live execution additionally requires `--live --prepaid-usd <fresh-observed-balance>` plus
`--balance-verified-at <UTC-ISO-timestamp> --auto-reload-off`. These flags attest read-only evidence;
they do not change billing settings. Coverage must be at least USD 1.00 and less than one hour old.
The script requests the existing Anthropic API key through a private masked terminal prompt only
after local preparation. It never reads the key from Git, `.env`, cloud secrets, or chat, nor sends
it to a model; the SDK uses it only for normal authenticated Anthropic HTTPS requests. No raw SDK
exceptions or tracebacks are printed. Run in a private terminal, not a captured assistant terminal.

Preparation evidence: 30 guard/isolation tests passed; the four-case fake-provider runner passed
with 10 mock model calls after the full migration manifest passed. Early dry rehearsals exposed
an overly long recall fixture and an audit fingerprint taken after a reconciliation read; both
test-harness issues were corrected before any live calls. Each disposable container was removed.
The full backend suite passed 1,113 tests before the additional local-Docker regression (which passed
in the 30-test focused run), with four existing opt-in tests skipped and the upstream
Starlette/AnyIO warning visible. Fake usage/cost numbers are simulated, not actual spend. The runner
is **locally implemented and rehearsed, not provider-backed or deployed acceptance**.

### Readiness review — 2026-09-09

At review baseline `fb22842`, the runner applied the current manifest through schema 0.42 but
required runtime health to equal 0.41. A default fake-provider rehearsal reproduced
`runtime_database_health_failed` before any provider dispatch; its earlier printed 0.41 message
was a hard-coded label, not measured schema evidence. The runner now compares restricted runtime
health with the final logical version in the manifest it applied, and prints success only after
that comparison passes. The complete migration validator still runs first; a missing or mismatched
health version stops the trial before private credential entry.

The corrected four-case EN/SV rehearsal passed at schema 0.42 with **10 fake model calls**. It proved
private markers present for Li and absent from Nora's complete packet, private derived history,
one synthetic correction before an injected delivery failure, uncertainty, and unchanged canonical
fingerprints with no additional fake-provider call on exact replay. Both disposable containers
created during reproduction and validation were removed by their exact returned IDs. There was no
live trial ledger at the fixed path when checked; no ledger was deleted or reset. This is local
fake-provider evidence only. The displayed simulated cost is not actual consumption.

Validation: **34 trial budget/isolation tests passed**, including current-manifest acceptance and
older, unexpected and missing runtime-schema rejection; **1,171 backend tests passed**, with four
intentional opt-in skips. The upstream Starlette/AnyIO warning remained visible. No production
runtime, migration file, provider configuration or authority changed.

The next proposed trial retains the existing four-case allocation and fixed ledger: one privacy
and one recovery turn per language, **4 new turns / 16 underlying calls / USD 0.50 maximum**.
It requires new exact authorization, current prepaid balance and pricing/coverage verification,
disabled auto-reload, and the existing masked credential prompt. Do not run the earlier dated
operator wrapper with stale balance evidence. The current continuation authorizes local preparation
only. Subsequent Workspace and derived-capture provider cases remain outside that four-turn batch.

| Evidence layer | Disposition after this review |
| --- | --- |
| Local fake providers and real disposable database | Passed at schema 0.42; earlier schema-0.41 results remain historical evidence |
| Local real providers | Still unexecuted; prompt/classifier output and provider interaction remain unverified for these cases |
| Deployed privacy/recovery correction | Recorded in prior releases; this local rehearsal does not reverify Cloud Run or owner data |
| Reconciliation | The isolated driver proves the same synthetic correction record and unchanged replay fingerprint. It does not establish a production reconciliation endpoint or permission to reset an uncertain turn |
| Historical owner records | Unassessed; needs separately scoped owner review or an explicit residual-risk decision |
| Device, owner and stable use | Open; no new owner observations were supplied |

For the proposed recovery case, classify the isolated result as **effect observed** only after the
same fixture record, source-turn identity and fingerprint checks pass. Failure to find a result is
**unresolved**, not proof of no effect. A no-effect finding would require positive evidence that
the write never dispatched or committed; it is not an outcome this post-write fixture aims to prove.
The model response is deliberately withheld after it returns, so the case exercises the application's
deterministic uncertainty response; do not label it a test of model-generated uncertainty wording.
Never reset the ledger or turn, submit a replacement identity, or infer safe retry from a 503.

### First provider attempt and safe checkpoints — 2026-09-09

The owner ran the authorized local trial after read-only verification of USD 11.99 prepaid
credit and disabled auto-reload at 13:09 UTC. The fixed ledger records two new turn identities,
four reservations and four settled usages: 7,925 input and 2,262 output tokens. Its conservative
USD 3/15 rate bound totals **USD 0.057705**, not a remeasured invoice or account balance.
The trial stopped at `correction_not_completed`; the owner-provided output confirms cleanup of
the disposable database/container/volume. A subsequent attempt stopped at expired coverage
before dispatch. The original ledger remains intact; no further live trial is authorized here.

Control-flow and ledger evidence imply the English privacy case completed before the English
recovery precondition failed. This older runner did not persist completed-case observations.
English recovery and both Swedish cases remain unproven. The failure means an exact-value lookup
did not return exactly one expected row; it does **not** prove no correction occurred. The
classifier contract permits a concise memory statement, whereas the fixture requires the bare
synthetic marker. Local EN/SV fixtures demonstrate that a statement containing that marker fails
the equality assertion. That is a plausible harness mismatch, not the established cause of the
discarded live result; raw provider output and database contents were not retained.

The runner now durably checkpoints completed cases and records only fixed-schema booleans before
the correction assertion: unique exact value, marker presence in the bounded lookup, and a source
reference ending in the current synthetic turn identity. These diagnostics do not relax the
assertion, establish no-effect from an empty lookup, or replace the later record/source/fingerprint
reconciliation checks. Arbitrary diagnostic keys, strings and non-boolean values are rejected.
Existing ledgers are never upgraded, overwritten or reset by this change. Any later live attempt
needs a separately reviewed continuation and exact authorization, fresh coverage and private entry;
do not mint a replacement identity merely to bypass the existing ledger.

Local validation: 45 budget/isolation/diagnostic tests and Ruff passed. The four-case fake-provider
rehearsal passed at schema 0.42 with 10 fake calls, and its disposable resources were removed.
This did not consume provider credit or reset the live ledger. No staging runtime,
provider configuration, personal records or protected output files were changed. KR-011 and
OM-003 remain open; this result does not establish staged recovery, owner/device or stability acceptance.

### Correction verification refinement — 2026-09-09

After the first provider attempt, a local fake-classifier reproduction returned a concise EN/SV
notebook-preference statement containing the synthetic replacement marker and used the `notebooks`
domain. Both choices are permitted by the classifier contract. The previous bare-marker equality
and fixed `preferences` lookup reproduced `correction_not_completed`. This establishes a harness
defect, not the exact output or cause of the discarded first live attempt.

The trial now observes the real governed correction function without replacing its implementation
or changing its arguments. Before the deliberate delivery failure, it requires exactly one successful
correction receipt, the seeded previous-memory ID, a distinct newly created replacement ID, the
current `li-chat` source-turn reference, and a unique recalled row with that replacement ID. Stored
content must equal the actual correction argument, include the replacement marker and exclude the
old marker; the row must remain a confirmed/current explicit preference with the exact source
reference. Lookup is bounded but not hard-coded to the seed domain. Receipt arguments and results
stay in process memory and are never written to the ledger or console.

The same proof runs after delivery failure and exact replay; unchanged record ID/content, call count,
and complete canonical-schema fingerprint remain required. Marker presence alone, a model claim,
an unrelated record, duplicate receipts, missing/duplicate rows or mismatched provenance cannot pass.
Missing evidence remains unresolved, never permission to retry an uncertain effect.

Validation: 65 focused tests and Ruff passed, including EN/SV sentence values and negative identity,
source, outcome, content, status and uniqueness cases. The full backend suite passed 1,202 tests
with four intentional opt-in skips and the upstream Starlette/AnyIO warning visible.
The revised four-case fake-provider rehearsal
passed at schema 0.42 with 10 fake calls; both reproduction and verification disposable containers
were removed. No live call, staging change or personal-data access occurred. The original live ledger
is preserved and still blocks rerunning the old command. A separately scoped, owner-authorized new
synthetic trial with fresh coverage is needed before claiming the real-provider failure resolved.
KR-011 and OM-003 remain open.

### Separately authorized PR-104 validation preparation — 2026-09-09

The owner authorized one new isolated four-turn / 16-call / USD 0.50 maximum prepaid trial
after PR #104, not a restart or reconciliation of the discarded first result. Select it explicitly
with `--authorized-pr104-trial`; `--live` is still separately required. The original command remains
blocked by its original ledger. No arbitrary ledger-path or automatic live-batch generator is exposed.

The new live ledger is `output/acceptance/kr011-provider-pr104-20260909.jsonl`. Before creating
resources, the runner requires the preserved `kr011-provider-20260907.jsonl` to match its reviewed
SHA-256. The new exclusive-created ledger records that predecessor filename/hash and PR #104's
merge commit. An existing new ledger blocks execution; a creation race also fails closed. Never
delete, rename, reset or overwrite either ledger to rerun. A stopped new trial requires reconciliation
and another owner decision, not this flag again. Fake rehearsals retain separate dry-run ledgers.

This preparation uses only the new disposable `li-os-kr011-provider-pr104-20260909` container and
`li_os_kr011_provider_pr104` database on `127.0.0.1:55443`, with the unchanged pinned image,
three separated synthetic roles, tracked manifest, guarded provider and correction proof. Local
validation passed 75 focused tests, 1,212 full-backend tests with four intentional opt-in skips,
and Ruff. The Starlette/AnyIO warning remained visible. One four-case EN/SV fake rehearsal passed
at schema 0.42 with 10 fake calls; its exact disposable resources were removed. The original ledger
hash remained unchanged and the new live ledger was absent after preparation.

Read-only billing at 15:12 UTC showed USD 11.95 prepaid with auto-reload off. The official
[Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) still listed Sonnet 5
at USD 2/10 per million input/output tokens; the guard retains conservative 3/15 reservations.
Coverage expires after one hour and must be checked again if stale. No live call occurred during
this preparation. Private key entry and the new trial's actual observations remain pending.
KR-011 and OM-003 remain open; local provider results cannot establish historical-record safety,
staging recovery, subsequent Workspace/capture provider coverage, or device/owner/stability acceptance.

### Private-entry stop and separately authorized attempt — 2026-09-09

The PR-104 trial stopped at `anthropic_key_not_entered` before SDK construction or dispatch.
Its ledger contains only the creation/provenance event: zero turns, reservations or provider calls,
and zero provider consumption for that run. This was local prefix validation, not an Anthropic
authentication rejection. Operator output and an exact-name local Docker check confirm cleanup.
Both this ledger and the original four-call ledger remain unchanged.

The owner subsequently authorized one separate attempt under the same limits. The explicit
`--authorized-key-entry-trial` selector uses only
`output/acceptance/kr011-provider-pr104-key-entry-20260909.jsonl`, requires both previous ledgers'
reviewed hashes, and records both references. Both earlier selectors remain blocked; an existing
new ledger or conflicting selectors also stops execution. No automatic retry or arbitrary ledger
path is introduced. The new disposable database still uses the reviewed localhost-only setup.

Preparation passed 77 focused tests, Ruff, and the four-case schema-0.42 fake rehearsal with
10 fake calls and exact-resource cleanup. The full backend suite passed 1,214 tests with four
intentional skips and the existing Starlette/AnyIO warning. Billing was rechecked at 16:04 UTC:
USD 11.95 prepaid, auto-reload off. Official Sonnet 5 pricing remained USD 2/10 per million
input/output tokens, below the guard's conservative reservation rates. No new live call occurred.
Private entry and actual provider-backed acceptance remain pending; KR-011 and OM-003 remain open.

### Execution and stop conditions

- **Privacy first:** for EN and SV independently, seed synthetic history without recipient metadata,
  then request recall plus Nora consultation and one subsequent Workspace turn. Assert the marker
  actually reaches Li's selected history, is absent from the complete outgoing specialist packet,
  and the derived answer/capture retains private metadata. Include the shared-history variant in
  offline coverage; a further live variant requires a new bounded authorization. A missing recall
  trigger is inconclusive, not a privacy pass. A model declining to repeat a leaked marker is a fail.
- **Recovery separately:** first use the unchanged application path with the disposable database
  and fake providers. Observe one synthetic correction committed, then inject one failure after the
  effect marker/write; separately rehearse process loss. Inspect only the run's fixture IDs and
  recorded turn state. Confirm an uncertain result and no duplicated effect. Any deliberate replay
  rejection probe belongs only to this isolated test and must show zero further writes/provider calls;
  it is not permission to retry an uncertain owner turn. A live-provider version needs its own exact
  fault-point and call budget approval; do not consume the privacy batch allowance for it.
  The explicitly combined 2026-09-07 authorization and narrower allocation above are an exception
  for that single batch, not permission to combine or repeat future trials automatically.
- **Reconciliation:** compare the synthetic before/after record IDs and turn status through the
  scoped test authority. Classify effect observed, no effect proven, or unresolved. Do not reset the
  turn, issue a fresh identity, overwrite data or claim safe retry merely because an HTTP call failed.
  No production reconciliation endpoint is established by this procedure. Unresolved outcomes remain
  unresolved; any real owner decision or record repair is separately authorized.
- Stop the case on unexpected data, packet disclosure, authority drift, ambiguous mutation target,
  missing observation, exhausted budget or unsafe logging. Do not repeat it with new IDs to get a
  green result. Preserve only safe evidence; report failed and inconclusive cases distinctly.
- Record exact environment/image, language, fixture digest, call count/usage, assertions, failures
  and retained disposable-resource names. Remove only specifically authorized disposable resources;
  never delete owner data or backups as cleanup. A local provider-backed fixture proves that layer,
  not the existing Cloud Run configuration. Any remaining staging difference stays explicit.

### Closure and voice eligibility

Close individual evidence gaps only after their applicable observations pass. KR-011 also needs the
separate historical-record decision; a clean synthetic run cannot establish absence of prior harm.
Follow the existing [OM-003 entry gate](LI_OS_IMPROVEMENT_BLUEPRINT.md#om-003-dependency-placement):
rollout and bounded bilingual routing are evidenced, but live privacy/recovery, applicable owner/device
checks and stability evidence remain outstanding. Voice is still planned and gated. Optional themes,
photos, all proactive rhythms and standalone native completion do not become voice prerequisites.

## Calendar sanitized diagnosis — 2026-09-07

The [a7601b7 staging read](releases/2026-09-07-a7601b7-staging.md) failed safely but its
generic outcome did not identify the upstream cause. Read-only checks in this batch confirmed
backend `li-os-release-a7601b7` Ready at 100% traffic, three numeric Calendar secret references,
and Calendar API (`calendar-json.googleapis.com`) enabled among 33 enabled staging-project
services. No secret value, event or personal record was read. These observations do **not** prove
OAuth credential validity, granted scopes, calendar access, or that the OAuth client belongs to
the staging project. The actual provider failure remains unclassified.

Local [adapter tests](../backend/tests/test_google_calendar.py) reproduced 20 missing-diagnostic
cases before the change. Fixed-category diagnostics now separate OAuth/API stages, authentication,
client configuration rejection, required-scope mismatch, explicit API-disabled reasons, access
denial, not-found-or-inaccessible resources, invalid requests, rate limits, unavailability,
timeouts, network failures and malformed responses. An unclassified 403 stays access-denied;
a 404 cannot distinguish a wrong ID from inaccessible data. Unknown codes remain unknown.
No permission is inferred or changed. See Google's
[Calendar error reference](https://developers.google.com/workspace/calendar/api/guides/errors).

Diagnostics contain only fixed action/category/stage and a validated HTTP status, alongside the
existing request correlation. They never log exceptions, raw bodies, URLs, search strings,
calendar identifiers, event content, headers or credentials. Error-code parsing is bounded to
16 KiB and allowlisted machine codes; unexpected or oversized bodies fall back to status-only
classification. User-facing outcomes remain unchanged. No automatic retry was added. Existing
approved-create conflict reconciliation remains limited to an API-stage 409 and the same event ID;
an OAuth-stage 409 cannot enter it.

Synthetic integrated checks also reproduced HTTPX INFO request logging containing a search query.
The backend now disables verbose HTTPX/HTTPCore transport messages and replaces any remaining
transport log body with a fixed privacy notice while retaining severity. Calendar's safe diagnostic
remains visible. This is not suppression of the upstream Starlette/AnyIO warning or proof that
historical logs contain no private data; see [KR-013](KNOWN_RISKS.md#kr-013-provider-transport-log-privacy).

Validation on the local branch: **74 focused tests passed**, **1,167 full backend tests passed**,
four existing opt-in database cases skipped; Ruff and compileall passed. The upstream
Starlette/AnyIO warning remained visible. Tests used synthetic EN/SV search strings, malformed and
oversized responses, unknown adapter attributes, timeouts and denied responses. They verified no
additional calls, no leaked sentinel, unchanged create approval and conflict behavior. No live
provider call, migration or deployment was performed. All 56 tracked Markdown files passed link
and anchor validation; the tracked-file secret audit passed. Local tests do not establish Calendar
provider-backed or device acceptance. Runtime correction commit: `8a56a00`.

### Authorized Calendar diagnostic rollout and bounded result

1. The backend-only tracked-image rollout completed on 2026-09-08 after review, green CI, fresh
   cost evidence, zero-normal-traffic candidate validation, public denial, IAM health, masked
   application readiness/schema-0.42 validation, identity and numeric-reference continuity, and
   authorized promotion. See the [release record](releases/2026-09-08-db1d17c-staging.md). No web,
   database, OAuth, IAM, secret, scheduler or billing change occurred.
2. `a7601b7` remains a schema-compatible availability fallback but restores the transport-logging
   risk. Do not call it privacy-safe or trigger Calendar/provider reads on it merely to verify health.
3. The owner then authorized one bounded read. The one-use runner verified the serving revision,
   authenticated readiness and schema 0.42, recorded its dispatch marker, and attempted one
   `calendar.search` over one UTC day with no query and a maximum of one result. Calendar made no
   model call. The operator request expired while queued, but its exact correlation ID matched one
   `li.calendar` entry: `authentication`, `oauth`, HTTP 400. No retry was made.
4. The deployed mapping means Google returned `invalid_grant` during refresh-token exchange. The
   stored refresh authorization is invalid, expired, revoked or mismatched with the OAuth client;
   the safe evidence cannot distinguish further. A new owner consent flow, refresh-token secret
   version and reviewed backend revision require separate exact authorization. After repair, a new
   bounded read must separately establish Calendar display.
5. Leave OM-010, physical-device/owner/stability acceptance and the exact `LIOS42` archive step
   open until their own evidence exists. Archive requires fresh action-time owner confirmation.
   Weekly Avanza quotes and specialist recency ordering remain planned and out of this batch.
6. On 2026-09-09, the owner-authorized configuration-only follow-up retained the exact `db1d17c`
   image and identity while changing only the three Calendar numeric references from version 1 to
   version 2. Zero-traffic candidate checks, masked application readiness, schema 0.42, public
   denial, private IAM, unchanged web traffic, and pre/post-promotion ERROR-log checks passed. See
   the [Calendar configuration release](releases/2026-09-09-calendar-v2-staging.md).
7. A fresh dated one-use runner then attempted exactly one `calendar.search` over one UTC day with
   no query, no approval, no automatic retry, and a maximum of one result. The provider-backed read
   completed and returned zero events. Event contents were not printed or saved. This closes the
   OAuth credential/read sub-gate, not physical-device Calendar display, owner, or stability
   acceptance.

### Synthetic Finance archive acceptance — 2026-09-09

After fresh action-time owner confirmation, a dated one-use runner verified backend
`li-os-calendar-v2` and web `li-os-web-release-131034f` at 100% traffic, authenticated readiness,
and schema 0.42 before selecting the exact active `LIOS42` Avanza fixture named
`Synthetic acceptance holding`. It required exactly one match and recorded its durable dispatch
marker immediately before the sole archive request.

The governed `archive_portfolio_holding` capability returned `archived`; the target was absent from
the active portfolio afterward. An in-memory before/after fingerprint proved every non-target active
Avanza holding unchanged without printing, logging, or writing any holding value. The tracked
database function archives by setting timestamps rather than deleting its audit record. No automatic
retry, provider call, Calendar or memory operation, schema, IAM, secret, scheduler, billing,
application deployment, or unrelated portfolio mutation occurred. The one-use marker remains so the
operation cannot be dispatched again under this authorization. This closes only the exact synthetic
archive sub-gate; physical-device, owner, and stability acceptance remain open.

## Pre-commit audit

Run and report:

```text
git status --short
git diff --check
git diff --stat
git diff --name-only
git diff --no-ext-diff --binary
git status --short --untracked-files=all
```

Ordinary `git diff` does not include untracked files. For each untracked path, inspect a full new-file
diff with `git diff --no-index -- NUL <path>` on Windows (or `/dev/null` on POSIX), or include it in an
equivalent review tool that visibly renders untracked content. Then verify every changed path is in
scope, scan added lines for secret-like values and personal/runtime data, and confirm no generated
environment-specific manifest was added. Do not commit until the complete diff and validation result
have been reviewed. Whether a separate owner prompt is required is governed by the current
repository-level authorization in [AGENTS.md](../AGENTS.md); that authorization never removes the
review requirement or expands protected external actions.

## Result format

Report each check as `PASS`, `FAIL`, or `SKIPPED`, followed by the exact command and a short reason.
Include environment/tool versions where they affect reproducibility. Separate automated results,
manual review findings, and external operator evidence. Never collapse skipped or unavailable checks
into a general statement that “all tests passed.”
