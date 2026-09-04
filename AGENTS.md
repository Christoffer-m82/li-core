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
- Commit and merge authority is governed by the project-limited authorization below; review and
  validation remain mandatory even when another owner approval is not required.

## No-spending requirement

The owner permits using existing subscriptions, prepaid credits and included/free allowances for
this project, provided the work requires no new payment or additional charge. This supersedes the
earlier blanket ban on using paid-for services or consuming prepaid credits. It does not authorize
new spending, automatic overages or bill-later charges.

- Continue ordinary in-scope work using access already paid for or included. Do not stop merely
  because a service has paid plans or because an existing subscription is being used.
- Do not purchase, subscribe to a new service, upgrade plans, buy credits/top-ups, enable automatic
  replenishment or paid overages, start chargeable trials, or incur charges outside existing
  coverage. The absence of a checkout/payment screen does not make usage free of additional charges.
- Before metered operations, establish that the relevant subscription/credit/allowance covers the
  intended bounded work and will not spill into automatic billing. Use available read-only usage
  evidence or reliable owner-provided account information, never expose credentials or change billing
  controls. An API key or configured service alone does not establish coverage.
- The owner reports an existing Anthropic subscription. Do not assume that it includes the particular
  Anthropic API/model usage needed by Li; verify that product's entitlement or prepaid balance before
  live calls. Apply the same principle to hosted CI, cloud compute/storage/egress and other providers.
- If an operation requires an additional payment or charge, leave that operation blocked and tell
  the owner what is required; do not pay on their behalf. If coverage is uncertain, first investigate
  safely or use local tests, mocks or included alternatives. Continue other safe in-scope work rather
  than stopping the whole project at a cost-blocked step.
- Flag metered dependencies in designs. Do not claim a cloud-dependent feature is free, and do not
  activate it without both verified existing coverage and any separate external-action approval.
- Do not cancel existing services, delete resources, change billing settings or disrupt the live
  system to enforce this rule without separate exact authorization. This rule does not establish
  that existing services have stopped billing or that the owner's account has no existing costs.
- Do not treat "keep going" or project-completion approval as permission for additional spending.
  New payments or charges require an explicit owner change to this rule for a specified action and
  budget. Never bypass a paid prerequisite or misrepresent a blocked check as passed.

## Project-limited end-to-end authorization

The owner authorizes autonomous completion of this Li OS project's agreed scope, until that scope
is fully completed or the owner revokes or changes this authorization, subject to the no-spending
requirement above. This is not authorization
for unrelated projects, indefinite maintenance, or newly invented product scope. Use the
[personal-use acceptance checklist](docs/PERSONAL_V1_ACCEPTANCE.md) and the owner's agreed requests
to track completion; green tests or merged code alone do not establish deployed, live or device readiness.

- Inspect files, edit the current working branch, install declared dependencies, run development
  servers and tests, fix failures, and make ordinary implementation and design decisions without
  asking the owner to advance each step.
- Review the complete diff and applicable validation results, then commit, push feature branches,
  create or update pull requests, and address CI failures without a separate owner approval for
  each batch. Keep changes scoped and preserve unrelated work.
- Merge reviewed pull requests when all required checks pass and there are no unresolved conflicts,
  blocking review findings, or failed security/data-integrity validations. Never bypass checks or
  change branch protection to make a merge possible.
- Continue to the next safe in-scope step rather than ending at an ordinary review, commit, PR or
  merge checkpoint. Give concise progress updates and report meaningful results without turning
  those updates into routine approval requests.
- Stop for secrets the owner must enter, a genuine blocker that prevents safe progress, a
  system-required confirmation, or a separately protected action. Exhaust safe in-scope alternatives
  when possible; never expose credentials or weaken a safeguard to avoid stopping.
- Deployment, applied migrations, provisioning, production/cloud/Supabase/IAM changes, secret
  rotation, billing, account permissions, branch-protection changes and destructive operations
  still require authorization for the exact action. Force-pushes, shared-history rewrites and
  alterations to unrelated branches/worktrees are not included. A broad "keep going" does not
  authorize these protected actions.

This authorization controls the development workflow only. It does not change Li's runtime action
permissions, owner-confirmation requirements, memory boundaries or security policy. On completion,
report the acceptance evidence and remaining limitations honestly; do not claim completion merely
to close this authorization. Subsequent out-of-scope work requires a new owner request.

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

## Specialist portrait work

Before creating or revising any specialist thumbnail, read the owner-directed
[portrait standard](system/specialist-portrait-standard.md) and the entire
[assignment record](system/specialist-portrait-assignments.md). Use registry names and roles,
plan variety against the whole roster, and preserve existing approved portraits. Update the
assignment record when a new portrait is selected. Always use the specialist's registry name;
Elena is Elena, with no revision labels. Only her current selected portrait belongs in the collection.
