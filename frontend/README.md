# Li Mobile Web Interface — Phase 1

The frontend is a mobile-first installable web app served by a lightweight FastAPI
backend-for-frontend (BFF). The browser never receives the Li API token or a Cloud Run
identity token.

## Security architecture

1. The visitor signs in with Google OAuth. The BFF verifies the signed Google ID token,
   requires a verified email, and allowlists `Christoffer.Mellden@gmail.com`.
2. The browser receives only an HTTP-only, Secure, SameSite session cookie signed by the
   BFF. No credentials are stored in browser JavaScript or localStorage.
3. For each Li request the BFF obtains a short-lived Google identity token from its Cloud
   Run service account and sends it as `X-Serverless-Authorization`. It reads the Li API
   token from Secret Manager and sends it as `Authorization`.
4. The existing Li backend stays IAM-private. Grant the web runtime service account only
   `roles/run.invoker` on that backend. Do not grant `allUsers` backend access.

The web service itself must be reachable for the OAuth redirect. Its application content
and API remain protected by Google sign-in plus the server-side email allowlist. The only
anonymous endpoint is a data-free health check and the sign-in shell.

## Android and Windows installation

The web app manifest supplies explicit 192 px and 512 px PNG icons for Chromium installation on
Android and Windows, plus full-bleed maskable variants for supported Android launchers. The service
worker caches only explicitly listed static assets. Pages, sign-in routes, API responses, and URLs
with query strings remain network-only; opening Li and signing in require a connection. Older Li
shell caches are removed on worker activation, without touching unrelated application caches.
The SVG remains the browser favicon.
When Chromium exposes its install prompt, Settings shows an in-app **Install Li on this device**
control; otherwise it gives Android/Windows browser-menu guidance and detects standalone launch.

## Local validation

See [Appearance library](APPEARANCE.md) for built-in/custom themes, extension rules, and the Home
template analysis. Themes change presentation only and are saved per browser/device.
See [Specialist workspace](SPECIALIST_VIEW.md) for recorded exchanges, activity filters,
evidence details, data limits, and the agent-view reference analysis.
All 12 specialists have local portrait assets on Home, analytics cards, and their detail page.
Ada, Theo and Heimdall appear separately as system agents on Specialists and Backend, not Home. Their
read-only profiles use their registry names and roles, selected portraits, and the same large
portrait viewer. System-agent profiles describe responsibilities, not live activity or conversations;
they do not enter specialist analytics or acquire new permissions. Li has no portrait.
Names and roles remain visible; failed images fall back to initials. The approved portrait is
always named Elena, with no revision labels. See the
[portrait standard](../system/specialist-portrait-standard.md) and
[assignment record](../system/specialist-portrait-assignments.md) before adding another specialist.

On a specialist's detail page, press their portrait to open a large, theme-aware popup with their
name and role above the uncropped original. Close it with **Close** or Escape. **Open original image**
opens the full-resolution asset in a new tab for browser zoom. See the
[portrait viewer](SPECIALIST_VIEW.md#portrait-viewer) for interaction and accessibility details.

Portraits currently retain the original 1254 × 1254 PNGs (about 32 MB for all 15 selected portraits).
Images load lazily and their exact public static paths are cached on demand, not precached during
service-worker installation. Private API and authentication responses remain network-only.
Replacing a portrait requires a service-worker cache-version bump. Smaller optimized derivatives
remain a future bandwidth improvement; these source images have not been resized or recompressed.

## Owner profile photo

Settings contains the prepared private profile-photo experience. It shows CM by default and supports
local JPEG/PNG/WebP selection (5 MiB maximum), preview, explicit Save, Cancel and confirmed Remove.
The shared avatar renderer covers the account button, new Home messages and owner messages in Specialist
Workspace. A saved 512 × 512 JPEG is held only in browser memory through a revocable `blob:` URL; logout,
removal and stale-session invalidation release it. Photo responses use network-only `/api/profile/`
routes and are never service-worker cached, placed in preference storage, chat payloads or theme exports.

The BFF routes stay disabled with 503 while both private profile service settings are unset. Their prepared
client accepts only the exact internal operations, obtains a workload identity for the separate profile
audience, refuses redirects and bounds every response. Replacement validates the browser mutation guard
before incrementally parsing exactly one multipart file, then forwards only its bounded raw bytes, media type,
actual size and current opaque revision—never its filename. The UI therefore still honestly reports that
profile photos are unavailable in the current unconfigured state; it does not replace this with local-only
persistence. See the [profile-photo design](../system/OWNER_PROFILE_PHOTO_ARCHITECTURE.md) and
[local service foundations](../profile-service/README.md). A cryptographic service-side verifier, provider
storage, server composition, private hosting and physical-device checks remain pending.

The CSP permits `blob:` only for image rendering; scripts and connections remain same-origin. This is needed
for in-memory previews and saved-photo display and does not make profile URLs public.

From `frontend`, install the project with its `dev` extra, then run `ruff check app tests`,
`pytest`, and `python -m compileall app`. Start with
`uvicorn app.main:app --host 127.0.0.1 --port 8080`.

## Staging deployment

Build from the repository root with `frontend/Dockerfile`. Create a dedicated
`li-os-web-runtime` service account, grant it Secret Manager access only to the four web
secrets in the template, and grant it Cloud Run Invoker on `li-os` only. Deploy the web
service from `deployment/cloud-run/web-service.template.yaml`, substituting the project,
image, and final frontend URL without committing the rendered manifest.

Create a Google OAuth 2.0 **Web application** client and add this exact authorized redirect
URI: `https://FRONTEND_URL/auth/callback`. Store its ID and secret as
`LI_WEB_GOOGLE_CLIENT_ID` and `LI_WEB_GOOGLE_CLIENT_SECRET`. Generate a random 32-byte or
longer `LI_WEB_SESSION_SECRET`. Bind all secrets to pinned versions for staging.

After the first deployment supplies the final URL, set `LI_WEB_PUBLIC_ORIGIN` to that URL,
add its callback URI to the OAuth client, and deploy a new revision. Gmail sending remains
unavailable; this UI exposes no email mutation operation.
