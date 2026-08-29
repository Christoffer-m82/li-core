# Artifact retention enforcement

The staging retention worker is a private Cloud Run Job in `europe-west1`. It reuses
`gs://li-os-staging-private-artifacts`, runs the existing backend image with
`python -m app.retention_job`, and has no HTTP service or Li API token.

## Identities and least privilege

- `li-os-retention@li-os-staging.iam.gserviceaccount.com` runs only the retention job.
- `li-os-retention-scheduler@li-os-staging.iam.gserviceaccount.com` invokes only that job.
- PostgreSQL `li_retention_runtime` inherits only the NOLOGIN
  `li_artifact_retention` capability created by migration 022.
- The runtime service account gets a project custom role containing only
  `storage.objects.get` and `storage.objects.delete`, bound on the existing bucket.
- It gets `roles/secretmanager.secretAccessor` separately on only
  `LI_RETENTION_DB_HOST`, `LI_RETENTION_DB_USER`, and `LI_RETENTION_DB_PASSWORD`.
- The scheduler service account gets `roles/run.invoker` on only the retention job.

Do not grant either identity project-wide basic roles, do not grant the job the backend
database secrets, and do not put an application API token in Scheduler.

## Owner-controlled database step (do this before deployment)

Apply `memory/migrations/022_retention_worker_role.sql` as the database owner. Then set a
generated password for `li_retention_runtime` out of band and store its hostname, literal
username `li_retention_runtime`, and password in the three retention-specific Secret Manager
secrets. Never commit or paste the password.

Verify as the retention login that both approved functions execute, while a representative
application function and direct artifact-table access fail. Migration 022 is intentionally
not applied by repository automation.

## Google Cloud resources

Create the two service accounts and a project custom role named
`liArtifactRetentionObjectOperator` with only these permissions:

```text
storage.objects.get
storage.objects.delete
```

Bind that custom role to the retention service account on
`gs://li-os-staging-private-artifacts`. Bind Secret Manager accessor separately on each of the
three retention secrets. Deploy `retention-job.template.yaml` after replacing its explicit
placeholders with the existing backend image, bucket, and retention service-account email.
The parameterized `provision-retention.ps1` performs these steps without accepting or printing
secret values; run it only after the owner-controlled database step and secret creation.

Grant the scheduler service account `roles/run.invoker` on the deployed job, then create a
daily Scheduler job named `li-os-artifact-retention-daily` in `europe-west1`. Its target is:

```text
POST https://run.googleapis.com/v2/projects/li-os-staging/locations/europe-west1/jobs/li-os-artifact-retention:run
```

Use OAuth with the scheduler service account and scope
`https://www.googleapis.com/auth/cloud-platform`. A suggested schedule is `17 3 * * *` with
timezone `Europe/Berlin`. The unusual minute avoids a top-of-hour thundering herd.

The job may safely retry. Missing objects are treated as already deleted; the database row is
marked deleted only after object deletion succeeds. The selection function includes only
`retention_state='expiring'` rows whose expiry is due, so Keep-permanent (`kept`, no expiry)
and Delete-early (`deleted`) rows are excluded.

## Default compute service account

The project Editor grant on `340043378280-compute@developer.gserviceaccount.com` is not needed
by this design. Do not remove it based only on this repository. First inventory Compute Engine,
Cloud Build, Cloud Run, Functions, batch jobs, and instance templates for that identity, then
review recent IAM/service-account usage logs. If unused, replace Editor with narrowly scoped
roles or remove it in a separate, reversible IAM change.
