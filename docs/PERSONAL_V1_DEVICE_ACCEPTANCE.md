# Personal-use v1 device and owner acceptance

## Purpose

Use this checklist to record the remaining owner-observed evidence for the installable Li web app on
the owner's Android phone, Android tablet, and Windows laptop. It supplements the
[personal-use v1 acceptance checklist](PERSONAL_V1_ACCEPTANCE.md) and does not replace the
[security boundaries](SECURITY_BOUNDARIES.md), [deployment workflow](DEPLOYMENT_WORKFLOW.md), or
[2026-09-05 staging release record](releases/2026-09-05-a864076-staging.md). The current device target
is backend [Calendar diagnostic release](releases/2026-09-08-db1d17c-staging.md) `db1d17c` with web
[public OAuth information release](releases/2026-09-08-131034f-staging.md) `131034f` and database
schema 0.42. The earlier
[specialist-language release](releases/2026-09-07-0fc39a7-staging.md) remains the backend application
rollback target; web `a7601b7` is the immediate web rollback target.

Repository tests and synthetic browser sizes do not complete this checklist. Record only behavior
seen on the named device against the deployed staging URL. Do not put passwords, tokens, private
message contents, personal memory, email bodies, calendar details, or recovery passphrases in this
file, screenshots, issues, or pull requests.

## Before testing

- Confirm the address is `https://li-os-web-7gyegrz7vq-ew.a.run.app/` before signing in.
- Sign in with the approved Google account yourself. Codex must not operate the Google sign-in flow
  or read authentication material.
- Use harmless synthetic content, such as `LI-ACCEPTANCE-2026-09-05`, unless an ordinary existing
  record is sufficient for a read-only check.
- Do not activate a proactive rhythm, create a Calendar event, create a Gmail draft, delete a real
  record, or restore a database merely to complete this checklist. Those actions retain their exact
  approval and safety gates.
- For each failure, record the device, browser/app version, time, visible error, and whether retrying
  was safe. Do not repeatedly submit a request whose external outcome is uncertain.

## Physical-device procedure

Use the matrix below as the evidence record and follow this sequence on each named device:

1. Record the device model, operating-system version, browser version, and test time without adding
   account identifiers or private content.
2. Open the verified staging address in the normal browser, install Li using that browser's
   **Install app** or **Add to Home screen** control, and launch Li from the new icon. Record whether
   it opens without normal browser chrome; do not count an ordinary browser tab as standalone mode.
3. Complete the device-matrix rows in order. On Android, use the device's larger-text setting and
   touch navigation. On Windows, use keyboard-only navigation and the browser's actual 200% zoom;
   synthetic viewport or CSS-zoom results do not replace that check.
4. For the offline row, finish any active request first, disconnect the device, relaunch Li, and
   confirm the limited state is honest. Reconnect before submitting anything and verify that one
   deliberate request creates only one turn. Do not retry a request with an uncertain external
   outcome.
5. Return to the installed app after an ordinary browser reload/update check, sign out, and record
   `PASS`, `FAIL`, or `NOT RUN` for every applicable row. A failure needs the safe diagnostic details
   listed above, not a screenshot containing private data.

## Device matrix

Record `PASS`, `FAIL`, or `NOT RUN`; never turn `NOT RUN` into a pass.

| Check | Android phone | Android tablet | Windows laptop |
| --- | --- | --- | --- |
| Install or add Li to the home screen/desktop | NOT RUN | NOT RUN | NOT RUN |
| Launch in standalone app mode | NOT RUN | NOT RUN | NOT RUN |
| Sign in and sign out without exposing credentials | NOT RUN | NOT RUN | NOT RUN |
| Home loads without horizontal overflow | NOT RUN | NOT RUN | NOT RUN |
| Touch or keyboard navigation reaches every visible control | NOT RUN | NOT RUN | NOT RUN |
| Text remains usable with the device's larger-text setting | NOT RUN | NOT RUN | NOT RUN |
| Windows browser/app at actual 200% zoom | Not applicable | Not applicable | NOT RUN |
| Offline launch gives an honest limited/offline explanation | NOT RUN | NOT RUN | NOT RUN |
| Returning online recovers without duplicate submission | NOT RUN | NOT RUN | NOT RUN |
| Reload receives the deployed app update | NOT RUN | NOT RUN | NOT RUN |

## Authenticated owner journeys

Run these once on the most convenient signed-in device. Repeat layout-, touch-, voice-, and
installation-specific checks on each device where the matrix requires them.

