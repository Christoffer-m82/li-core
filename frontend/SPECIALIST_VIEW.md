# Specialist workspace

Open a specialist from Home or Agent Status & Analytics. **Workspace** (formerly Current work)
is the default tab, with a shared chat for the owner, Li and the selected specialist. Opening
the view only reads data; pressing **Send** starts a consultation through the existing authenticated
Li chat boundary. No new specialist authority is granted. It inherits the [appearance library](APPEARANCE.md).
The specialist header, Home cards, and analytics cards share the selected portrait with an initials
fallback. Images are decorative beside readable names and roles, and never change with the theme.
Portraits depict fictional AI characters, not real staff or verified professional credentials.

## Shared conversation

On the Specialists analytics page, the entire specialist card opens **Workspace**. The separate
**History** text button opens **History** directly, including after its data finishes loading.
These are two sibling native buttons, not nested buttons: both support keyboard activation and
visible focus. Home's specialist cards continue to open Workspace.

The conversation selector keeps cases separate. **New conversation** starts without another case's
chat context; selecting a retained case shares its bounded recent context for follow-ups. The input
stays below the scrollable timeline. Messages are oldest first, newest at the bottom. **Jump to latest**
returns to the bottom; Refresh preserves the reading position when reviewing older messages.

| Sender | Presentation |
| --- | --- |
| Owner | Green bubble aligned right, readable name and initial placeholder. A personal profile-photo setup is not implemented yet. |
| Li | Lavender bubble aligned left, Li placeholder reserved for a future portrait. |
| Specialist | Blue bubble aligned left, existing selected portrait with initials fallback. |

All messages show the recorded local date/time (or explicitly say the time was not recorded).
Distinct labels and alignment supplement color; fixed light bubble tokens retain dark readable text
inside every appearance. No read receipts or read status are collected or displayed.

Choose **Li + specialist** or **specialist directly · Li included**. Both send through `/api/chat`
with an allowlisted `workspace_specialist` and a `workspace_recipient` of `group` or `specialist`.
The backend consults that specialist even for short follow-ups and Li still synthesizes the result;
direct addressing asks Li to keep her synthesis brief. Existing evidence and action-approval rules
still apply. Proposed action cards appear in the main Li chat, not as automatically executed actions.
The addressing choice is per turn, not a separate private channel or permission grant.

The timeline joins real owner/Li messages with the selected specialist's recorded recommendations.
The owner's saved request is never relabelled as Li speaking. Supporting findings and questions
expand inside the specialist bubble; History retains routing details, evidence and activity filters.
Omitted or failed recommendations appear as system notices, not invented agent dialogue.

Files use the existing authenticated temporary upload endpoint (10 MB maximum). Text, Markdown,
CSV and JSON can supply extracted text; a validated PDF/image is not described as attached unless
analysis text is actually returned. Extracted context must fit the existing 6,000-character limit.
Unsupported/oversized/failed analysis is explained; no file is silently saved. Remove attachment
clears its in-memory context. Successful sending clears the draft and attachment; failed sending
keeps the draft and warns to check history before retrying because an uncertain request may have
reached the server. Switching cases asks before discarding unsent work. Signing out clears it.

### Current limits

- The existing conversation function returns the latest **40 messages**; the activity API returns
  up to **50 specialist records**. Both limits are visible. This is not complete all-time history.
- Automatic polling, older-message pagination, owner-photo setup, and retained file attachments
  are not part of this change. Refresh checks for new activity.
- Follow-up model context remains bounded by the existing runtime, not the entire visible history.
- If saving fails, the returned reply stays visible with a warning but may disappear after reload.
- No browser storage or offline cache holds chat data. Switching specialists invalidates late UI
  responses; it does not cancel a request already accepted by the backend.

Release compatibility: publish the backend support for the two workspace fields before the
frontend composer. An older backend may ignore unknown request fields and use its normal routing
instead. This repository change does not deploy either service or modify an external database.

## Statistics

