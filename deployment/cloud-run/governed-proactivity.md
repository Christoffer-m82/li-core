# Governed proactivity scheduler

Li uses five paused Cloud Scheduler jobs that invoke only the IAM-private backend endpoint
`POST /internal/rhythms/{key}/run`. The dedicated
`li-os-proactivity-scheduler` service account receives `roles/run.invoker` on the backend
service only. It receives no database role, Li API token, provider credential, or Secret
Manager access.

The jobs are provisioned paused. A rhythm remains `preview_only` in database state until the
owner explicitly activates it through `POST /li/rhythms/{key}/configuration` with
`approved=true`; deployment operators then resume only that matching Scheduler job. Disabling
or standing down a rhythm also pauses its job. The database still rejects an unexpected call
for a disabled rhythm.

Cloud Scheduler supplies its scheduled timestamp and job name as headers. Li derives the run
key from those values and atomically inserts it into `rhythm_runs`; retries and missed-delivery
replays therefore cannot create a second brief. Quiet hours and timezone live in typed durable
rhythm state. No external notification channel is configured; delivery is Li Web only.

The annual job defaults to January 2 until the owner approves a birthday-derived schedule.
Do not encode a birthday in scheduler names, headers, logs, or public deployment metadata.

Migration `031_governed_proactivity.sql` must be reviewed and applied before provisioning.
This milestone does not modify or execute the artifact-retention job.