| Journey | Expected result | Result |
| --- | --- | --- |
| Ask an ordinary typed question | One owner message and one grounded Li response appear; History reload shows the same completed turn | NOT RUN |
| Ask `Ask Nora to compare these options` and the Swedish equivalent `Be Nora jämföra de här alternativen` | Both requests select Nora under the same policy; the response identifies real specialist use without invented attribution | NOT RUN |
| Retry a deliberately interrupted read-only chat turn | The same turn recovers or reports its state without duplicating the owner message or action | NOT RUN |
| Open a specialist card, Workspace, History, Statistics, and the portrait viewer | Navigation, recorded evidence, unavailable states, name, role, thumbnail, and full portrait are correct | NOT RUN |
| Upload a harmless text file without Save | Li can use it for the current request, but it does not appear as a retained file after reload | NOT RUN |
| Upload the same harmless file with explicit Save, then reopen and download it | The private library lists one file and the downloaded bytes match; use the normal owner UI to remove the synthetic file afterward only if separately intended | NOT RUN |
| Inspect memory and history | Recall and provenance are truthful; proposed memory is visibly distinct from confirmed memory; correction/forgetting retains its confirmation boundary | NOT RUN |
| Switch among built-in and custom appearances, then export/import a custom appearance | Content does not change, contrast remains readable, and the custom appearance survives reload on that device | NOT RUN |
| Read Calendar, Gmail, tasks, and current research using harmless queries | Configured reads return grounded results or an honest unavailable/stale state; Gmail does not send | NOT RUN |
| Open the Calendar workspace, move between weeks, choose a month date, use Today, and refresh | Week starts Monday; Saturday/Sunday remain distinct without warning-like contrast; all-day events stay on their correct date; month cells reveal counts rather than private titles; unavailable reads are honest | NOT RUN — source is deployed; physical-device and provider-backed display evidence remain open |
| Open My Finances, switch between Avanza and Crypto, and use one clearly synthetic holding | Values remain separated by currency; unpriced/stale states are explicit; create/edit/archive affect only the synthetic holding; no broker login, market quote, trade, memory, or specialist sharing occurs | NOT RUN — source and schema 0.42 are deployed; physical-device owner journey remains open |
| Grant microphone permission and speak once in English and once in Swedish | The transcript is correct before submission, exactly one normal chat turn is sent, and spoken output can be stopped | NOT RUN |
| Deny microphone permission, then cancel an active attempt | Li explains the denial/cancel state and typed chat remains usable | NOT RUN |

## Planned enhanced voice acceptance gate

The two microphone rows above test the existing voice foundation. They do not accept the planned
real-time enhancement. After OM-003 completes its provider/cost evaluation, architecture decision,
implementation and authorized staged deployment, apply the audio-specific criteria in the
[real-time voice plan](REALTIME_VOICE_PLAN.md#evaluation-and-completion-criteria) on the Android phone
and tablet, with Windows regression coverage. Record owner acceptance before final release sign-off
includes enhanced voice. Until then this gate is **NOT ELIGIBLE / NOT RUN**, and unrelated device
acceptance may continue.

## Proactivity and scheduled work

The five proactive rhythm jobs were read-only verified as paused on 2026-09-05. Keep them paused until
the owner chooses a specific rhythm and approves its schedule, quiet hours, delivery behavior, and
stand-down test. The artifact-retention scheduler is separate from proactivity and remains enabled.

| Check | Expected result | Result |
| --- | --- | --- |
| Preview a rhythm without activation | Preview is grounded and does not resume a scheduler job | NOT RUN |
| Inspect quiet hours and duplicate-prevention explanation | The UI accurately describes the configured policy and does not claim a delivery occurred | NOT RUN |
| Activate and stand down one selected rhythm | Requires a separate exact owner decision and coordinated database/scheduler evidence | BLOCKED — owner decision required |

## Recovery and stability

The [2026-09-06 isolated restore drill](releases/2026-09-06-isolated-restore-drill.md) authenticated and
restored the earlier encrypted pre-migration backup, then advanced the disposable copy from schema
0.36 to 0.39 while preserving canonical counts and authority boundaries. No plaintext dump was
written. An independently encrypted replacement then passed authentication, catalogue validation, a
full schema-0.39 restore, and the same authority checks. Migration 040 and its matching application
were subsequently deployed and validated.

Before migration 041, a fresh encrypted staging backup passed authenticated archive validation and a
full isolated schema-0.40 restore and retrieval drill. Migration 041 then passed an isolated rehearsal
before it was applied once in staging, and the matching application release passed bounded read-only
validation. The complete evidence, authority checks, rollback target, and residual limitations are in
the [schema-0.41 release record](releases/2026-09-06-8831381-staging.md). The disposable restore target
was removed after review while encrypted release backups were preserved. Recurring recovery cadence
remains operational work; these results do not prove a production recovery or physical-device
behavior, and each restore remains labelled with the schema it actually restored.

Stable-use acceptance requires an owner-observed period of ordinary use. Record the agreed start and
end dates, devices used, completed journeys, errors, uncertain outcomes, unexpected duplicates,
security/privacy findings, and whether rollback remained available. Health checks alone are not
normal-use evidence.

## Evidence record

| Field | Value |
| --- | --- |
| Deployed release | Backend `release-db1d17c`; web `release-131034f` |
| Backend revision | `li-os-release-db1d17c` |
| Web revision | `li-os-web-release-131034f` |
| Database schema | `0.42` |
| Staging rollout | PASS — schema/UI/Finance evidence is in the [workspace release](releases/2026-09-07-a7601b7-staging.md); sanitized diagnostics, backend promotion and the OAuth-authentication failure classification are in the [backend release](releases/2026-09-08-db1d17c-staging.md); the public Google OAuth information documents, web promotion, branding update and In-production publication are in the [web release](releases/2026-09-08-131034f-staging.md). This is not successful Calendar-provider, physical-device, owner or stability acceptance |
| Owner test start | NOT RECORDED |
| Owner test end | NOT RECORDED |
| Devices and versions | NOT RECORDED |
| Critical findings | NOT ASSESSED |
| Restore drill | PASS — fresh pre-041 backup restored at schema 0.40 and migration 041 rehearsed locally on 2026-09-06 |
| Stable-use observation | NOT STARTED |

Completion requires all applicable rows to pass or a residual limitation to be explicitly accepted
in the authoritative decision/risk records. A successful device check does not authorize wider
runtime powers, spending, provider writes, or production deployment.
