# Native Gateway deployment gate

Do not run `provision-native-gateway.ps1` until migration 034 is reviewed and applied and both
platform-specific Google OAuth client IDs exist. Create a separate 256-bit signing key in Secret
Manager, plus a separate scoped `LI_OS_NATIVE_GATEWAY_API_TOKEN`. Pass exact numeric secret
versions; never use `latest`. The backend runtime must receive the same pinned scoped-token version.

The gateway runtime account receives only Cloud Run Invoker on the private backend and accessor on
the two named secrets. It receives no Cloud SQL role and no database secret. The backend must retain
no `allUsers` member. The gateway itself is reachable at network level so native apps can bootstrap,
but its protected application routes require an owner-allowlisted Google identity or a live bearer
session. CORS is intentionally absent because native clients do not rely on browser origins.

After deployment, set the backend's read-only `LI_OS_NATIVE_GATEWAY_STATUS=configured`, keeping auth
mode `google_oidc_bootstrap_bearer_refresh` and attestation status `not_configured`, then deploy a new
backend revision. This changes display metadata only; it does not activate any rhythm.
