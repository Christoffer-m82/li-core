# ADR-008: Authenticated Native Gateway and coarse on-device Place flow

**Status:** Implemented for review; not deployed. Schema 0.34 is required. The iOS and Android
modules are proof-of-concept libraries, not shipped production apps.

## Decision and trust boundaries

```text
iOS / Android app
  | Google OIDC bootstrap, then short-lived bearer token
  | country + optional locality only (never coordinates)
  v
Public network boundary: Li Native Gateway
  | verifies owner allowlist, installation binding, expiry and revocation
  | Cloud Run service identity + private Li API credential
  v
IAM-private Li backend
  | sole database/business-logic boundary
  | existing Place freshness, manual precedence, replay, 30/hour and policy checks
  v
Private database / governed providers
```

The gateway is a separate Cloud Run service. It is public only at the network layer because native
clients cannot safely embed a Google Cloud service identity. Application endpoints are owner-only.
The gateway service account may invoke the private backend and read two pinned secrets; it has no
database access. A separate scoped native-gateway API credential reaches only the backend's
`/internal/native/*` routes and cannot act as Li Web, Theo, or Owner. Native users and installations
receive neither Cloud Run IAM permission nor the private backend URL/token. The backend must never
gain an `allUsers` binding.

## Authentication and token lifecycle

1. A host app performs Google Sign-In with its platform OAuth client and sends the Google ID token,
   platform, and optional typed attestation assertion to `/v1/auth/bootstrap`.
2. The gateway verifies signature/issuer/time through Google, checks the audience against the exact
   iOS/Android client-ID allowlist, requires verified email, and applies the server owner allowlist.
3. The private backend creates a schema-0.33 opaque installation UUID and a schema-0.34 session.
4. The gateway returns a 10-minute signed access token and a high-entropy refresh token. The access
   token contains only issuer/audience, allowlisted owner subject, session UUID, installation UUID,
   issued time and expiry. The app stores secrets in Keychain or Keystore-backed encrypted storage.
5. Only keyed SHA-256 refresh-token hashes persist. Refresh is single-use rotation under a row lock;
   the immediately consumed hash is retained only for replay detection. Its reuse atomically revokes
   that session and installation. Older, expired, revoked, wrong-owner, or revoked-installation
   refresh attempts fail closed.
6. Every protected call validates the access signature/expiry and asks the backend to validate the
   session/installation binding and revocation. Logout revokes one session; device removal revokes
   the session and installation; revoke-all invalidates all owner sessions and installations.

Bearer authorization is used, so CSRF is not applicable. Browser cookies are neither accepted nor
issued. The gateway has no CORS middleware; a future browser consumer would require an explicitly
reviewed origin list and separate CSRF/session design. Session requests are limited to 120/minute per
owner-bound session/installation; Place retains its authoritative 30/hour installation limit.

## Coarse Place contract and device flows

Both modules request OS permission explicitly and preserve manual entry as the fallback. The version
1.0 payload contains only installation/update UUIDs, ISO country, optional locality, `device_coarse`,
observation time, granted permission assertion, and an optional minimal overnight/transit event.
Unknown fields are forbidden at gateway and backend boundaries.

```text
explicit permission -> one low/balanced-accuracy observation -> local reverse geocoder
 -> country / optional locality -> release transient coordinate -> typed gateway payload
denied / restricted / no geocode result -> no update -> manual Place remains available
```

iOS uses `requestWhenInUseAuthorization`, three-kilometre desired accuracy and a one-shot request.
Significant-change monitoring is exposed only behind a separate opt-in and is suitable for sparse
country-change/overnight hints, not tracking. Android requests `ACCESS_COARSE_LOCATION` only and uses
a balanced-power one-shot fused location request. Fine and background permissions are absent.

Neither module stores or serializes a location object, creates GPS trails, or continuously polls.
The optional overnight classifier only detects a local calendar-day boundary. Background updates,
if ever needed, are a later explicit opt-in milestone with separate battery/privacy review.

## Attestation, chat and governance

The bootstrap contract has typed Apple App Attest, DeviceCheck and Google Play Integrity extension
points. Verification is truthfully `not_configured`; assertions are rejected with 501 rather than
accepted without verification. Adding attestation requires provider credentials, nonce/replay state,
and a separate threat-model review.

`/v1/chat` accepts text or an already-created voice transcript and forwards existing `/li/chat`
semantics. No raw audio endpoint exists. ActionIntent proposal/decision boundaries, Freshness &
Evidence, Provider Coverage, jurisdiction rules and approval policy remain backend-owned. Native
voice never auto-approves and always-listening/background voice is out of scope.

## Privacy and operational guarantees

- No coordinate column exists in schema 0.34 and coordinates are forbidden by strict request models.
- Access/refresh tokens are not logged. Access logging is disabled for the gateway container; any
  future structured logging must redact authorization, identity tokens, message bodies and audio.
- Responses are allowlisted/sanitized and never surface private backend URL, service credentials,
  secret names/values, database identifiers, owner database IDs or internal errors.
- Place remains relevant-only downstream and manual correction retains 24-hour precedence.
- Gmail sending remains unavailable. This milestone creates no scheduler and activates no rhythm.
- Artifact-retention cleanup is unrelated and must not run for secret repinning or this deployment.

## Deployment prerequisites and acceptance gate

Migration `034_authenticated_native_gateway.sql` is unapplied and may be hardened until owner review;
after approval it must be applied exactly once
before backend or gateway deployment. Then create platform OAuth client IDs, a pinned Secret Manager
signing key, build the gateway image, provision its least-privilege service account, and deploy with
the supplied manifest/script. Verify backend IAM has no public member and gateway identity alone can
invoke it. Deploy native proofs only after app entitlement/permission copy and Keychain/Keystore
integration are reviewed. Platform attestation may remain explicitly not configured for this proof.
