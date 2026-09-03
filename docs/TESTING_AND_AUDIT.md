# Testing and audit

## Purpose

Use the smallest relevant checks during development and the full applicable matrix before release.
This file documents repository commands and evidence expectations; it does not claim that a check
passed unless a dated work report records the result.

## Python component checks

The three Python projects use Python 3.12+, pytest, and Ruff as declared in their `pyproject.toml`
files. Run them from their own directories because each project exposes a top-level package named
`app`.

```text
cd backend
python -m ruff check app tests
python -m pytest
python -m compileall app

cd ../frontend
python -m ruff check app tests
python -m pytest
python -m compileall app

cd ../native-gateway
python -m ruff check app tests
python -m pytest
python -m compileall app
```

Each component tracks a universal `uv.lock`. With uv 0.12.9, run `uv sync --locked --extra dev`
inside the component before these commands, and prefix commands with `uv run --locked` to use the
locked environment. After an intentional dependency change, regenerate that component's lock with
`uv lock`, review the resolved-version and source changes, and rerun its checks. CI rejects a stale
lock. The three production Dockerfiles use the same locks with development dependencies excluded;
CI builds each image from the repository root to verify that path. The uv build binary is pinned by
version and immutable image digest, as is the shared Python base image. Review and update each
readable version together with its digest, rebuild all three images, and inspect the source manifest
before accepting a refresh. Do not copy production `.env` values into a development shell; use
placeholders and synthetic data.

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
simulator/device, permission-flow, or staged Native Gateway integration testing.

External GitHub Actions in repository workflows are pinned to immutable 40-character commit SHAs;
the adjacent release comment keeps the intended version readable. For an intentional action update,
resolve the official upstream release tag to its commit, review the upstream release and diff, update
the SHA and comment together, and let the repository audit reject any mutable tag reference.

Absence of a local platform toolchain is a skipped check, not a pass.

## Documentation checks

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
environment-specific manifest was added. Do not commit until the user has reviewed the complete diff
and validation result and explicitly asks for a commit.

## Result format

Report each check as `PASS`, `FAIL`, or `SKIPPED`, followed by the exact command and a short reason.
Include environment/tool versions where they affect reproducibility. Separate automated results,
manual review findings, and external operator evidence. Never collapse skipped or unavailable checks
into a general statement that “all tests passed.”
