# Draft-exit warning web staging release: `c155bb1`

## Scope, authorization and rollout plan

The owner authorized a web-only staging deployment of
`c155bb1dbdb266c2744a7ff1c4c7f99127100b68`, using freshly verified existing coverage with
no additional charge. Backend, database, IAM, secrets, providers, scheduler and billing changes
are excluded. Codex is performing the rollout on 2026-10-04 against `li-os-web` in project
`li-os-staging`, region `europe-west1`.

**Validated web revision serves 100% of staging traffic.** The candidate
`li-os-web-release-c155bb1` was validated with zero normal traffic before promotion. A local Linux/amd64 build from a tracked-only
archive of the authorized commit was pushed to the existing Artifact Registry repository. The
immutable image is `europe-west1-docker.pkg.dev/li-os-staging/li-os/li-os-web@sha256:b73016a3aa0c1ddf312fc384459712b0a53aea187d42532201d3878da8deab93`.
Pinned build inputs are unchanged. No migration is included.

Cloud Run resolves the immutable OCI index above to its Linux/amd64 manifest
`sha256:d04b980d8d2b55843ec2101518ddd81c738271beaa47c80ece4a6a0425065aa5`; the registry index was
inspected and confirms that mapping. The candidate is Ready with that resolved digest.

The preceding Ready web revision `li-os-web-release-a9a6bf8` served 100% until promotion and is the
rollback target. The reviewed runtime diff adds only a best-effort browser warning for pending
drafts/uploads/messages and advances the public shell cache to v26. Rollback removes that warning,
but retains the enlarged-text correction and unchanged server security boundaries. Android Back
or process termination cannot be guaranteed to display a warning. No automatic send, persistence,
retry or navigation trap is introduced.

## Prerequisite evidence

- The authorized merge of [PR #115](https://github.com/Christoffer-m82/li-core/pull/115) has all
  12 post-merge checks completed successfully. Its previously recorded local frontend and offline
  browser checks remain local evidence, not device acceptance.
- A fresh read-only linked-account billing-console check on 2026-10-04 shows available Free Trial
  credit of EUR 261.59, expiring 2026-11-27, and the Free Trial status reports 54 days remaining.
  This covers the bounded existing Artifact Registry/Cloud Run rollout without a purchase or
  account upgrade. No billing controls were changed. This is not indefinite future cost coverage.
- Backend `li-os-calendar-v2` remains at 100% and private. Schema 0.42 is the last recorded database
  state, not a fresh database inspection. No schema-dependent runtime change is included.
- The worktree's pre-existing untracked backups and portrait ZIP remain untouched and must not
  enter the tracked-only build. Existing live acceptance ledgers are outside this batch.

## Candidate gates and rollback controls

Before promotion require immutable image identity, Ready candidate and rollback revisions, complete
non-image specification continuity, identical numeric secret references and IAM, unchanged backend,
public health and policy pages, anonymous denial at actual protected routes, matching static asset
bytes, and owner-operated masked authenticated readiness. Inspect only revision-scoped error counts,
not historical logs or raw payloads. Stop on any failed gate; retain the preceding normal traffic.

Follow the [deployment workflow](../DEPLOYMENT_WORKFLOW.md) and
[web staging guidance](../../frontend/README.md#staging-deployment).

## Candidate evidence obtained

- Candidate health, signed-out shell, About, Privacy and Terms each returned 200 with CSP, nosniff
  and no-store headers. Anonymous readiness, memory, proposal, portfolio, Calendar and privacy-settings
  requests at their actual protected routes returned 401.
- Candidate `/assets/app.js`, `/assets/exit-guard.js`, `/assets/workspace.js`, `/assets/app.css`,
  `/assets/specialists.css` and `/sw.js` bytes match the authorized tracked archive.
- The complete non-image template specification equals the preceding web specification, including
  runtime identity, resources, environment and all five numeric secret references. The only revision
  annotation difference is Cloud Run's operation identifier. Web IAM is unchanged, and backend
  service metadata/specification/traffic is unchanged. Backend IAM remains private.
- A candidate-only ERROR-severity query for the rollout window beginning 2026-10-04T06:44:33Z
  returned zero entries. No historical logs or sensitive payloads were inspected.
- The exact candidate's masked owner-operated readiness script passed parsing and offline
  `-CheckOnly` checks. The owner then privately supplied an existing web session and reported
  authenticated `/api/ready` returned 200. Neither the cookie nor response body was displayed or
  saved. This is owner-reported candidate evidence, not a second authenticated live test.

## Promotion and live evidence

Credit coverage was freshly rechecked immediately before promotion: the linked Free Trial remained
available at EUR 261.59 with expiry 2026-11-27. The immutable resolved image, complete non-image
specification, candidate/rollback readiness, preceding 100% traffic and web IAM were reverified.
Promotion began at 2026-10-04T06:59:24Z. The exact validated revision now serves 100% normal traffic.

- The web template and complete backend service object remained unchanged across promotion.
  Backend `li-os-calendar-v2` still serves 100%; web IAM is unchanged and backend IAM remains private.
- Live health, shell, About, Privacy and Terms returned 200 with CSP, nosniff and no-store headers.
  Anonymous readiness, memory, proposals, portfolio, Calendar and privacy-settings routes returned 401.
- All six candidate-checked static assets also match the authorized archive on the normal hostname.
- The initial post-promotion candidate-revision ERROR query returned zero entries. This bounded
  observation is not a stable-use period, a latency/error-rate study or universal absence-of-errors claim.

No rollback was needed. No provider call, personal-record read, migration or excluded configuration
change was performed. Physical draft-warning behavior remains unverified; browsers may suppress it.

The tracked-only build directory is retained at
`C:\Users\chris\AppData\Local\Temp\li-core-web-release-c155bb1-20261004`. No existing temporary
directory, live ledger, backup or other protected output was deleted or modified.

## Acceptance limitations

No provider call, personal-record access or device acceptance is authorized by this rollout.
Physical Samsung enlarged-text and Back behavior, installed-app, tablet, Windows, owner and stability
acceptance remain open. KR-011, KR-013 and OM-003 are not closed by a web release.
