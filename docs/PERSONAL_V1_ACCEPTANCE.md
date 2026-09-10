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

The schema-0.41 privacy and recovery rollout is now recorded in the
[2026-09-06 release evidence](releases/2026-09-06-8831381-staging.md), building on the earlier
[schema-0.40 release](releases/2026-09-06-2746421-staging.md). Outstanding entry evidence is
the broader live privacy/recovery journey (bounded bilingual routing and Swedish specialist output
are evidenced below), applicable owner mutation and physical-device checks,
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
| Core chat and routing | Typed request, specialist selection, final response, history reload, timeout/retry, no duplicate or unauthorized action | A controlled API journey covers bilingual Nora routing, completion, persisted history reload and idempotent replay. The [backend routing release](releases/2026-09-06-e46b509-staging.md) now verifies the previously failing prefixed Swedish request invoked Nora and produced a Swedish Li response; broader live recovery acceptance remains open |
| Memory and history | Recall, inspect proposed memory, correction and forgetting through the documented confirmation boundaries; no cross-authority access | Schema 0.41 and the matching privacy/recovery application corrections are deployed after a fresh encrypted backup, full restore and rehearsal. The signed-in read-only paths passed without changing data. Provider-backed bilingual privacy, correction/forgetting, uncertain-effect reconciliation, and physical-device journeys remain open |
| Files | Temporary upload, explicit save, reopen/download, permission denial, retention and failure recovery | A synthetic HTTP-boundary lifecycle now covers the complete journey, owner-scoped not-found behavior, a recoverable storage outage and deletion; operator-verified scheduled expiry remains pending |
| Home | Useful real-data summary, clear freshness/unavailable states, working navigation; no invented agenda or priorities | Compact real-data glance and phone specialist entry implemented; agenda, owner-selected priorities and consolidated attention remain in the [Home recommendations](../frontend/APPEARANCE.md#home-template-analysis) |
| Specialists | All registry names/roles, selected portraits, original viewer, recorded interactions, honest unavailable states | A signed-in staging smoke check opened a Home specialist card directly into Workspace, loaded the three-party saved conversation, History and bounded Statistics, and opened the named full-resolution portrait without mutation. Physical-device, longer-running interaction and screen-reader checks remain open; system profiles remain read-only definitions. |
| Themes | Built-ins and custom creation; editing and portable export/import; preserve content and contrast | [Editing and transfer](../frontend/APPEARANCE.md#edit-and-transfer) is implemented, locally regression-tested and deployed to staging; physical-device acceptance remains pending. Automatic cross-device sync needs a storage design |
| Calendar, Gmail, tasks, research | Read flows; supported writes gated by approval; unavailable providers and stale evidence handled clearly | One bounded provider-backed backend Calendar read passed with no event content exposed; Calendar device/UI, Gmail, tasks and research end-to-end checks remain open. Gmail sending remains deliberately unavailable |
| Finance and calendar workspaces | Avanza/Crypto positions remain private and non-transactional; per-currency values and stale/unpriced states are honest; Calendar is Monday-first with weekend distinction, all-day safety and bounded governed reads | The [schema-0.42 workspace release](releases/2026-09-07-a7601b7-staging.md) records backup, migration, UI and Finance evidence. The [diagnostic backend release](releases/2026-09-08-db1d17c-staging.md) records the safely classified OAuth failure, and the [public OAuth information release](releases/2026-09-08-131034f-staging.md) records the prerequisite pages, branding and In-production publication. The [Calendar configuration release](releases/2026-09-09-calendar-v2-staging.md) records matching owner consent, validated version-2 credential references, a configuration-only backend rollout, one successful bounded provider-backed read returning zero events, and the separately action-time-confirmed `LIOS42` synthetic archive. Android phone/tablet, installed-Windows owner checks, and stability evidence remain open; automatic market quotes are not part of this release |
| Proactivity | Owner-approved schedule, grounded brief, quiet hours, duplicate prevention, delivery and stand-down | Exact per-rhythm activation approval plus coordinated database/scheduler verification; external notification delivery needs a design |
| Voice | Existing foundation: transcript correctness, cancel, permission denial, unavailable service and spoken response stop. Planned late-Package-6 extension: expressive Swedish/English real-time conversation, natural turn timing, interruption and recovery; see the [real-time voice plan](REALTIME_VOICE_PLAN.md). | Close the core stability entry gate first. Then complete provider/cost evaluation, architecture decision, implementation, authorized staged deployment and measured Android phone/tablet owner acceptance with Windows regressions. The addition remains planning only. |
| Installation | Install, launch, sign-in expiry, update, offline explanation, keyboard/touch navigation | Complete the [physical-device and owner checklist](PERSONAL_V1_DEVICE_ACCEPTANCE.md); native Android and gateway completion remains tracked separately |
| Security and recovery | Auth/role denial, safe logs, pinned release, rollback, successful isolated restore with recovery timings | The [schema-0.41 release](releases/2026-09-06-8831381-staging.md) adds a fresh authenticated pre-migration backup, full schema-0.40 restore, migration rehearsal, live authority denials, pinned immutable images, unchanged runtime identities, safe logs and an immediate application rollback path. Recurring cadence and remaining live/device evidence stay open. See [known risks](KNOWN_RISKS.md). |
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

## Chat memory recovery correction — 2026-09-06

The Astra review reproduced a separate recovery gap: a permitted memory correction could commit
before a model failure, while the enclosing turn was marked `failed` (safe to resume). The paired
English/Swedish regression failed before the fix. Memory effects were not covered by the email
dispatch marker, and deferred capture happens after `response_ready`, too late for a backward
transition in the existing ordered progress stages.

[Migration 041](../memory/migrations/041_chat_memory_effect_fencing.sql) adds a narrow, attempt-fenced
write-ahead uncertainty marker independent of model progress. It preserves existing role membership,
tables and stored data. Each actual capture write (store, proposal, correction or forgetting) must
pass its guard first. A handled failure after a write is uncertain; a process loss after the marker
cannot make the same turn safe to repeat on lease expiry. Missing schema capability or a stale guard
blocks the memory write and reports an unverified capture instead of silently using an unfenced path.
Legacy requests without a turn ID still report durability unavailable; this is not an exactly-once
claim or a new provider reconciliation mechanism.

The complete manifest through 0.41 passed on a fresh local container using the CI-pinned Supabase
PostgreSQL image. The rehearsal checked data preservation, replay rejection, function ownership,
existing role separation, wrong hash/token and null-token rejection, expired-lease rejection,
repeat guards, late writes after `response_ready`, and process-loss uncertainty. These are synthetic
local results. Migration 041 and the matching application were subsequently deployed through the
[recorded staging release](releases/2026-09-06-8831381-staging.md); provider-backed bilingual memory
mutation and uncertain-effect acceptance remain open.

Backend `pytest -q` passed 1,062 tests; Ruff passed for the backend and migration harness. The
upstream Starlette/AnyIO alias warning remains visible. Run these commands from `backend/`, as the
component test configuration requires; a repository-root invocation is not equivalent.

### Staging entry and rollback for this correction

Follow the existing [migration workflow](MIGRATION_WORKFLOW.md) and
[deployment workflow](DEPLOYMENT_WORKFLOW.md). Obtain exact staging authorization and verified
no-additional-charge coverage; make and validate a fresh pre-041 encrypted backup through private
operator prompts. Confirm target schema 0.40 and the new file checksum, rehearse, then apply the
reviewed migration once before deploying the matching application. Existing 0.40 staging evidence
and an older restored backup do not prove this new operation has happened.

The additive function leaves the previous application schema-compatible; keep the prior immutable
image and rollback revision. An application rollback does not undo memory writes or close the old
recovery defect. Do not delete memory or remove the function as a rollback shortcut. An application
deployed ahead of 041 must fail closed on durable-turn capture, not pretend all memory journeys work.
After rollout, verify permitted and denied calls and bounded bilingual recovery journeys before
recording the finding as closed. Existing affected outcomes may need owner reconciliation, not an
automatic retry. OM-003 remains gated; unrelated eligible personal-use work continues.

## Private-proposal rollout review — 2026-09-06

The Astra readiness review found that automatic Theo proposals did not carry `source_private_to_li`.
The existing nine-argument proposal API has no such field, and the canonical approval function in
migration 005 writes `private_to_li = FALSE`. This could turn private-source capture into shareable
memory after review. No historical migration was changed.

The application now rejects a private-source capture batch containing a Theo proposal before any
write or effect marker. It does not bypass Theo with a direct store, silently discard privacy, or
claim successful capture. Shared-source proposals retain their normal guarded path. Private-source
proposal support is an explicit residual limitation pending a separate end-to-end privacy-preserving
proposal design; existing proposal/memory records were not inspected or reclassified.

Two synthetic English/Swedish private-proposal regressions reproduced the missing rejection before
the fix. Shared-source controls and HTTP-level tests cover unchanged proposal behavior and a visible
capture error without an external memory effect. Backend `pytest -q` passed 1,068 tests and Ruff
passed; the upstream Starlette/AnyIO alias warning remains visible. These are local mocked results, not live-provider,
physical-device, owner, or stability acceptance.

A read-only Cloud Run check on 2026-09-06 confirmed backend `li-os-release-2746421` and web
`li-os-web-release-2746421` remain Ready at 100% traffic. This does not independently verify current
database schema; schema 0.40 remains the last recorded database evidence. No deployment, migration,
provider call, backup access, or personal-record inspection occurred in this review.

KR-011 remains open for provider-backed bilingual privacy and uncertain-effect acceptance, not for
deployment. The fresh authenticated pre-041 backup, full isolated schema-0.40 restore, rehearsal,
schema-0.41 migration, and matching application rollout are recorded in the
[release evidence](releases/2026-09-06-8831381-staging.md). No personal records were inspected or
reclassified. OM-003 remains gated by the outstanding core-stability and acceptance requirements.

## Local Home and Workspace recovery evidence — 2026-09-06

Focused dependency-free browser regressions now cover the owner-visible recovery states in both
chat surfaces. Home preserves one stable turn identity across a failed or uncertain retry, keeps the
draft, displays the backend's partial-completion guidance, and renders separate warnings when memory
capture or durable replay confirmation is unavailable. Specialist Workspace proves the same stable
identity and draft behavior, now preserves the specific uncertainty guidance instead of replacing it
with a generic failure, and reports both memory-capture and durability uncertainty without claiming
that anything was saved or changed. Existing tests continue to cover changed-request identities,
reload recovery without message content in browser storage, concurrent-submit suppression and
unavailable saved history.

The complete frontend checks passed: Ruff, 93 Python tests, compileall and 85 Node browser tests.
The upstream Starlette/AnyIO alias warning remains visible. A local synthetic rendering of the
Workspace uncertainty state was also measured at 390 × 844, 800 × 1280 and 1440 × 900 CSS pixels.
At each size the status and draft remained visible, the page and chat log had no horizontal overflow,
and the Send control remained at least 44 CSS pixels high. This is local simulated layout and
contract evidence only; it is not staging, physical Android, installed-Windows, microphone or owner
acceptance.

## Post-0.41 read-only web and accessibility check — 2026-09-06

After the schema-0.41 rollout, the signed-in staging Home, Specialists, Marco Workspace, specialist
History and Statistics, global History, and Settings views were opened without submitting a chat,
changing settings, uploading a file, or mutating memory. Across those visible views, DOM-backed
measurements found no horizontal page overflow, unnamed enabled controls, or displayed images without
alternative text. Visible interactive controls met the 44 CSS-pixel target. Sampled keyboard focus
used a visible outline, and the native specialist portrait dialog exposed its name and role, focused
its Close control, and returned focus to the opening portrait button after Escape. The Statistics
view retained textual counts and explanations alongside its visual presentation. No client browser
errors were recorded during the check.

The Settings view truthfully showed the `CM` owner-photo fallback and the choose, save, and remove
controls without changing the current photo. The page linked its web manifest and displayed install
guidance, but the audit browser was running as a normal tab rather than an installed app. The current
frontend suites also passed locally: Ruff, 93 Python tests, compileall, and 85 dependency-free browser
tests; the upstream Starlette/AnyIO alias warning remained visible.

This is bounded staging-read and local automated evidence, not a full WCAG conformance claim. No
screen reader, actual Windows 200% zoom, offline transition, installed Windows PWA, physical Android
phone/tablet, microphone, provider-backed response, owner acceptance, or stability period was tested.
Those rows remain `NOT RUN` in the
[device and owner checklist](PERSONAL_V1_DEVICE_ACCEPTANCE.md), which now targets the recorded
[schema-0.41 release](releases/2026-09-06-8831381-staging.md).

## Live bilingual specialist-routing finding — 2026-09-06

After the owner confirmed an existing Anthropic API credit balance and disabled auto-reload, a
bounded signed-in staging check used one synthetic, non-personal comparison in English and its
Swedish equivalent. The English request invoked Nora and recorded her recommendation. The Swedish
request returned a Swedish Li response but created no Nora recommendation. No file, external action,
memory correction, forgetting request, personal fact, or existing personal-record inspection was
part of the check.

The deployed router recognized Swedish `Be <specialist> ...` only at the start of the entire
message or after a narrow modal phrase. A harmless sentence before the instruction therefore changed
the Swedish outcome, while English `Ask <specialist> ...` remained explicit anywhere in the request.
The repository correction accepts `Be` at a later sentence or clause boundary and preserves the
existing quoted-example, name-only, opt-out, disclosure, and maximum-specialist guards. A paired
regression failed against the prior logic and passes with the correction. The full backend suite
passes 1,081 tests and Ruff passes; the upstream Starlette/AnyIO warning remains visible.

This is a live staging failure plus a locally verified repository correction. It is not a deployed
fix. The corrected backend requires an authorized reviewed rollout, followed by the same bounded
Swedish check and activity-record verification before bilingual live routing can pass. The two
synthetic chat turns remain ordinary staging history; no destructive cleanup or personal-data
operation was performed.

## Live routing correction deployed — 2026-09-06

The [backend-only release](releases/2026-09-06-e46b509-staging.md) supersedes the undeployed status
in the earlier finding above. After authenticated candidate readiness and schema 0.41 verification,
`li-os-release-e46b509` was promoted to 100% backend traffic. One synthetic Swedish Home retest
produced an actual recorded Nora recommendation and a completed Swedish Li response. The web remains
on `8831381`. This closes the narrow reproduced routing defect, not KR-011, full bilingual language
quality, historical privacy, uncertain-effect reconciliation, device, owner or stability acceptance.

The live retest also exposed that Nora's recorded structured recommendation was in English despite
the Swedish conversation. Li's final response correctly remained Swedish, so this did not change the
routing result. The specialist prompt now applies the established conversation-language rule to all
human-readable JSON values while keeping field names, evidence, privacy, routing and authority
unchanged. Paired English/Swedish prompt-wiring regressions cover the correction locally. Generated
language quality and deployment of this follow-up remained unverified at that point.

The [2026-09-07 backend release](releases/2026-09-07-0fc39a7-staging.md) subsequently deployed this
specialist-language correction after candidate denial, health, authenticated readiness and schema
checks. After read-only verification of USD 12.02 prepaid credit and disabled auto-reload, one
synthetic Swedish Home turn invoked Nora and produced both her recorded recommendation and Li's
completed reply in natural Swedish. The release record contains the bounded evidence. This closes
the narrow reproduced specialist-language mismatch, not universal bilingual quality, KR-011,
physical-device, owner or stability acceptance.

## Privacy and recovery acceptance review — 2026-09-07

The combined focused privacy/recovery/budget suite passed 117 synthetic tests, including all 5
budget cases. The full normal backend suite passed 1,084 tests and skipped the four deliberately
opt-in database cases; the upstream Starlette/AnyIO warning remained visible. A new opt-in local acceptance
harness passed four EN/SV integration cases against a dedicated localhost-only disposable database
at schema 0.41 with fake providers. It exercised real application/database history, recall, capture,
correction and turn-recovery paths; inspected the complete fake-provider specialist packet; and
proved exact replay after a post-write failure caused no additional write or fake-provider call. The
disposable container and synthetic records were removed after the run. No live calls, personal-record
reads, staging changes or backup access occurred. The
[bounded acceptance procedure](TESTING_AND_AUDIT.md#kr-011-bounded-privacy-and-recovery-acceptance)
maps the remaining gaps to existing tests and specifies isolation, exact authorization, cost limits,
packet-level observations and uncertainty reconciliation before any future live trial. The local
fake-provider portion is implemented and executed; provider-backed acceptance and retrospective
owner-record decision remain unexecuted. This is evidence progress, not closure of KR-011.
OM-003 remains gated by the outstanding core privacy/recovery, owner/device and stability evidence.

## Provider trial preparation — 2026-09-07

The [bounded provider trial](TESTING_AND_AUDIT.md#provider-trial-preparation--2026-09-07) is locally
implemented and fake-provider rehearsed against a fresh disposable schema-0.41 database. Its four
EN/SV cases passed with 10 mock calls; 30 guard/isolation tests passed. The full backend suite passed
1,113 tests before the additional passing local-Docker regression, with four opt-in skips.
The existing Starlette/AnyIO warning remains visible. This adds
whole-trial spend/call/turn controls and canonical-schema replay fingerprints, not new live evidence.
Read-only billing showed USD 11.99 prepaid and auto-reload off. No provider calls, deployment,
staging migration, personal-record inspection, or backup access occurred. The live trial awaits
private credential entry and fresh coverage at execution. KR-011 remains open; subsequent Workspace
provider acceptance, the historical-record decision, device/owner evidence and stability remain
distinct outstanding requirements. OM-003 remains gated.

## Privacy and recovery readiness review — 2026-09-09

The [existing bounded trial](TESTING_AND_AUDIT.md#readiness-review--2026-09-09) was blocked locally
by a stale schema-0.41 check after the manifest advanced to 0.42. Its corrected manifest comparison
passed the four existing EN/SV privacy/recovery cases at schema 0.42 with 10 fake calls; the full
backend suite passed 1,171 tests with four intentional opt-in skips. This adds local evidence and
repairs trial readiness; no live provider test or staging change occurred. KR-011 remains open for
real-provider acceptance, reconciliation and the separately authorized historical-record decision.
OM-003 remains gated by those relevant core findings and the applicable owner/device and stable-use
requirements. Finance archive and Calendar-read acceptance do not substitute for these observations.

The later [first provider attempt](TESTING_AND_AUDIT.md#first-provider-attempt-and-safe-checkpoints--2026-09-09)
stopped at the English synthetic correction precondition after four settled calls. English privacy
completion is inferred from control flow and the ledger; recovery and Swedish cases remain unproven.
The failed exact-value lookup does not prove no effect. Local checkpoint diagnostics preserve
future bounded observations without relaxing acceptance or authorizing another live run. KR-011,
OM-003, owner/device and stability requirements remain open.

The subsequent [correction verification refinement](TESTING_AND_AUDIT.md#correction-verification-refinement--2026-09-09)
reproduced the strict-string/domain harness defect with realistic fake-classifier statements and
replaced it with governed replacement-record, source-turn and persisted-content proof. The local
EN/SV rehearsal passes; no new real-provider evidence is claimed and the original ledger is preserved.

The later [PR-104 provider-validation result](TESTING_AND_AUDIT.md#pr-104-provider-validation-result--2026-09-09)
adds a provider-backed English historical-privacy pass. Its English recovery case could not prove
exactly one governed correction dispatch, so the post-response uncertainty/replay case was not
reached; both Swedish cases remain unrun. The one-use ledger and disposable-resource cleanup are
preserved evidence, not permission to retry or proof of no effect. KR-011 and OM-003 remain open.

The subsequent [content-free diagnostic hardening](TESTING_AND_AUDIT.md#content-free-recovery-diagnostic-hardening--2026-09-09)
adds fixed boolean-only checkpoints for classifier disposition, governed apply, target resolution
and correction dispatch. A local schema-0.42 fake-provider rehearsal passed the four EN/SV cases and
removed its disposable resources. This prevents the same category of ambiguity in a separately
authorized future trial, but it neither reconstructs the prior provider response nor authorizes a
retry. No new live evidence, staging change or personal-record access occurred; KR-011 and OM-003
remain open.

The later [unresolved-case continuation preparation](TESTING_AND_AUDIT.md#unresolved-case-continuation-preparation--2026-09-09)
adds a new exclusive-created ledger identity for only English recovery, Swedish historical privacy
and Swedish recovery. It verifies the hashes of all three earlier immutable live ledgers and does
not repeat the already passed provider-backed English privacy case. A local schema-0.42 rehearsal
passed those three cases with seven fake calls and removed its exact disposable resources and dry
ledger. The unchanged four-case fake path also passed with 10 calls; the full backend suite passed
1,237 tests with four intentional skips and the upstream warning visible. A read-only account check
showed USD 11.92 prepaid with auto-reload off at 18:45 UTC. This prepares but does not authorize or
perform another live attempt; no personal data, staging service or protected output was touched.
KR-011 and OM-003 remain open.

The [content-free trial result](TESTING_AND_AUDIT.md#content-free-trial-result-and-explicit-recovery-fixture--2026-09-09)
then identified no parsed classifier candidates in the first English recovery case: no governed
apply or correction dispatch started. One provider call settled; neither Swedish case ran. All four
live ledgers remain preserved. Local EN/SV fixture clarification and an earlier classifier stop
passed the seven-call fake rehearsal and 1,244 backend tests, but do not establish a live correction
fix or authorize another attempt. KR-011 and OM-003 remain open; staging is unchanged.

The owner subsequently authorized [one recovery-fixture validation trial](TESTING_AND_AUDIT.md#authorized-recovery-fixture-trial-preparation--2026-09-09).
Its new exclusive selector preserves all four live ledgers and skips English privacy. Local guard
tests and the seven-call fake rehearsal passed; live execution still requires fresh coverage and
private key entry. No new provider-backed result or staging change was claimed by that preparation.

The subsequent [recovery-fixture provider-backed result](TESTING_AND_AUDIT.md#recovery-fixture-provider-backed-result--2026-09-09)
passed English recovery, Swedish historical privacy and Swedish recovery with seven calls and a
USD 0.074364 conservative bound. Combined with the earlier English privacy pass, the four baseline
cases now have local provider-backed evidence. All five live ledgers remain preserved; the isolated
container is absent. No staging or device acceptance is added. KR-011 and OM-003 remain open for
remaining coverage, deployed reconciliation, historical-record decisions, device/owner and stability
evidence. Do not rerun this completed trial or repeat the already passed English privacy case.

## Remaining KR-011 acceptance review — 2026-09-10

The [remaining-acceptance review](TESTING_AND_AUDIT.md#remaining-acceptance-review--2026-09-10)
identifies the unproven later-Workspace and derived-capture provider observations without repeating
the passed baseline trials. Existing focused tests passed 61 cases with the upstream warning visible.
The proposed local extension now passes one two-turn chain per language against real disposable
schema-0.42 storage and fake providers. It verifies a genuinely Swedish follow-up, Li-only historical
answer propagation, complete specialist-packet exclusion, private captures with exact current-turn
provenance, and replay with no additional provider call, conversation row or canonical-memory change.
The unchanged recovery baselines also passed, for four opt-in harness cases total; the disposable
container and volume were removed. Provider-backed chained execution and any deployed reconciliation
trial retain separate authorization gates. No new provider, deployment, historical-record, device or
stability evidence is claimed. KR-011 and OM-003 remain open. Android-phone installation, standalone
launch and Home layout can be checked by the owner independently, without submitting chat or reading
another provider.

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
