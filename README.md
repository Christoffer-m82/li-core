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
