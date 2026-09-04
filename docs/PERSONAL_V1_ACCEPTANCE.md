# Personal-use v1 acceptance

This is the execution checklist for the owner's request to finish Li, not a replacement for the
[Constitution](../CONSTITUTION.md), [open milestones](OPEN_MILESTONES.md), or component specifications.
The first release target is dependable personal use through the installable web app on the owner's
Android phone, Android tablet, and Windows laptop. A standalone native app remains a separate
unfinished deliverable; this ordering does not cancel it or imply that it is shipped.

## Completion rule

An area is complete only when its agreed user journeys pass, relevant security/error paths pass,
the reviewed version is deployed with authorization, and required live/device evidence is recorded.
Code presence, green CI, configuration status, and an agent portrait alone do not prove completion.
Earlier percentage and time estimates are planning judgments, not measured acceptance results.

Use synthetic fixtures for automated tests. Do not send mail, create calendar events, change memory,
delete records, activate rhythms, or restore a database solely to gather evidence without the exact
required authorization. Secret entry and physical-device checks may require the owner.

## Ordered work and exit checks

| Area | Acceptance checks | Evidence still required |
| --- | --- | --- |
| Core chat and routing | Typed request, specialist selection, final response, history reload, timeout/retry, no duplicate or unauthorized action | Representative end-to-end journeys with controlled fixtures and an approved live smoke test |
| Memory and history | Recall, inspect proposed memory, correction and forgetting through the documented confirmation boundaries; no cross-authority access | Complete UI journeys and authorized data-integrity/recovery tests |
| Files | Temporary upload, explicit save, reopen/download, permission denial, retention and failure recovery | Synthetic full-stack lifecycle test and operator-verified expiry behavior |
| Home | Useful real-data summary, clear freshness/unavailable states, working navigation; no invented agenda or priorities | Implement and validate remaining [Home recommendations](../frontend/APPEARANCE.md#home-template-analysis) |
| Specialists | All registry names/roles, selected portraits, original viewer, recorded interactions, honest unavailable states | Longer-running interaction and accessibility checks; system profiles remain read-only definitions |
| Themes | Built-ins and custom creation; editing and portable export/import; preserve content and contrast | Editing/transfer implementation and tests; automatic cross-device sync needs a storage design |
| Calendar, Gmail, tasks, research | Read flows; supported writes gated by approval; unavailable providers and stale evidence handled clearly | Provider-specific end-to-end checks; Gmail sending remains deliberately unavailable |
| Proactivity | Owner-approved schedule, grounded brief, quiet hours, duplicate prevention, delivery and stand-down | Exact per-rhythm activation approval plus coordinated database/scheduler verification; external notification delivery needs a design |
| Voice | Transcript correctness, cancel, interruption, permission denial, unavailable service, spoken response stop | Physical Android phone/tablet and Windows browser checks; server speech remains unconfigured |
| Installation | Install, launch, sign-in expiry, update, offline explanation, keyboard/touch navigation | Physical-device checklist; native Android and gateway completion tracked separately |
| Security and recovery | Auth/role denial, safe logs, pinned release, rollback, successful isolated restore with recovery timings | Authorized restore drill and dated evidence; see [known risks](KNOWN_RISKS.md) |
| Release stability | All agreed journeys pass, no unresolved critical findings, normal use observation and rollback available | A stable-use observation period; no unsupported claim of 100% |

## Baseline — 2026-09-04

- Local Python suites: backend 350, frontend 59, native gateway 12 tests passed; Ruff passed in all
  three components. The local runtime reported an existing Starlette/httpx deprecation warning.
- PR #27 passed 11 CI checks and was merged. Its frontend was deployed with explicit approval.
- Read-only live capability inventory reported database readiness passing and Calendar/Gmail configured;
  this does not establish successful end-to-end provider operations.
- Read-only scheduler inventory showed all five proactive jobs paused. The live UI reported morning
  disabled and the remaining rhythms preview-only. Native gateway and market quotes were unconfigured.
- Backup restoration and physical-device acceptance have not been demonstrated in this task.
- The first local reliability fix prevents blocked browser storage from aborting startup or breaking
  voice controls. Two regression tests failed before the fix and passed after it; all 34 JavaScript
  tests passed before adding a third save-failure regression check. The final JavaScript suite has
  35 passing tests. This new fix is not yet committed or deployed.

Run checks from [Testing and audit](TESTING_AND_AUDIT.md). Attach dated evidence when closing a row;
never infer external state from a repository commit or mark a skipped check as passed.
