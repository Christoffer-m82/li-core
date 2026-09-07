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

**Reviewed 2026-09-07; procedure only, not live-test authorization or completion.** Use the
[personal-use checklist](PERSONAL_V1_ACCEPTANCE.md) as the completion ledger and
[KR-011](KNOWN_RISKS.md#kr-011-chat-privacy-and-memory-retry-live-acceptance-remains-incomplete)
as the risk record. The [current release](releases/2026-09-07-0fc39a7-staging.md) proves rollout and
one Swedish specialist exchange, not the privacy/recovery cases below.

### Existing evidence and remaining gaps

| Boundary | Existing executable evidence | Still required |
| --- | --- | --- |
| Historical recall and later Workspace disclosure | `test_historical_recall_stays_private_in_workspace_and_derived_outputs` in [chat acceptance tests](../backend/tests/test_personal_v1_chat_acceptance.py): EN/SV, fresh/shared history, subsequent turn, private answer/capture metadata | Provider-backed synthetic run with packet-boundary inspection, not merely an answer that omits a marker |
| Private-source proposals | `test_proposal_cannot_drop_source_privacy` and `test_every_memory_mutation_is_guarded_immediately_before_write` in [capture tests](../backend/tests/test_memory_capture.py), plus HTTP capture-error tests | Preserve rejection before writes/markers; live classifier behavior is separate. Full private-proposal support remains unavailable |
| Failure after memory write | `test_memory_change_then_model_failure_is_not_safe_to_repeat`, deferred-capture and uncertain-retry tests in [recovery tests](../backend/tests/test_recoverable_turns.py) | Isolated integrated application/database failure observation and provider-backed uncertainty wording; no live failure induced in the owner's environment |
| Process loss and authority fencing | `validate_memory_effect_fence` in the [migration harness](../memory/tests/validate_migrations.py): invalid/stale identities, expired lease, uncertainty, permitted/denied roles | Preserve existing rehearsal evidence; do not relabel it as a live provider failure or rerun a personal backup restore solely for this check |
| Previously affected records | No retrospective assessment performed | Separate exact authorization and owner-controlled privacy-preserving assessment, or explicit residual-risk decision; new tests cannot certify old records |

The current focused local run passed 112 tests with the upstream Starlette/AnyIO warning visible:

```text
cd backend
python -m pytest tests/test_personal_v1_chat_acceptance.py tests/test_recoverable_turns.py tests/test_memory_capture.py tests/test_conversation_history.py tests/test_li_orchestration.py tests/test_governed_systems.py tests/test_context_privacy_migration.py -q
```

This reused existing synthetic tests; no provider call, personal-record read, database migration or
deployment was performed. It is not an integrated live-environment result.

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
4. A reviewed isolated runner and per-call budget guard are prerequisites, not existing capabilities
   claimed by this procedure. It must count all classifier, specialist, synthesis and fallback calls,
   enforce input/output ceilings and stop before the next call would exceed the approved allowance.
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
