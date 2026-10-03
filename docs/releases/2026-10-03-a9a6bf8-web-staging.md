# Enlarged-text web staging release: `a9a6bf8`

## Status and authorization

**Validated web revision now serves 100% of staging traffic.** The owner authorized only
a web staging deployment of `a9a6bf8f21b996123194e8e3ba1bb6471c50e05c`, against verified existing
coverage with no additional charge. Backend, database, IAM, secrets, providers, scheduler and
billing changes are excluded.

The candidate `li-os-web-release-a9a6bf8` was created on 2026-10-03. The preceding
`li-os-web-release-131034f` remained at 100% until all candidate gates passed. Backend `li-os-calendar-v2`
still serves 100%; schema 0.42 is the last recorded database state, not a newly performed database
verification. See the [Calendar configuration release](2026-09-09-calendar-v2-staging.md).

## Review, build and coverage

- [PR #113](https://github.com/Christoffer-m82/li-core/pull/113) merged; all 12 PR and 12
  post-merge checks passed. The complete frontend diff from the deployed `131034f` commit was
  reviewed: only the enlarged-text layout correction, service-worker cache bump and local tests
  and documentation changed. Server code, dependencies and authority boundaries did not change.
- The owner-reported Samsung A55 5G 200% text failure and local simulated checks remain in the
  [device evidence record](../PERSONAL_V1_DEVICE_ACCEPTANCE.md#samsung-galaxy-a55-5g-browser-observations---2026-10-03).
  Local checks do not establish physical-phone acceptance.
- A fresh read-only billing-console check showed available Free Trial credit of EUR 261.59,
  expiring 2026-11-27. Existing coverage was checked before this bounded Artifact Registry/Cloud
  Run rollout; no billing control, purchase, upgrade or replenishment was changed. This is not
  a claim that cloud services are inherently free or that future usage is covered indefinitely.
- The image was built locally from a tracked-only archive of the exact authorized commit.
  Protected backups and the untracked specialist-thumbnail ZIP were excluded. The pinned build
  inputs were unchanged; the Linux/amd64 image digest is
  `sha256:9c898d3c0fe22a34c26fc508cec7be77529e85ffb8d1e8d78d52930adcc50546`.

## Candidate and promotion evidence

- The complete non-image revision specification equals the preceding web revision, including
  runtime identity, resources, environment and all five numeric secret references. The only
  annotation difference is Cloud Run's operation identifier. Web IAM's etag is unchanged; backend
  IAM remains private.
- Candidate health, signed-out shell, About, Privacy and Terms returned 200 with CSP, nosniff and
  no-store headers. Anonymous readiness, memory, proposal, portfolio, Calendar and privacy-settings
  requests returned 401 at their actual protected routes. Nonexistent paths returned 404 and are
  not counted as authority-denial evidence.
- Candidate `/assets/app.js`, `/assets/app.css`, `/assets/specialists.css` and `/sw.js` bytes match
  the authorized archive. An initial hash check used the incorrect `/static/sw.js` path and failed;
  the corrected `/sw.js` check passed. This was a test-path error, not an image mismatch.
- A revision-scoped ERROR-severity query found no entries during the candidate check window. No
  historical logs or raw provider output were inspected.
- The owner operated the masked local validation and reported that the exact candidate's
  authenticated `/api/ready` returned 200. Its only authenticated request was readiness; neither
  the cookie nor response body was displayed or saved. The unchanged OAuth configuration redirects
  to the normal staging hostname, so an existing owner-entered web session was used without changing
  OAuth or accessing Secret Manager values. This is owner-reported authenticated candidate evidence,
  not a second independently performed authenticated test after promotion.
- Immediately before promotion, the immutable digest, complete non-image specification, candidate
  and rollback readiness, and preceding revision's 100% traffic were reverified. The exact validated
  revision was promoted on 2026-10-03 at approximately 20:44 UTC.
- Post-promotion checks verified 100% traffic on `li-os-web-release-a9a6bf8`; health, shell and the
  three public documents returned 200 with security headers. Anonymous readiness, portfolio,
  Calendar and proposal routes remained 401. The four changed static assets again matched the
  authorized archive. Web IAM's etag and backend `li-os-calendar-v2` at 100% were unchanged.
- The initial revision-scoped post-promotion ERROR query returned no entries. This bounded rollout
  observation is not an owner stable-use period or universal absence-of-errors claim.

## Rollback and limitations

The Ready preceding revision `li-os-web-release-131034f` is the web rollback target. The reviewed
diff contains no web server/security correction that rollback would remove, but rollback would
restore the known enlarged-text layout failure. It leaves backend, schema, personal data and OAuth
configuration unchanged. Stop promotion on any failed readiness, configuration, privacy or image
check, per the [deployment workflow](../DEPLOYMENT_WORKFLOW.md).

No provider call, Calendar read, personal-record access, migration or adjacent service change was
performed. Samsung 200% retesting, installed-app, tablet, Windows, owner and stability
acceptance remain open. Android Back behavior is a separate unresolved finding. KR-011, KR-013 and
OM-003 remain open; this web release does not close their gates.