The **Statistics** tab presents measured information from the same up-to-50 interaction snapshot.
It does not issue additional analytics calls or reuse potentially stale, differently scoped totals
from the Specialists overview. Choose All loaded records, Last 7 days or Last 30 days; date filters
use consultation start time and UTC calendar days. Missing/future dates are reported explicitly
and excluded from dated charts and date-filtered selections.

- Summary cards: consultation count, active days, average response, median response and completion rate.
- Labelled horizontal bars with exact counts: completed/failed/in-progress/unknown outcomes,
  solo/collaborative/unknown consultations, explicit used/not-used/unmeasured attribution to Li,
  and response-time buckets (under 5, 5–15, 15–30, 30+ seconds).
- Daily activity for the last 14 UTC calendar days, within the chosen selection. A zero is no matching
  loaded record, not proof of no activity beyond the snapshot.

Charts use zero-based scales, existing appearance tokens and semantic tables for direct labels and
values. Panels stack on narrow screens. Each chart has its own labelled count scale. Timing summaries
use only completed consultations with finite nonnegative elapsed times and display their sample size.
Completion rate is completed divided by completed plus failed; in-progress/unknown records are excluded.
Empty denominators and missing timing measurements say Not measured, never zero percent/seconds.
Completion and attribution are not measures of accuracy, helpfulness or real-world action success.

Refresh updates both history and statistics without changing the chosen tab. After a send,
only a validated activity response updates the History,
summary and Statistics together. Late responses for another specialist or an older refresh are ignored.
Opening Workspace after loading a conversation in a hidden tab scrolls to the latest message once;
subsequent tab switches do not force a reader away from older messages.
A failed manual refresh clears old statistics and shows an error rather than zero activity;
sign-out clears all displayed data.
Answer accuracy, owner satisfaction, time/money saved, token cost and real-world impact remain explicitly
unmeasured. Useful later additions are owner helpfulness feedback and verified action outcomes once
their underlying instrumentation is defined; no new tracking is silently introduced here.

## Portrait viewer

Ada, Theo and Heimdall have separate system-agent cards on Home, Agents and Backend, leading to
read-only profiles with their exact registry names/roles, purpose and boundaries. They share the
portrait viewer below, but are not added to the specialist history API or its analytics totals.
These profiles explicitly show defined responsibilities, not verified live work; no system-agent
conversations or private memory/security records are fetched. Li retains her existing orb identity.

The detail-page portrait is a button labelled “View full portrait of [name]”. Click, tap, Enter,
or Space opens a native modal dialog with the existing name and role above the original
1254 × 1254 image. The whole image fits the viewport without cropping; **Open original image**
opens the same public asset in a new tab for browser zoom, not a higher-resolution substitute.
No portrait is regenerated, renamed, or recompressed by this viewer.

The dialog uses the active theme's surface, text, accent, and radius tokens. Focus starts on
**Close**, stays inside the modal, and returns to the portrait button after Close or Escape.
Page scrolling is locked while open. Navigation or sign-out also dismisses the viewer.
A loading message becomes a retry instruction if the asset fails; reopening retries the image.
Only the explicit local portrait roster is accepted, and late events from a previous image
cannot overwrite the current status. Opening a portrait does not call an agent or change data.

## Reference analysis

The owner-supplied `li-os-agent-view.html` is a bundled design mockup, not runtime evidence. Its
embedded template and sample data were inspected as text, without running its scripts. The design
centres on Nora but is appropriate for every specialist in the current roster.

| Reference element | Adaptation |
| --- | --- |
| Profile and role | Use the existing roster; no invented agent biography or capabilities. |
| Left-hand conversation history | Selectable interaction history, request/response search, and status filter. An interaction is not necessarily an entire conversation. |
| Central Li/agent chat | Real owner/Li messages joined with explicitly labelled recorded specialist recommendations. |
| Live/History switch | Workspace is the default shared chat; History retains record inspection, with manual Refresh and check time. |
| Current task sidebar | Status, timestamps, routing reason, selection mode, collaboration mode, and whether sources are still needed. |
| Evidence progress | Recorded verification/freshness metadata and citation count only; no invented sources-found/analyzed progress bars. |
| 78% confidence | Omitted. Model self-assessment is not a calibrated measure of correctness. |
| Likely deliverables | Actual findings, recommendation, assumptions and open questions. No fictional completion checklist. |
| Agent statistics | Counts and mean completed duration from the loaded interactions, labelled with scope. |
| Direct agent composer | Shared Workspace composer selects group or specialist addressing; Li remains included and action authorities stay unchanged. |

