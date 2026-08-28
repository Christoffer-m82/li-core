# Artifact retention enforcement

Create one private regional bucket in `europe-west1` with public-access prevention and
uniform bucket-level access enabled. Grant the backend runtime service account only
`roles/storage.objectUser` on that bucket. Do not grant the web runtime service account,
`allUsers`, or `allAuthenticatedUsers` any bucket role.

Deploy `retention-job.template.yaml` as a Cloud Run Job with the backend runtime identity and
the same database secret references as the backend. Create a daily Cloud Scheduler job that
calls the Cloud Run Jobs `:run` API with OAuth. Its service account needs only permission to
execute this one job; no application API token is stored in Scheduler. The cleanup operation
is bounded, idempotent, and records an audit tombstone only after object deletion succeeds.
