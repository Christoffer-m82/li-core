# li-core
Core architecture, identity, orchestration rules and configuration for Li OS — my personal AI operating system.

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
