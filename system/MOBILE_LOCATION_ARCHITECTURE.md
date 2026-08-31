# ADR-007: Native mobile location provider boundary

**Status:** Proposed for schema 0.33 review  
**Date:** 2026-08-31  
**Decider:** Owner

## Context

Li Web supports an explicitly selected country and optional town/city. Future iOS and Android apps need a stable way to provide coarse current-place observations without sending coordinates, creating a location trail, weakening the private Cloud Run boundary, or overriding a recent manual correction.

## Decision

Version `1.0` of the mobile contract accepts only an opaque server-issued installation UUID, an update UUID, ISO country code, optional device-resolved town/city, `device_coarse` source, explicit OS permission assertion, observation time, and an optional minimal overnight/transit event. Unknown fields fail validation, so `lat`, `lng`, `latitude`, `longitude`, GPS objects, hardware identifiers, and advertising identifiers are rejected.

The future flow is:

```text
iOS/Android OS permission
  -> on-device geocoding and coarse country resolution
  -> authenticated native BFF/API gateway (future)
  -> private Li backend mobile Place endpoint
  -> existing Place service and visit semantics
  -> Li relevant-context filter
```

The native app should geocode on-device whenever practical. If it cannot resolve a country locally, it sends no location update and asks the user to select a country manually. A later gateway may use an explicitly reviewed coarse-resolution service, but precise coordinates must be discarded before the versioned Place contract and must never reach Li's backend, database, logs, specialist prompts, or analytics.

The backend remains IAM-private. Native clients must not call Cloud Run directly or embed backend credentials. A future native gateway will authenticate the owner/session, bind that session to a server-issued opaque installation ID, authenticate to the private backend, and forward the typed payload. The current registration route is a protected extension point and is not evidence that automatic native updates have shipped.

## Trust, precedence, and lifecycle

- Only `granted` permission updates are accepted. `unknown`, `not_requested`, `denied`, and `restricted` are status states and cannot mutate current place.
- Observations older than 24 hours or more than five minutes in the future are rejected.
- Update UUIDs provide idempotency; accepted observations are limited to 30 per installation per hour.
- A manual Web/mobile correction holds precedence for 24 hours. A device update must be both fresh and observed after that hold; stale queued observations cannot overwrite it.
- Installation IDs are random server-issued UUIDs. Revocation immediately rejects later updates; re-enrollment gets a new rotatable ID.
- Overnight/transit input is an event, not tracking. Corrections can change the classification while existing rolling-12-month, overlap, suppression, and pin rules remain authoritative.

## Privacy and context consequences

Persistence contains country, optional town/city, first/last event times, classification, source, permission state/timestamp, opaque installation/update/event IDs, platform, and acceptance/revocation timestamps. It contains no coordinate or raw location field and no hardware, advertising, IMEI, or serial identifier.

Only the existing relevance filter can add current place to Li context: country for materially location-relevant requests and town/city only for town-level relevance. Visit history never enters specialist context. Device origin does not relax Freshness & Evidence, Provider Coverage, legal jurisdiction, tax, health, or finance verification.

## Options considered

1. Send coordinates to the backend and geocode centrally — rejected because it expands sensitive collection and breach impact.
2. Reuse only schema 0.32 — rejected because replay state, revocation, provider status, and manual precedence require durable server state.
3. Store a hardware-derived device fingerprint — rejected because correlation does not justify durable device identity.

## Deployment gate

Migration `033_native_mobile_location_boundary.sql` is immutable and must be reviewed and applied before backend/web deployment. Automatic native collection remains disabled until a separately reviewed native gateway, client authentication flow, OS permission UX, and platform apps exist.
