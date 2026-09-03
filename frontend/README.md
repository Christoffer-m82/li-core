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
