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
