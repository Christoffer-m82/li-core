# ADR: private cross-device owner profile photo

**Status:** Proposed technical design; hosted activation blocked by the no-spending requirement.
**Date:** 2026-09-04
**Decider:** Christoffer, after implementation/security review.
**Release state:** Local domain foundation only; no running service, upload UI or deployment.

## Cost gate

The owner's later [no-spending requirement](../AGENTS.md#no-spending-requirement) overrides earlier
approval to pursue cross-device photos. This document is not spending authorization. The proposed
cloud service/storage may incur charges, and zero cost has not been established. Do not provision,
invoke, deploy or activate it, or trigger potentially billable hosted CI to test it. Existing cloud
resources and a provider free tier do not establish zero cost.

Local implementation and synthetic tests may proceed without new paid dependencies or external calls.
The [domain foundation](../profile-service/README.md) tests state transitions only. A verified no-cost
hosting/storage option or an explicit owner change to the spending rule is required before activation,
in addition to the exact external-action approvals. Browser-only persistence would change the agreed
cross-device/privacy behavior and is not silently substituted. Existing paid services are not cancelled
or reconfigured by this proposal.

## Context and verified repository facts

The owner wants Settings to offer an optional personal photo, replacement and removal, with CM
shown when no photo is set. Specialist Workspace should use that same photo beside owner messages.
Android phone, Android tablet and Windows laptop should see one private profile, not separate uploads.
This is a presentation preference, not a photograph submitted to Li for analysis or personal memory.

