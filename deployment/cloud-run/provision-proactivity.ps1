param(
    [Parameter(Mandatory=$true)][string]$ProjectId,
    [string]$Region = "europe-west1",
    [string]$BackendService = "li-os"
)
$ErrorActionPreference = "Stop"
$account = "li-os-proactivity-scheduler@$ProjectId.iam.gserviceaccount.com"
$backendUrl = gcloud run services describe $BackendService --project=$ProjectId --region=$Region --format="value(status.url)"

gcloud iam service-accounts create li-os-proactivity-scheduler --project=$ProjectId `
    --display-name="Li OS governed proactivity scheduler"
gcloud run services add-iam-policy-binding $BackendService --project=$ProjectId --region=$Region `
    --member="serviceAccount:$account" --role=roles/run.invoker

$jobs = @(
    @{ Key="morning"; Cron="30 7 * * 1-5" },
    @{ Key="friday"; Cron="0 16 * * 5" },
    @{ Key="monthly"; Cron="0 9 1 * *" },
    @{ Key="quarterly"; Cron="0 9 1 1,4,7,10 *" },
    @{ Key="annual"; Cron="0 9 2 1 *" }
)
foreach ($job in $jobs) {
    $jobName = "li-os-$($job.Key)-rhythm"
    gcloud scheduler jobs create http $jobName --project=$ProjectId `
        --location=$Region --schedule="$($job.Cron)" --time-zone="Europe/Berlin" `
        --uri="$backendUrl/internal/rhythms/$($job.Key)/run" --http-method=POST `
        --oidc-service-account-email=$account --oidc-token-audience=$backendUrl `
        --headers="Content-Type=application/json" --message-body="{}"
    if ($LASTEXITCODE -ne 0) { throw "Could not create scheduler job $jobName" }
    gcloud scheduler jobs pause $jobName --project=$ProjectId --location=$Region
    if ($LASTEXITCODE -ne 0) { throw "Could not pause scheduler job $jobName" }
}
