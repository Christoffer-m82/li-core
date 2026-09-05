# Codex operating guide

This is the entry point for repository work performed with Codex. It supplements, but does not
replace, the governing and component documentation.

## Read first

1. [AGENTS.md](AGENTS.md) — repository-wide working rules and non-negotiable boundaries.
2. [Li Constitution](CONSTITUTION.md) — governing identity, authority, and change-control principles.
3. [Li OS Architecture](ARCHITECTURE.md) — foundational system intent and target architecture.
4. [Repository README](README.md) — implemented features and deployment guidance.

Then use the operating documents that match the task:

| Need | Document |
| --- | --- |
| Understand components and data flow | [Architecture overview](docs/ARCHITECTURE_OVERVIEW.md) |
| Review trust and authority boundaries | [Security boundaries](docs/SECURITY_BOUNDARIES.md) |
| Prepare or review a release | [Deployment workflow](docs/DEPLOYMENT_WORKFLOW.md) |
| Prepare or review database change | [Migration workflow](docs/MIGRATION_WORKFLOW.md) |
| See unfinished or externally gated work | [Open milestones](docs/OPEN_MILESTONES.md) |
| Choose and report validation | [Testing and audit](docs/TESTING_AND_AUDIT.md) |
| Implement or verify the six improvement packages | [Improvement blueprint](docs/LI_OS_IMPROVEMENT_BLUEPRINT.md) and [acceptance record](docs/LI_OS_IMPROVEMENT_ACCEPTANCE.md) |
| Find an existing decision | [Decision index](docs/DECISIONS.md) |
| Create or revise specialist portraits | [Portrait standard](system/specialist-portrait-standard.md) and [assignment record](system/specialist-portrait-assignments.md) |
| Review evidence-backed repository risks | [Known risks](docs/KNOWN_RISKS.md) |

## Evidence rule

Use one of these labels when operational state matters:

- **Repository fact:** directly verified in tracked files or Git history.
- **Test result:** observed from a named command on the current revision.
- **Operator-verified state:** confirmed in the external system by an authorized operator, with date
  and environment.
- **Unknown:** not established by the repository or current authorized checks.

Never infer a live deployment, applied migration, secret version, IAM binding, backup, scheduler
state, or Supabase state solely from code, templates, documentation, or a commit message.

## Standard handoff

Before committing under the current repository authorization, or before requesting a commit when
that authorization does not apply, review and provide:

- a concise outcome summary;
- the complete diff or an explicit path to it;
- validation commands and results;
- skipped checks and why;
- security or migration review findings;
- residual risks; and
- the resulting commit status.
