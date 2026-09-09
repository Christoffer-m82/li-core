# Calendar OAuth configuration release: `calendar-v2`

## Status and scope

**Backend configuration deployed to staging and one bounded Calendar read passed on 2026-09-09.**
Cloud Run revision `li-os-calendar-v2` is Ready and serves 100% of backend staging traffic. Web
remains `li-os-web-release-131034f`, and the database remains at schema 0.42.

This configuration-only release retains the exact immutable backend image from
`li-os-release-db1d17c`. It changes only the numeric versions referenced by
`LI_OS_GOOGLE_CALENDAR_CLIENT_ID`, `LI_OS_GOOGLE_CALENDAR_CLIENT_SECRET`, and
`LI_OS_GOOGLE_CALENDAR_REFRESH_TOKEN`, from version 1 to version 2. No secret value is recorded here
or in Git.

The owner separately completed Google consent using the matching Li OS Web Staging credential set.
A private local validator confirmed that Google accepted the replacement client ID, client secret,
and refresh token together with the `calendar.events` scope before exactly one new numeric version
of each existing secret was created. The backend continued referencing version 1 until this
separately authorized rollout.

## Authorization, review, and cost gates

- The owner authorized a backend-only configuration deployment changing only those three numeric
  references, a zero-normal-traffic candidate, promotion after complete validation, and at most one
  bounded read-only Calendar test. The authorization excluded image, web, database, IAM, OAuth
  client, scope, provider, scheduler, billing, and personal-record changes.
- Read-only comparison against `li-os-release-db1d17c` confirmed the same immutable image digest,
  runtime identity, all non-Calendar numeric secret references, and every plain environment value.
  Exactly the three approved Calendar references changed from version 1 to version 2.
- Google documents standard Calendar API use as available at no additional cost and a daily
  no-additional-charge threshold far above this single request. No purchase, upgrade, billing
  change, automatic replenishment, or paid overage was enabled. See Google's
  [Calendar API usage limits](https://developers.google.com/workspace/calendar/api/guides/quota).

## Candidate and promotion evidence

- `li-os-calendar-v2` was created as a zero-normal-traffic candidate while
  `li-os-release-db1d17c` continued serving 100% of normal traffic.
- The candidate retained image
  `europe-west1-docker.pkg.dev/li-os-staging/li-os/li-os@sha256:4d76c5d1be8c3f1ca5c211b63a93f0e004cc3eadbcf2cc29fa723db323805a37`
  and runtime identity `li-os-runtime@li-os-staging.iam.gserviceaccount.com`.
- Backend IAM remained private. Public candidate health returned 403; IAM-authenticated health
  returned `ok`; `/ready` without the application token returned 401.
- The owner ran the masked candidate validator. Authenticated `/ready` passed, restricted database
  health reported schema 0.42, and the validator reconfirmed that only the three approved Calendar
  references used version 2. The token was not printed, logged, persisted, or sent to chat.
- No candidate ERROR-or-higher log entry was found. The validated revision was then promoted to
  100% traffic.
- Post-promotion checks reconfirmed public denial, IAM health, application-token enforcement, the
  unchanged image and identity, and web `li-os-web-release-131034f` at 100%. No ERROR-or-higher
  entry was found for the promoted backend revision.

## Single bounded Calendar read

The owner authorized at most one read-only Calendar test. A dated one-use runner verified
`li-os-calendar-v2` at 100% traffic, authenticated readiness, and schema 0.42 before exclusively
creating its durable dispatch marker. It then requested one `calendar.search` over the next UTC day,
with no query and a maximum of one result. Automatic retry was disabled.

The request completed successfully and returned zero events. Event contents were neither printed
nor saved. The test made no Calendar mutation, model call, personal-record write, database change,
web change, or retry. This establishes one provider-backed backend Calendar read with the replacement
credential set. It does not establish Calendar UI behavior on a physical device, broad provider
quality, owner acceptance, or stability.

## Post-release synthetic Finance archive

The owner later gave fresh action-time confirmation to archive only the active synthetic Avanza
holding `LIOS42`, named `Synthetic acceptance holding`. A dated one-use local runner first verified
backend `li-os-calendar-v2` and web `li-os-web-release-131034f` at 100% traffic, authenticated
readiness, and schema 0.42. It required exactly one matching active target before creating its
durable dispatch marker and calling the normal governed Finance archive capability once.

The request returned `archived`, and `LIOS42` was no longer active afterward. An in-memory
before/after fingerprint confirmed every non-target active Avanza holding was unchanged. No holding
value or other personal portfolio content was printed, logged, or written to disk. The tracked
schema-0.42 function archives by setting `archived_at` and `updated_at`; it does not delete the audit
record. No automatic retry, Calendar, memory, provider, schema, IAM, secret, scheduler, billing,
backend, or web deployment change occurred. The retained one-use marker prevents another dispatch
under this authorization. This proves the exact synthetic archive sub-gate, not the remaining
physical-device or owner journey.

## Recovery and remaining gates

`li-os-release-db1d17c` remains Ready at 0% and is the authorized backend rollback target. Returning
traffic to it would restore the previous three version-1 references and the known OAuth refresh-grant
failure while retaining the transport-log privacy correction. Application rollback does not alter
schema 0.42, the web service, Google OAuth configuration, secret versions, or Calendar data.

OM-010 remains open for physical Android phone/tablet and installed-Windows PWA acceptance, owner
acceptance, and stability observation. KR-013 remains open only for the separately authorized
historical-log assessment; no historical log or personal record was inspected. Weekly Avanza quotes,
specialist recency ordering, and OM-003 real-time voice remain outside this release.
