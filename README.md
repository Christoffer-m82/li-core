# li-core
Core architecture, identity, orchestration rules and configuration for Li OS — my personal AI operating system.

## Mobile web interface

Phase 1 of the responsive, installable Li web interface lives in `frontend/`. It uses a
server-side BFF so Cloud Run IAM credentials and the Li API token are never exposed to the
browser. See `frontend/README.md` for the security model, local validation, and staging
deployment instructions.

## Secure remote deployment

The recommended production target is **Google Cloud Run** in `europe-west1` (Belgium),
using the included OCI container. Cloud Run provides managed HTTPS, immutable revisions,
traffic rollback, scale-to-zero, and integration with Google Secret Manager. The container
is platform-neutral and can be moved to another OCI host later.

Production has two authentication layers:

1. Cloud Run IAM controls who may invoke the service. Do not grant `allUsers` the
   Cloud Run Invoker role. A client obtains a short-lived Google identity token.
2. Li still requires one of its separate, rotating bearer tokens (`API`, `THEO`, or
   `OWNER`) according to the endpoint. Keep those authority boundaries separate.

The public `/health` route contains no integration or user data and exists only for the
platform probes. `/ready`, `/health/database`, and all product routes require Li API
authentication. Production disables interactive API docs, rejects wildcard CORS, requires
TLS for PostgreSQL, requires 32-character-or-longer service tokens, applies a per-instance
request limit, emits JSON logs, and redacts credential-like names. Optional providers
degrade to unavailable when absent; partially configured OAuth providers fail startup.

### One-time Google Cloud setup

Use a dedicated non-production Google Cloud project first. Enable Cloud Run, Cloud Build,
Artifact Registry, and Secret Manager. Create:

- a runtime service account with only `Secret Manager Secret Accessor` on the listed
  secrets;
- an Artifact Registry Docker repository in `europe-west1`;
- a Cloud Run service from `backend/Dockerfile`, with unauthenticated access disabled;
- one Secret Manager secret per item below, with automatic replication or an EU user-
  managed replication policy.

Required Secret Manager entries (values must be entered manually, never copied by a
script from `.env`):

- `LI_OS_API_TOKEN`, `LI_OS_THEO_API_TOKEN`, `LI_OS_OWNER_API_TOKEN`
- `LI_OS_ANTHROPIC_API_KEY`
- `LI_OS_DB_HOST`, `LI_OS_DB_USER`, `LI_OS_DB_PASSWORD`
- `LI_OS_THEO_DB_USER`, `LI_OS_THEO_DB_PASSWORD`
- `LI_OS_OWNER_DB_USER`, `LI_OS_OWNER_DB_PASSWORD`
- `LI_OS_BRAVE_SEARCH_API_KEY` for live research
- `LI_OS_GOOGLE_CALENDAR_CLIENT_ID`, `LI_OS_GOOGLE_CALENDAR_CLIENT_SECRET`,
  `LI_OS_GOOGLE_CALENDAR_REFRESH_TOKEN` for Calendar
- `LI_OS_GOOGLE_GMAIL_CLIENT_ID`, `LI_OS_GOOGLE_GMAIL_CLIENT_SECRET`,
  `LI_OS_GOOGLE_GMAIL_REFRESH_TOKEN` for Gmail Phase A

Set non-secret configuration directly on the service: `LI_OS_ENVIRONMENT=production`,
`LI_OS_ALLOWED_ORIGINS` to the exact trusted web origin (or leave it empty for non-browser
clients), `LI_OS_CLAUDE_MODEL` (currently `claude-sonnet-5`), the model timeouts, database
port/name/TLS mode, Google calendar ID, and
Gmail user ID. Use the placeholders in `deployment/cloud-run/service.template.yaml` as a
reviewable baseline; do not commit a rendered manifest containing project identifiers or
secret values.

Build from the repository root and deploy the resulting immutable image digest. Configure
each secret environment variable as a Secret Manager reference to a pinned secret version,
then grant only the intended Google account or client service account the Cloud Run Invoker
role. Set minimum instances to zero initially and maximum instances to two. The in-memory
rate limit is a basic abuse control, not a distributed quota; Cloud Armor or an API gateway
is the later upgrade if the service gains multiple users.

### Verification

Use a staging database or synthetic account with no personal data. Obtain a Cloud Run
identity token and send it in `X-Serverless-Authorization: Bearer`; send Li's token in the
normal application `Authorization: Bearer` header. Cloud Run checks and removes the former
before forwarding the request, leaving Li's own authorization header intact. Verify, in order:

