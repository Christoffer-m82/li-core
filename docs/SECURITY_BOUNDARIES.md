# Security boundaries

## Authority

[Li OS Security & Privacy Policy](../system/security-policy.md) is authoritative. This document is a
maintainer checklist derived from repository structure and implementation. It does not replace a
Heimdall review, threat model, or operator verification of live controls.

## Trust-boundary map

| Boundary | Allowed path | Credentials or authority | Must remain prohibited |
| --- | --- | --- | --- |
| Browser to web BFF | HTTPS session routes in `frontend/` | Google OAuth identity and BFF-managed session | Backend tokens, Cloud Run identity tokens, provider secrets, or object credentials in browser code |
| Web BFF to backend | Server-side request to IAM-private backend | Cloud Run identity token plus the narrow Li or owner token required by the route | Passing owner authority to ordinary Li routes; exposing either token to the browser |
| Native client to gateway | Google OIDC bootstrap followed by bounded bearer/refresh sessions | Owner-allowlisted identity, installation session, revocation state | Direct database access; trusting client-reported identity without verification |
| Gateway to backend | Dedicated internal native routes | Cloud Run identity token plus scoped native-gateway API token | Backend general API, Theo, owner, database, or provider credentials in the gateway |
| Backend to database | Function-oriented PostgreSQL API | Separate application, Theo, and owner-confirmation logins | Broad direct table access or authority sharing between roles |
| Backend to providers/models | Backend-owned adapters | Provider-specific OAuth/API credentials in secret manager | Raw credentials in prompts, specialist context, logs, responses, or Git |
| Backend to private objects | Governed artifact service | Backend runtime object access | Public bucket access, browser object credentials, UUID-as-authorization |
| Retention job to data/objects | Private Cloud Run Job | Dedicated retention DB capability and get/delete object role | Li API tokens, broad backend DB secrets, create/list bucket authority |
| Proactivity scheduler to backend | Private rhythm-run endpoint | Dedicated Cloud Run Invoker identity | Database, provider, Li API, or Secret Manager access |
| Repository to runtime | Reviewed deployment/migration process | Explicit operator action | Treating a merge as an automatic live mutation |

Implementation-specific detail lives in the [frontend README](../frontend/README.md),
[Native Gateway ADR](../system/NATIVE_GATEWAY_ARCHITECTURE.md),
[artifact-retention guide](../deployment/cloud-run/artifact-retention.md), and
[governed-proactivity guide](../deployment/cloud-run/governed-proactivity.md).

## Required review questions

For every change that crosses a boundary, answer:

1. What identity initiates the operation, and where is it authenticated?
2. What separate authorization check permits this exact operation?
3. Which credential is used, where is it stored, and can a less powerful one work?
4. What user, owner, conversation, installation, or request scope is enforced?
5. What untrusted content can enter the path, and where is it neutralized or validated?
6. What is logged, redacted, retained, and deletable?
7. How are retries made idempotent and stale approvals rejected?
8. What is the kill switch, revocation path, or rollback?
9. Which automated tests exercise denial as well as success?
10. Which live controls still require dated operator verification?

## Secret handling

- Store only placeholders and secret *references* in tracked files.
- Never print, paste, diff, or ask an agent to inspect live secret values.
- Use distinct secrets for distinct authorities; rotation must not silently broaden scope.
- Prefer pinned numeric secret versions for controlled rollouts. Where current templates use
  `latest`, treat that as a documented risk in [Known risks](KNOWN_RISKS.md), not as evidence of a
  pinned deployment.
- Scan staged content before commit, including generated manifests and captured command output.

## Data classification and minimization

Canonical memory, raw conversations, third-party data, health, financial, relationship, work-
confidential, location, embeddings, and object bytes have different retention and disclosure
requirements. Use [Memory Storage Policy](../memory/storage-policy.md) for storage rules and the
policy sections linked from [Security & Privacy Policy](../system/security-policy.md) for the
authoritative classifications. Synthetic or anonymized data is the default for development and
staging validation.

## Stop conditions

Stop and request explicit authorization when a task would apply a migration, reveal or rotate a
secret, modify Supabase or cloud state, change IAM, activate a scheduler/rhythm, send external data,
or perform an irreversible deletion. Stop and escalate a design conflict when a change requires
combining authorities that the current architecture keeps separate.
