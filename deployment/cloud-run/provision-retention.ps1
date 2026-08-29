param(
    [Parameter(Mandatory = $true)][string]$BackendImage,
    [string]$ProjectId = "li-os-staging",
    [string]$Region = "europe-west1",
    [string]$Bucket = "li-os-staging-private-artifacts"
)

# Run only after migration 022 is applied and the three retention DB secrets exist.
$runtimeAccount = "li-os-retention@$ProjectId.iam.gserviceaccount.com"
$schedulerAccount = "li-os-retention-scheduler@$ProjectId.iam.gserviceaccount.com"
$jobName = "li-os-artifact-retention"
$schedulerName = "li-os-artifact-retention-daily"
$customRole = "liArtifactRetentionObjectOperator"

function Invoke-Gcloud {
    & gcloud @args
    if ($LASTEXITCODE -ne 0) {
        throw "Google Cloud command failed. No secret values were printed by this script."
    }
}

Invoke-Gcloud iam service-accounts create li-os-retention `
    --project=$ProjectId --display-name="Li OS artifact retention job"
Invoke-Gcloud iam service-accounts create li-os-retention-scheduler `
    --project=$ProjectId --display-name="Li OS artifact retention scheduler"

Invoke-Gcloud iam roles create $customRole --project=$ProjectId `
    --file=deployment/cloud-run/retention-object-role.yaml
Invoke-Gcloud storage buckets add-iam-policy-binding "gs://$Bucket" `
    --project=$ProjectId --member="serviceAccount:$runtimeAccount" `
    --role="projects/$ProjectId/roles/$customRole"

foreach ($secretName in @("LI_RETENTION_DB_HOST", "LI_RETENTION_DB_USER", "LI_RETENTION_DB_PASSWORD")) {
    Invoke-Gcloud secrets add-iam-policy-binding $secretName --project=$ProjectId `
        --member="serviceAccount:$runtimeAccount" --role=roles/secretmanager.secretAccessor
}

Invoke-Gcloud run jobs deploy $jobName --project=$ProjectId --region=$Region `
    --image=$BackendImage --service-account=$runtimeAccount --command=python `
    --args=-m,app.retention_job --tasks=1 --max-retries=3 --task-timeout=10m `
    --set-env-vars="LI_OS_ENVIRONMENT=staging,LI_OS_ARTIFACT_BUCKET=$Bucket,LI_OS_DB_PORT=5432,LI_OS_DB_NAME=postgres,LI_OS_DB_SSLMODE=require" `
    --set-secrets="LI_OS_DB_HOST=LI_RETENTION_DB_HOST:latest,LI_OS_DB_USER=LI_RETENTION_DB_USER:latest,LI_OS_DB_PASSWORD=LI_RETENTION_DB_PASSWORD:latest"

Invoke-Gcloud run jobs add-iam-policy-binding $jobName --project=$ProjectId --region=$Region `
    --member="serviceAccount:$schedulerAccount" --role=roles/run.invoker

$runUri = "https://run.googleapis.com/v2/projects/$ProjectId/locations/$Region/jobs/${jobName}:run"
Invoke-Gcloud scheduler jobs create http $schedulerName --project=$ProjectId --location=$Region `
    --schedule="17 3 * * *" --time-zone="Europe/Berlin" --uri=$runUri `
    --http-method=POST --oauth-service-account-email=$schedulerAccount `
    --oauth-token-scope=https://www.googleapis.com/auth/cloud-platform
