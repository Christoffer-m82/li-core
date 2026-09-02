# Codex repository instructions

## Purpose

This repository defines and implements Li OS. Work here must preserve the separation between
version-controlled system definition, runtime data, and operator-controlled infrastructure.

The existing documents remain authoritative. Start with:

- [Li Constitution](CONSTITUTION.md) for identity, authority, privacy, and change-control principles.
- [Li OS Architecture](ARCHITECTURE.md) for the foundational target architecture.
- [Security & Privacy Policy](system/security-policy.md) for security requirements.
- [Memory Storage Policy](memory/storage-policy.md) for data, backup, and migration principles.
- [Update Policy](system/update-policy.md) for review, approval, regression, and rollback rules.
- [Repository README](README.md) and component READMEs for implemented behavior and operator guidance.

The files under `docs/` are an operating and navigation layer. They do not supersede the sources
above. If they conflict, stop, cite both locations, and resolve the conflict in the authoritative
source before changing the operating layer.

## Non-negotiable boundaries

- Never commit secrets, tokens, credentials, rendered secret values, production data, or personal
  memory. Example environment files may contain placeholders only.
- Do not treat Git state as proof of live database, Supabase, Google Cloud, scheduler, bucket, IAM,
  or service state. Label repository facts and operator-verified external facts separately.
- Do not apply migrations, run provisioning scripts, deploy services, rotate credentials, change
  IAM, or touch cloud resources unless the task explicitly authorizes that exact external action.
- Treat every file in `memory/migrations/` as immutable history. Add a new migration for a schema
  change; never edit an applied migration merely to make the sequence look cleaner.
- Keep application, Theo, owner-confirmation, native-gateway, retention-worker, browser/BFF, and
  scheduler authorities separate. A convenient shared credential is not an acceptable shortcut.
- Preserve user work and unrelated changes. Do not modify old worktrees or branches as part of a
  current-tree task.
- Do not commit unless the user explicitly asks after reviewing the diff and validation result.

## Working method

1. Read the relevant authoritative documents and the nearest component README before editing.
2. Check `git status --short` and identify pre-existing changes.
3. Verify claims against tracked files. Prefer links to existing explanations over copied prose.
4. Make the smallest scoped change. Keep policy, implementation, migration, and deployment changes
   in separately reviewable commits when a task includes more than one category.
5. Run the focused tests first, then the broader applicable checks in
   [Testing and audit](docs/TESTING_AND_AUDIT.md).
6. Validate Markdown links whenever documentation changes.
7. Review the complete diff for secrets, authority expansion, unverified operational claims, and
   accidental changes outside scope.
8. Report changed files, commands run, failures or skipped checks, known residual risks, and commit
   status.

## Repository map

- `backend/`: private FastAPI backend, orchestration, providers, governed actions, and database API.
- `frontend/`: FastAPI browser BFF and mobile-first web application.
- `native-gateway/`: authenticated gateway between native clients and the private backend.
- `native/android/` and `native/ios/`: coarse-place proof-of-concept libraries.
- `memory/`: schema baseline, immutable migrations, permissions, and storage policy.
- `deployment/cloud-run/`: reviewable templates, provisioning scripts, and deployment-specific docs.
- `agents/`, `li/`, `system/`, and `users/`: identity, governance, registry, policy, and configuration.
- `docs/`: Codex operating documentation, indexes, workflows, milestones, and risk register.

See [CODEX.md](CODEX.md) for the operating-document index.
