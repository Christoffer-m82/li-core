param(
    [Parameter(Mandatory=$true)][string]$ProjectId,
    [Parameter(Mandatory=$true)][string]$Region,
    [Parameter(Mandatory=$true)][string]$BackendService,
    [Parameter(Mandatory=$true)][string]$GatewayService,
    [Parameter(Mandatory=$true)][string]$BackendRuntimeServiceAccount,
    [Parameter(Mandatory=$true)][string]$ImageUri,
    [Parameter(Mandatory=$true)][string]$OwnerEmail,
    [Parameter(Mandatory=$true)][string]$GoogleClientIdsJson,
    [Parameter(Mandatory=$true)][string]$ApiTokenSecretVersion,
    [Parameter(Mandatory=$true)][string]$SigningKeySecretVersion
)

$ErrorActionPreference = "Stop"
$gatewayAccount = "li-os-native-gateway-runtime@$ProjectId.iam.gserviceaccount.com"
$backendUrl = gcloud run services describe $BackendService --project=$ProjectId --region=$Region --format="value(status.url)"
if (-not $backendUrl) { throw "Private backend URL could not be resolved." }

gcloud iam service-accounts create li-os-native-gateway-runtime `
    --project=$ProjectId --display-name="Li OS Native Gateway runtime"
gcloud run services add-iam-policy-binding $BackendService --project=$ProjectId --region=$Region `
    --member="serviceAccount:$gatewayAccount" --role="roles/run.invoker"
gcloud secrets add-iam-policy-binding LI_OS_NATIVE_GATEWAY_API_TOKEN --project=$ProjectId `
    --member="serviceAccount:$gatewayAccount" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding LI_OS_NATIVE_GATEWAY_API_TOKEN --project=$ProjectId `
    --member="serviceAccount:$BackendRuntimeServiceAccount" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding LI_NATIVE_TOKEN_SIGNING_KEY --project=$ProjectId `
    --member="serviceAccount:$gatewayAccount" --role="roles/secretmanager.secretAccessor"

gcloud run deploy $GatewayService --project=$ProjectId --region=$Region --image=$ImageUri `
    --service-account=$gatewayAccount --allow-unauthenticated --ingress=all `
    --set-env-vars="LI_NATIVE_ENVIRONMENT=production,LI_NATIVE_BACKEND_URL=$backendUrl,LI_NATIVE_BACKEND_AUDIENCE=$backendUrl,LI_NATIVE_ALLOWED_EMAIL=$OwnerEmail,LI_NATIVE_GOOGLE_CLIENT_IDS=$GoogleClientIdsJson,LI_NATIVE_ACCESS_TOKEN_SECONDS=600,LI_NATIVE_REFRESH_TOKEN_DAYS=30" `
    --set-secrets="LI_NATIVE_BACKEND_API_TOKEN=LI_OS_NATIVE_GATEWAY_API_TOKEN:$ApiTokenSecretVersion,LI_NATIVE_TOKEN_SIGNING_KEY=LI_NATIVE_TOKEN_SIGNING_KEY:$SigningKeySecretVersion"

# Network reachability is public because native bearer clients cannot use Cloud Run IAM directly.
# Application endpoints fail closed without owner bootstrap or an active installation-bound token.