1. `/health` returns `ok` without exposing provider details.
2. `/ready` and `/health/database` succeed with Li authentication.
3. A normal `/li/chat` turn succeeds.
4. A harmless current-events query uses live Brave research.
5. Calendar performs a read-only lookup.
6. Gmail performs search/read only. Do not create a draft or send anything during the
   staging smoke test.

If a client cannot set `X-Serverless-Authorization`, place an HTTPS gateway/IAP or trusted
proxy in front of Cloud Run. Keep the service IAM-private in every case.

### Rotation and rollback

Rotate one Li token at a time: add a new Secret Manager version, deploy a new revision
referencing that version, update the client, verify it, and disable the old version. OAuth
and provider credentials follow the same new-version/new-revision procedure.

To roll back, shift 100% of Cloud Run traffic to the last known-good revision. Because
deployments do not run database migrations, application rollback is independent of the
database. After rollback, check `/health`, authenticated `/ready`, and a read-only provider
operation. Keep the failed revision at zero traffic for diagnosis; delete it only after the
incident is resolved.

The longer-term authentication upgrade is per-device OIDC/WebAuthn with short-lived access
tokens, refresh-token revocation, device inventory, and endpoint scopes. That replaces the
shared Li token while retaining separate Theo and owner authority boundaries.

## Google Calendar provider setup

The backend keeps Calendar unavailable unless all three OAuth secrets are configured. To enable it:

1. In Google Cloud, enable the Google Calendar API and configure the OAuth consent screen.
2. Create an OAuth client for the environment running Li.
3. Authorize the account with only `https://www.googleapis.com/auth/calendar.events`, requesting offline access and consent so Google returns a refresh token.
4. Put the client ID, client secret, and refresh token in the deployment secret manager as `LI_OS_GOOGLE_CALENDAR_CLIENT_ID`, `LI_OS_GOOGLE_CALENDAR_CLIENT_SECRET`, and `LI_OS_GOOGLE_CALENDAR_REFRESH_TOKEN`. Do not commit them or paste them into chat.
5. Optionally set `LI_OS_GOOGLE_CALENDAR_ID` (default: `primary`) and `LI_OS_GOOGLE_CALENDAR_TIMEOUT_SECONDS` (default: `10`). Restart the backend.
6. With an authorized test calendar, create a clearly labeled future event through Li's approved action endpoint, search for it, delete it directly in Google Calendar, and confirm it no longer appears. The product API intentionally does not expose deletion.

Calendar reads do not require approval. Creates still require `approved=true` at Li's executor boundary. The provider is held only in application state and is never available to specialists.

## Gmail provider setup

Li's Gmail boundary supports search, individual message retrieval, thread retrieval,
and draft creation. It intentionally has no send action or provider method.

1. In the same or a separate Google Cloud project, enable the Gmail API and configure
   the OAuth consent screen.
2. Create an OAuth client for the environment running Li.
3. Add your Google account as a test user while the consent screen is in testing.
   In OAuth Playground, open Settings, enable **Use your own OAuth credentials**, and
   enter that client's ID and secret. Select exactly
   `https://www.googleapis.com/auth/gmail.readonly` and
   `https://www.googleapis.com/auth/gmail.compose`, then authorize access while signed
   into the intended mailbox. Exchange the authorization code for tokens and copy the
   refresh token once. Google requires `gmail.readonly`
   for bodies/search and `gmail.compose` for creating drafts. Although the compose
   scope can also send, this backend exposes no sending operation.
4. Store the resulting client ID, client secret, and refresh token only in the
   deployment secret manager as
   `LI_OS_GOOGLE_GMAIL_CLIENT_ID`, `LI_OS_GOOGLE_GMAIL_CLIENT_SECRET`, and
   `LI_OS_GOOGLE_GMAIL_REFRESH_TOKEN`. Optionally set `LI_OS_GOOGLE_GMAIL_USER_ID`
   (default `me`) and `LI_OS_GOOGLE_GMAIL_TIMEOUT_SECONDS` (default `10`). Restart Li.
5. Verify with a harmless message search/read, then create a clearly labeled draft
   through `/li/actions/email` with `approved=true`. Delete that draft directly in
   Gmail after verification; this phase deliberately exposes no delete or send action.

Reads do not require approval. Draft creation requires explicit approval at the
Li-owned execution boundary and returns a confirmation that the draft was not sent.
Email bodies are treated as untrusted data and instruction-like content is neutralized.
