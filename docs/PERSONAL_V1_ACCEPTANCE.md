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
| Home | Useful real-data summary, clear freshness/unavailable states, working navigation; no invented agenda or priorities | Compact real-data glance and phone specialist entry implemented; agenda, owner-selected priorities and consolidated attention remain in the [Home recommendations](../frontend/APPEARANCE.md#home-template-analysis) |
| Specialists | All registry names/roles, selected portraits, original viewer, recorded interactions, honest unavailable states | Longer-running interaction and accessibility checks; system profiles remain read-only definitions |
| Themes | Built-ins and custom creation; editing and portable export/import; preserve content and contrast | [Editing and transfer](../frontend/APPEARANCE.md#edit-and-transfer) implemented with local regression tests; deployed and physical-device acceptance remains pending. Automatic cross-device sync needs a storage design |
| Calendar, Gmail, tasks, research | Read flows; supported writes gated by approval; unavailable providers and stale evidence handled clearly | Provider-specific end-to-end checks; Gmail sending remains deliberately unavailable |
| Proactivity | Owner-approved schedule, grounded brief, quiet hours, duplicate prevention, delivery and stand-down | Exact per-rhythm activation approval plus coordinated database/scheduler verification; external notification delivery needs a design |
| Voice | Transcript correctness, cancel, interruption, permission denial, unavailable service, spoken response stop | Physical Android phone/tablet and Windows browser checks; server speech remains unconfigured |
| Installation | Install, launch, sign-in expiry, update, offline explanation, keyboard/touch navigation | Physical-device checklist; native Android and gateway completion tracked separately |
| Security and recovery | Auth/role denial, safe logs, pinned release, rollback, successful isolated restore with recovery timings | Authorized restore drill and dated evidence; see [known risks](KNOWN_RISKS.md) |
| Release stability | All agreed journeys pass, no unresolved critical findings, normal use observation and rollback available | A stable-use observation period; no unsupported claim of 100% |

## Local browser accessibility evidence — 2026-09-05

An authenticated local Windows Chromium check used synthetic specialist activity and no production
personal data. Home, Specialists, Backend and Settings exposed the correct current navigation item
and view-specific heading description. Every visible enabled button, link, input, select, textarea
and summary in those checked views measured at least 44 by 44 CSS pixels after the accessibility
corrections. The Specialist Workspace, History and Statistics views also met that target; the large
portrait dialog focused Close on opening, closed with Escape and returned focus to its portrait
button. Built-in Dark, Light and Forest appearances applied their validated text-on-accent tokens.

Permanent frontend tests cover the view announcements, current-page state and target-size rules.
This evidence is local browser validation, not a deployed acceptance result. Android phone/tablet,
Windows installed-PWA, 200% zoom and screen-reader checks remain open, as do the other external and
protected checks in the table above.

The later Home glance check used four synthetic successful data sources in the same authenticated
local Windows Chromium fixture. It displayed 2 recent conversations, 1 open commitment, 1 unread
brief and 1 saved file above the conversation without introducing a new backend source. Permanent
tests separately prove that a failed source displays unknown and that the freshness message reports
partial availability. This is desktop visual and local contract evidence only; responsive automated
rules do not replace the open Android/tablet/installed-Windows checks.

## Blueprint implementation evidence — 2026-09-05

The six packages in the [Li OS improvement blueprint](LI_OS_IMPROVEMENT_BLUEPRINT.md) are implemented
and locally verified on `codex/li-os-improvement-blueprint`. The dated
[acceptance record](LI_OS_IMPROVEMENT_ACCEPTANCE.md) maps R1–R14 to permanent tests, records the full
local test matrix and migration rehearsal, and distinguishes local implementation from remaining
deployment, external-database, live-provider, restore, physical-device and stable-use evidence.
Those remaining rows stay open; local green tests are not relabelled as deployed or device acceptance.

## Earlier baseline — 2026-09-04

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