- The [browser security architecture](../frontend/README.md#security-architecture) uses an allowlisted
  Google sign-in and server-side BFF; credentials do not enter browser storage.
- [Artifact storage](../README.md#phase-2-private-data-retention) is governed through the backend and
  PostgreSQL. Its existing bucket access belongs to the backend, not the web service or browser.
  Reusing that artifact API would not provide the desired separation from model-facing authorities.
- [Workspace](../frontend/SPECIALIST_VIEW.md#shared-conversation) currently renders owner initials;
  profile-photo setup is explicitly unimplemented.
- [The service worker](../frontend/static/sw.js) caches only enumerated public static assets.
  Owner photos must never join its specialist-portrait list.

Follow the [least-privilege policy](security-policy.md#7-least-privilege),
[document-storage policy](../memory/storage-policy.md#13-document-storage) and
[deletion policy](../memory/storage-policy.md#52-memory-deletion). This proposal changes none of those
policies or the existing artifact permissions. Repository inspection does not verify cloud state.

## Proposed decision

Use a dedicated private owner-profile service and dedicated private object storage. The browser calls
same-origin authenticated BFF routes; only the BFF service identity may invoke the profile service.
The profile service alone reads and writes its photo storage. It has no access to conversations,
canonical memory, artifacts, AI providers or the Li backend. Li, specialists, Theo, the native gateway
and the artifact-retention worker receive no profile-service or photo-storage permission.

For the current single-owner product, the profile service binds requests to one configured opaque
profile identifier. Derive the authenticated owner from the verified BFF session, never from a URL,
upload field, model request, arbitrary email header or client-supplied object name. Before any future
multi-owner support, replace this singleton mapping with a reviewed identity-binding contract.

The service independently verifies its intended audience and the allowlisted BFF workload identity,
in addition to private service invocation controls. The existing Li API token is not accepted as a
profile credential. Do not reuse owner-confirmation, Theo or native credentials. Reject the backend
runtime identity even if it knows a profile identifier.

This is an intentional new, narrow service boundary, not permission to grant the BFF access to the
artifact bucket. Its deployment and IAM review remain separately authorized external work.

## Alternatives considered

| Option | Benefit | Why not selected |
| --- | --- | --- |
| Browser-only photo | No new service; no upload | Does not satisfy one profile across devices; browser storage clearing loses it |
| Existing artifact API and bucket | Reuses current persistence | Couples a private presentation photo to model-facing file authority and retention |
| Give BFF direct access to isolated photo storage | Fewer services | Expands the web runtime's direct data permissions and couples image decoding to sign-in/chat serving |
| Dedicated private profile service | Isolated identity, decoder and storage; no memory migration | Selected proposal, with extra deployment, dependency and operational review cost |
| Use Google's account photo URL | Little UI work | No owner-controlled upload/removal lifecycle; remote image requests and identity leakage |

## User experience

Settings gains a Profile photo section with a large circular preview, Add/Change photo, explicit Save,
Cancel and Remove photo. Keep CM visible during loading, missing-image and failure states. Replacement
must not hide the saved photo until Save succeeds. Removal requires an explicit confirmation and
returns all visible owner avatars to CM only after server confirmation. Failed removal is not success.

Use a shared avatar renderer in the account button and owner messages, including specialist Workspace.
Names remain readable text; decorative images have empty alt text. Li keeps her placeholder and
specialists retain their approved portraits and message colours. Do not infer identity from a photo,
change the Google display name, modify past messages, or send a photo to a model.

Show a square crop preview before Save. Upload only on Save. Keep an original selected file only in
temporary browser memory; Cancel, successful Save, logout and navigation away release it. The server
revalidates the bytes independently. No automatic Google-photo import, face recognition or camera access.

## Proposed browser API contract

These routes do not exist yet. Every route requires the current allowlisted owner session.

| Route | Behavior |
| --- | --- |
| `GET /api/profile/photo` | Metadata: `state` is `available` or `empty`, opaque `revision`; no storage paths or photo bytes |
| `GET /api/profile/photo/image` | Current normalized JPEG, or 404 for empty; no public/signed storage URL |
| `PUT /api/profile/photo` | Bounded multipart upload; expected revision required; returns committed metadata |
| `DELETE /api/profile/photo` | Explicit owner removal; expected revision required; commits empty state |

Mutations require a same-origin Origin header checked against configured public origin, an explicit
custom request header and the current revision. Do not rely on SameSite cookies alone. Deny absent or
foreign origins; never enable credentialed wildcard CORS. The internal service accepts only its
authenticated BFF caller, not browser cookies or model-provided headers.

Return 401 for an expired browser session, 403 for rejected origin/authority, 409 for stale revisions,
413 for oversize input, 415 for unsupported type, 422 for invalid image and 503 for unavailable storage
or disabled configuration. Metadata read failures must not become `empty`. Use generic errors without
filenames, decoder traces, bucket names, tokens or image bytes. Never fall back to public/static files.

## Image processing limits

Proposed initial limits: one JPEG, PNG or WebP file; at most 5 MiB encoded; at most 16 million decoded
pixels and 8192 pixels on either axis. Reject SVG, GIF, animation/multiple frames, mismatched formats,
truncated content and decompression bombs. Validate signatures and actual decoded format, not filename
or browser MIME alone. Bound streamed request bytes even when Content-Length is absent or invalid.

Correct EXIF orientation, apply the explicitly previewed crop, resize to a 512-by-512 avatar, convert
to RGB and re-encode as JPEG no larger than 512 KiB. Strip EXIF/GPS, comments, thumbnails and embedded
profiles from the output. Persist no original, original filename or location metadata. The UI must
explain that this is a profile-sized copy, not an original-photo archive.

Use a pinned, reviewed decoder in a resource-limited worker: bounded concurrency, input/output size,
CPU time and memory. Cancelling a request must not leave unbounded decoding work. Dependency/security
review and resource-exhaustion tests are implementation gates, not established capabilities.

## Storage, concurrency and deletion

Store one current object at a server-generated path under the opaque profile ID in a dedicated
private bucket. Object bytes hold the normalized photo; bounded metadata holds a random revision,
state, normalized format and update time. An empty state uses a zero-photo-byte tombstone at the same
path. No PostgreSQL schema change is proposed for this single-owner presentation preference.

Use generation-conditioned atomic replacement of bytes and metadata. First creation requires the
object to be absent. Each mutation first verifies the expected opaque revision, then writes only if
the observed storage generation is unchanged. Tombstones retain a revision so delayed saves cannot
silently undo a newer removal. Use generation-pinned reads so a replaced object cannot mix old metadata
with new bytes. Do not expose provider generations, object paths or bucket names to the browser.

For a profile never saved before, metadata returns `empty` with the reserved revision `absent`.
Only a create-if-absent write can consume it. Once an object or tombstone exists, mutations require its
random revision; `absent` cannot overwrite it. Repeated removal of an already-empty profile is a
verified no-op only when its expected revision is still current.

On an uncertain write response, fetch metadata to reconcile; do not blindly retry against a newer
revision. An error before commit preserves the previous photo. A concurrent mismatch returns 409
and asks the owner to reload before saving. Process-local locks are not sufficient across instances.

Removal atomically makes the active profile empty and blocks subsequent image reads. Noncurrent object
versions, soft-delete retention and backups may retain encrypted historical bytes. Configure and verify
their actual retention before activation; explain the window to the owner. Never promise immediate
physical erasure from backups. Photo removal must not touch unrelated files or memory. A restored
backup must not silently resurrect a removed photo without owner approval and tombstone reconciliation.

## Browser privacy and synchronization

All photo metadata/image/mutation responses use `Cache-Control: private, no-store` and `nosniff`.
Keep `/api/profile/` network-only in the service worker. No photo bytes or metadata in localStorage,
IndexedDB, cached HTML, theme exports, chat payloads, analytics, logs or Git. Never log multipart bodies.

Fetch through same-origin session-bound routes. Display bytes only in memory and release references
on logout/session expiry, navigation invalidation and removal; ignore late responses from an earlier
session or revision. Use a scoped `blob:` image policy only if object URLs are chosen, never broaden
script/connect sources. Include this CSP change in implementation review rather than assuming it exists.

Other devices refresh on sign-in, window focus and opening Settings/Workspace, with bounded metadata
refresh while visible. No background personal-data polling while signed out. A photo already rendered
on another device cannot be remotely erased instantaneously; define and test a refresh interval before
release. Offline mode uses CM, not a persisted private image. No real-time push service is proposed.

## Acceptance and rollout gates

1. Implement domain/storage interfaces with synthetic in-memory test doubles and the shared UI avatar.
2. Test upload/replace/remove/reload, CM fallback, crop preview, cancellation and sync refresh.
3. Test denial for anonymous/wrong-owner/wrong-workload identities, foreign origins and stale revisions.
4. Test oversized/chunked/malformed/animated/bomb images, metadata stripping and bounded decoding.
5. Test generation races, uncertain-write reconciliation, failed storage, logout and late image responses.
6. Test that agents/artifact APIs cannot discover photos; service worker and theme exports retain none.
7. Review the complete diff, dependency pins, authority map and operating instructions before commit/release.
8. Separately authorize the exact private service, bucket, IAM, retention configuration and deployment.
   Keep the feature disabled with an honest explanation until prerequisites are verified.
9. Run staged authorization/retention/recovery checks, then physical Android phone/tablet and Windows
   upload, replace, remove, re-login and cross-device acceptance. Record evidence before declaring complete.

Rollback disables new photo operations and shows CM without deleting stored data or reverting security
controls. Never turn on a public-storage fallback. Review this decision before adding native-client
access, multi-owner support, image analysis, original-photo retention or additional profile fields.
