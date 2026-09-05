# Personal-use v1 device and owner acceptance

## Purpose

Use this checklist to record the remaining owner-observed evidence for the installable Li web app on
the owner's Android phone, Android tablet, and Windows laptop. It supplements the
[personal-use v1 acceptance checklist](PERSONAL_V1_ACCEPTANCE.md) and does not replace the
[security boundaries](SECURITY_BOUNDARIES.md), [deployment workflow](DEPLOYMENT_WORKFLOW.md), or
[2026-09-05 staging release record](releases/2026-09-05-a864076-staging.md).

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
| Grant microphone permission and speak once in English and once in Swedish | The transcript is correct before submission, exactly one normal chat turn is sent, and spoken output can be stopped | NOT RUN |
| Deny microphone permission, then cancel an active attempt | Li explains the denial/cancel state and typed chat remains usable | NOT RUN |

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

The encrypted pre-migration backup passed full authentication and archive-catalogue validation. A
restore is still unproven. Complete the restore drill only in an isolated non-production database,
with the owner entering the encryption passphrase outside chat. Record the source-backup hash,
restore start/end time, schema version, validation queries, retrieval result, cleanup disposition, and
RPO/RTO findings without recording personal data or secrets.

Stable-use acceptance requires an owner-observed period of ordinary use. Record the agreed start and
end dates, devices used, completed journeys, errors, uncertain outcomes, unexpected duplicates,
security/privacy findings, and whether rollback remained available. Health checks alone are not
normal-use evidence.

## Evidence record

| Field | Value |
| --- | --- |
| Deployed release | `release-c3f2d51` |
| Backend revision | `li-os-release-c3f2d51` |
| Web revision | `li-os-web-release-c3f2d51` |
| Database schema | `0.39` |
| Owner test start | NOT RECORDED |
| Owner test end | NOT RECORDED |
| Devices and versions | NOT RECORDED |
| Critical findings | NOT ASSESSED |
| Restore drill | NOT RUN |
| Stable-use observation | NOT STARTED |

Completion requires all applicable rows to pass or a residual limitation to be explicitly accepted
in the authoritative decision/risk records. A successful device check does not authorize wider
runtime powers, spending, provider writes, or production deployment.
