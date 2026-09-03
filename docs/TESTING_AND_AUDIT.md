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

Install each project with its `dev` extra in an isolated environment before running these commands.
Do not copy production `.env` values into a development shell; use placeholders and synthetic data.

## Native checks

- iOS package: run `swift test` from `native/ios/` on a host with the declared Swift 5.9 toolchain.
- Android library: use the project's Gradle tasks on an Android-capable host. This repository does
  not currently track a Gradle wrapper, so record the Gradle/JDK/SDK versions and exact command used.

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
the target environment's actual state. Record whether a disposable-database rehearsal was run.

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
