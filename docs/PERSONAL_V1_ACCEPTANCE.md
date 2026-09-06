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

## Package 6 dependency sequence

The current execution placement for OM-003 is:

**stable core chat/history, memory/privacy, bilingual response/routing, tactile action approval and
recoverable turns → OM-003 provider/voice evaluation and cost check → architecture decision →
implementation → authorized staged deployment → enhanced voice device/owner acceptance → final
personal-use sign-off that includes enhanced voice.**

The [Package 6 entry criteria](LI_OS_IMPROVEMENT_BLUEPRINT.md#om-003-dependency-placement) govern
eligibility. Packages 1–5 and the existing Package 6 foundations are merged and locally verified;
migrations 037–039 and the earlier application release have separate staging evidence. The controlled
bilingual chat/retry journey also passes. These are satisfied prerequisites at their recorded layers,
not proof that the full core stability gate is closed.

The schema-0.40 staging rollout and read-only owner-proposal journey are now recorded in the
[2026-09-06 release evidence](releases/2026-09-06-2746421-staging.md). Outstanding entry evidence is
the live English/Swedish core-chat smoke journey, applicable owner mutation and physical-device checks,
and absence of blocking findings through the required stability period. Until those are recorded,
OM-003 remains planned and is not automatically next. Unrelated eligible acceptance work continues
if voice is blocked.

Optional visual improvements, profile-photo activation, every proactive rhythm and standalone native-
app completion are not prerequisites for installable-web voice. The enhanced voice experience itself
must nevertheless complete Android phone/tablet and owner acceptance, with Windows regression checks,
before the final release sign-off can include it.

## Ordered work and exit checks

| Area | Acceptance checks | Evidence still required |
| --- | --- | --- |
| Core chat and routing | Typed request, specialist selection, final response, history reload, timeout/retry, no duplicate or unauthorized action | A controlled API journey now covers bilingual Nora routing, completion, persisted history reload and idempotent replay; an approved live staging smoke test remains pending |
| Memory and history | Recall, inspect proposed memory, correction and forgetting through the documented confirmation boundaries; no cross-authority access | Schema 0.40 and the matching application release are deployed; the signed-in read-only proposal journey passed without changing data. Physical-device, correction/forgetting and other authorized live data-integrity journeys remain open |
| Files | Temporary upload, explicit save, reopen/download, permission denial, retention and failure recovery | A synthetic HTTP-boundary lifecycle now covers the complete journey, owner-scoped not-found behavior, a recoverable storage outage and deletion; operator-verified scheduled expiry remains pending |
| Home | Useful real-data summary, clear freshness/unavailable states, working navigation; no invented agenda or priorities | Compact real-data glance and phone specialist entry implemented; agenda, owner-selected priorities and consolidated attention remain in the [Home recommendations](../frontend/APPEARANCE.md#home-template-analysis) |
| Specialists | All registry names/roles, selected portraits, original viewer, recorded interactions, honest unavailable states | A signed-in staging smoke check opened a Home specialist card directly into Workspace, loaded the three-party saved conversation, History and bounded Statistics, and opened the named full-resolution portrait without mutation. Physical-device, longer-running interaction and screen-reader checks remain open; system profiles remain read-only definitions. |
| Themes | Built-ins and custom creation; editing and portable export/import; preserve content and contrast | [Editing and transfer](../frontend/APPEARANCE.md#edit-and-transfer) is implemented, locally regression-tested and deployed to staging; physical-device acceptance remains pending. Automatic cross-device sync needs a storage design |
| Calendar, Gmail, tasks, research | Read flows; supported writes gated by approval; unavailable providers and stale evidence handled clearly | Provider-specific end-to-end checks; Gmail sending remains deliberately unavailable |
| Proactivity | Owner-approved schedule, grounded brief, quiet hours, duplicate prevention, delivery and stand-down | Exact per-rhythm activation approval plus coordinated database/scheduler verification; external notification delivery needs a design |
| Voice | Existing foundation: transcript correctness, cancel, permission denial, unavailable service and spoken response stop. Planned late-Package-6 extension: expressive Swedish/English real-time conversation, natural turn timing, interruption and recovery; see the [real-time voice plan](REALTIME_VOICE_PLAN.md). | Close the core stability entry gate first. Then complete provider/cost evaluation, architecture decision, implementation, authorized staged deployment and measured Android phone/tablet owner acceptance with Windows regressions. The addition remains planning only. |
| Installation | Install, launch, sign-in expiry, update, offline explanation, keyboard/touch navigation | Complete the [physical-device and owner checklist](PERSONAL_V1_DEVICE_ACCEPTANCE.md); native Android and gateway completion remains tracked separately |
| Security and recovery | Auth/role denial, safe logs, pinned release, rollback, successful isolated restore with recovery timings | The original and replacement backups passed the [2026-09-06 isolated restore drill](releases/2026-09-06-isolated-restore-drill.md), and the superseded copy was then deleted with owner authorization while the validated replacement was preserved. The [schema-0.40 release](releases/2026-09-06-2746421-staging.md) retained private backend IAM, numeric secret-version references and application rollback. Recurring cadence and remaining acceptance evidence stay open. See [known risks](KNOWN_RISKS.md). |
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

After the compact specialist entry was added, a synthetic authenticated system-Chrome review rendered
Home at 390 × 844, 800 × 1280 and 1440 × 900 CSS pixels, plus a 720 × 900 narrow-reflow proxy. The
phone and narrow cases showed exactly three active-first cards, retained all 12 in the document and
exposed a 44-pixel **View all 12 specialists** control that opened the full Specialists view. Tablet
and desktop showed all 12 without the redundant control. None of the four cases had horizontal page
overflow. This remains local responsive evidence, not actual 200% browser zoom or physical-device proof.

## Blueprint implementation evidence — 2026-09-05

The six packages in the [Li OS improvement blueprint](LI_OS_IMPROVEMENT_BLUEPRINT.md) are implemented,
merged and locally verified. The dated [acceptance record](LI_OS_IMPROVEMENT_ACCEPTANCE.md) maps
R1–R18 to permanent tests and records the full local test matrix and migration rehearsal. The later
[staging release record](releases/2026-09-05-a864076-staging.md) establishes migrations 037–039 and
deployment separately. Live-provider, restore, physical-device and stable-use evidence remains open;
local green tests and a healthy deployment are not relabelled as device acceptance.

## Staging release evidence — 2026-09-05

The reviewed backend and web images were deployed to staging, migrations 037 through 039 were applied
in order, and the final database schema is 0.39. A pre-migration logical backup was encrypted locally,
authenticated in full, and accepted by `pg_restore --list`; this validates backup integrity and
catalogue readability, not restoration. Both services are Ready on their recorded immutable image
digests, rollback revisions remain available, and all 12 pull-request and post-merge checks passed.
See the [release record](releases/2026-09-05-a864076-staging.md) for the bounded evidence and remaining
operator acceptance.

## Post-release acceptance progress — 2026-09-05

The backend file regression `test_saved_file_lifecycle_is_private_recoverable_and_owner_scoped`
passes the complete synthetic HTTP journey in one test: a temporary upload leaves no record or
object, explicit Save creates a kept artifact, the owner library lists it, download returns the exact
bytes with private no-store headers, an unknown or other-owner identifier is concealed as not found,
a simulated storage outage returns unavailable and then recovers, and deletion removes the object
before hiding the metadata tombstone. This closes the synthetic lifecycle portion of the Files row.
The deployed retention schedule and real expiry behavior remain external operator evidence.

Read-only external inventory on 2026-09-05 found the daily artifact-retention scheduler enabled and
its latest six scheduled executions successful. This proves that the job ran, not that a particular
artifact reached expiry and was deleted. The five proactive rhythm jobs remained paused. The live
backend configuration contained the required variable references for Anthropic, artifact storage,
Brave research, Calendar and Gmail; no value was read. Configuration presence does not prove provider
entitlement, correctness, successful calls, or owner-journey acceptance.

## Controlled core-chat journey — 2026-09-06

The permanent
[`test_bilingual_specialist_chat_persists_reloads_and_replays_once`](../backend/tests/test_personal_v1_chat_acceptance.py)
fixture drives the authenticated backend API with synthetic state. Both **Ask Nora to compare these
options** and **Be Nora jämföra de här alternativen** select Nora under the same policy, produce one
validated synthesis, persist one owner and one Li message, reload that history, and replay the same
stable turn without rerunning Nora or adding a duplicate message. Existing failure-path tests cover
in-progress, uncertain, conflicting, expired and unavailable turn states.

This evidence uses no live model, provider, personal memory or external action. It closes the
controlled-fixture portion of Core chat and routing, but it does not replace the pending provider-
backed staging smoke test or physical-device acceptance.

## Controlled memory UI journey — 2026-09-06

The authenticated web History view now includes a bounded, read-only search of Li's existing
`/memory/recall` boundary. It renders only the readable memory value and user-relevant status with
DOM text nodes. It also lists outstanding `pending` and `needs_user_confirmation` suggestions through
a new owner-only read function. The list excludes source references, raw metadata and proposal
identifiers; it does not expose Theo's credential, direct table access, owner credentials, or a
mutation route. Chat renders the backend's actual `stored`, `proposed`, `corrected` or `forgotten`
outcome and gives an explicit uncertainty message when the memory update cannot be verified.

Backend and frontend regression tests prove authentication, query and result limits, URL encoding,
separate Li/owner read authorities, absence of a memory mutation route, safe text rendering and the
visible outcome contract. The full migration history through schema 0.40 passes on the exact pinned
disposable Supabase PostgreSQL image, including owner allow, backend deny, function ownership, direct
table denial and replay rejection. Migration 040 and the matching backend/web release were later
deployed and the signed-in read-only owner journey passed; see the
[release record](releases/2026-09-06-2746421-staging.md). Physical-device, correction/forgetting and
other authorized live data-integrity journeys remain open.

## Historical recall privacy correction — 2026-09-06

The Astra review reproduced a gap at baseline `9db644c`: historical search snippets lack recipient
metadata, but a fresh Specialist Workspace could forward them through its untyped-history fallback.
With existing shareable history, Li's recalled answer could instead be saved as shareable, allowing
later disclosure. Four paired English/Swedish HTTP regressions failed before the correction.

Search snippets now remain private to Li. The runtime receives explicit recent-message disclosure
records even when that list is empty; raw legacy history is never a specialist-sharing permission.
Selected historical context also restricts the derived answer and memory-capture privacy. Regression
tests cover fresh and existing Workspaces, a subsequent turn, direct responses, and preservation of
explicitly permitted history sharing.

Validation: backend `pytest -q` passed 1,050 tests and Ruff passed. The existing upstream
Starlette/AnyIO alias warning remains visible. Markdown targets and anchors passed. The complete
diff review found no new authority, database schema, dependency, deployment or secret changes.

This is synthetic local acceptance evidence, not proof of live-provider or device behavior. It does
not reclassify previously saved answers or memories. The reviewed correction must be deployed and
existing affected records assessed through an authorized privacy-preserving process before this
finding can be treated as closed in staging. OM-003 remains gated by core stability and the other
outstanding entry evidence; no voice provider or implementation was activated.

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
  voice controls. Two regression tests failed before the fix and passed after it; later suites expanded
  this coverage. The fix is merged and included in the staging release recorded above.

Run checks from [Testing and audit](TESTING_AND_AUDIT.md). Attach dated evidence when closing a row;
never infer external state from a repository commit or mark a skipped check as passed.