The strongest part of the reference is the separation between navigation, work, and supporting
evidence. The implementation keeps that three-column structure on wide screens and stacks the
record and evidence on narrower screens. On phones the history list has a bounded scroll area so
older entries do not push the selected response indefinitely down the page. Search and status
controls have explicit labels, and selected buttons have pressed states and visible keyboard focus.

## What is recorded

Sources of truth are the [runtime result contract](../backend/app/specialist_runtime.py),
[persistence path](../backend/app/li_runtime.py), and
[interaction query](../memory/migrations/026_generalized_specialist_orchestration.sql).
Reading that migration is not evidence it has been applied to any external database.

The current endpoint returns up to 50 interactions, active first then most recently updated.
Search, counts and durations apply only to that returned set, not all-time activity. A mean duration
uses only completed records with a finite nonnegative `elapsed_ms`. A missing duration is not zero.
There is no older-history pagination in this view. Active records are selectable in History and
appear as notices in their associated Workspace conversation.

Responses using temporary upload context may intentionally omit content. The UI explains that
omission, rather than reconstructing it. Unknown fields remain unknown. A completed consultation
does not prove that its recommendation was used, that an action ran, or that an outcome improved.
The recorded `used_in_final` flag is displayed only when present; otherwise it is not measured.
The original conversation can be opened through the existing authenticated History view.

## Safety and failure states

- All dynamic record content is rendered as text, not executable HTML or Markdown links.
- Requests remain behind the existing owner session. No new write endpoint is added.
- Interaction content is held in page memory, not localStorage or the service-worker cache.
- Sign-out clears this view's data and invalidates pending specialist reads.
- Switching specialists invalidates late responses from the previous specialist.
- Refresh clears the old snapshot while fetching; errors remain visibly unavailable, not empty.
- The BFF returns a generic 502 for failed/malformed upstream history instead of claiming no activity.
- Sending explicitly addresses a specialist through Li's governed runtime, never a separate agent endpoint.
- No polling, database changes or deployments are introduced.

See the authoritative [security policy](../system/security-policy.md) and
[storage policy](../memory/storage-policy.md) for wider rules.

## Recommended future insights

1. **Evidence you can inspect:** link each recommendation to retained citations and retrieval dates,
   with a clear distinction between a source being retrieved and actually supporting a claim.
2. **What changed because of this work:** join specialist advice to Li's final answer and governed
   action outcomes. Do not infer action completion from consultation completion.
3. **Learning over time:** an explicit helpful/not-helpful assessment with optional owner notes;
   avoid automatic permanent memory writes or invented personal-impact scores.
4. **Disagreement and revision:** show recorded differences between specialists and changes to advice,
   with evidence, instead of presenting hidden reasoning or simulated agent conversations.
5. **Longer history:** authenticated pagination and date filters before claiming month/all-time coverage.

These are recommendations, not implemented features or permission to expand data collection.

## Validation

Run the [frontend checks](README.md#local-validation), including `node --test tests-js/*.test.mjs`.
The specialist tests cover metrics, filters, text-only rendering, missing/temporary responses,
failed refresh/retry, specialist-switch races, sign-out invalidation, and conversation identifiers.
Workspace tests cover chronology, author provenance, case isolation, explicit recipients, duplicate
send prevention, failed persistence, draft retention, attachments, and scroll position. Backend/BFF
tests verify selection forwarding, rejected system-agent/private recipients and Li's continued role.
BFF tests cover upstream errors and malformed responses for both roster and specialist history.
Use only synthetic records for visual checks; a local preview is not proof of deployment or
real Android-device behaviour.
