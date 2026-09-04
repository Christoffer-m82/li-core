# Specialist workspace

Open a specialist from Home or Agent Status & Analytics to inspect recorded work. The view uses
the existing authenticated specialist-interaction API; it does not start a consultation or grant
new specialist authority. It inherits the [appearance library](APPEARANCE.md).
The specialist header, Home cards, and analytics cards share the selected portrait with an initials
fallback. Images are decorative beside readable names and roles, and never change with the theme.
Portraits depict fictional AI characters, not real staff or verified professional credentials.

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
| Central Li/agent chat | The saved request and structured specialist response, explicitly not a verbatim transcript. |
| Live/History switch | Current-work snapshot and recorded history, with manual Refresh and check time. |
| Current task sidebar | Status, timestamps, routing reason, selection mode, collaboration mode, and whether sources are still needed. |
| Evidence progress | Recorded verification/freshness metadata and citation count only; no invented sources-found/analyzed progress bars. |
| 78% confidence | Omitted. Model self-assessment is not a calibrated measure of correctness. |
| Likely deliverables | Actual findings, recommendation, assumptions and open questions. No fictional completion checklist. |
| Agent statistics | Counts and mean completed duration from the loaded interactions, labelled with scope. |
| Direct agent composer | Continue with Li prepares an editable draft in the existing composer; it does not send automatically or create a new direct-agent authority. |

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
There is no older-history pagination in this view. Multiple active records are displayed separately.

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
- No polling, direct agent message sending, database changes or deployments are introduced.

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
BFF tests cover upstream errors and malformed responses for both roster and specialist history.
Use only synthetic records for visual checks; a local preview is not proof of deployment or
real Android-device behaviour.
