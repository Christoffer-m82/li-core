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

## Current proactive inputs

The morning rhythm uses bounded [Level 1 reads](../../CONSTITUTION.md#11-actions-and-autonomy)
and creates no provider-side state:

- Calendar searches the next two days, retains only event titles and configured-local start times,
  and raises overlapping commitments as higher-ranked private risks. Provider event identifiers are
  replaced with one-way fingerprints; locations, descriptions, and links are not retained.
- Gmail searches at most 20 messages from the previous two days that are both unread and marked
  important, excluding promotions and social mail. It requests only From, Subject, and Date metadata;
  bodies, snippets, recipients, thread identifiers, and provider message identifiers are not retained.
- The Friday rhythm searches the next seven days of Calendar and surfaces the same minimized event
  details and overlap risks under the `next_week` category. Events more than two days away are
  low-urgency context; conflicts remain higher-ranked risks.

Both sources fail closed without blocking other grounded brief items. Calendar and private-mail
categories can be stood down independently; a stood-down category is not read. The Friday
`next_week` category can likewise be stood down before any calendar read. Every resulting item
is marked sensitive so shoulder-visible previews remain neutral. These reads do not activate a
rhythm or resume its paused scheduler job.

The annual job defaults to January 2 until the owner approves a birthday-derived schedule.
Do not encode a birthday in scheduler names, headers, logs, or public deployment metadata.

Migration `031_governed_proactivity.sql` must be reviewed and applied before provisioning.
This milestone does not modify or execute the artifact-retention job.
