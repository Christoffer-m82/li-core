param(
    [string]$SdkPath = "$env:LOCALAPPDATA\Android\Sdk"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Offline build, no Gradle/Maven downloads, cloud calls or runtime credentials.
$component = $PSScriptRoot
$repo = [IO.Path]::GetFullPath((Join-Path $component '..\..'))
$output = Join-Path $repo 'dist\android-launcher'
$tools = Join-Path $SdkPath 'build-tools\35.0.0'
$androidJar = Join-Path $SdkPath 'platforms\android-35\android.jar'
foreach ($file in @($androidJar, "$tools\aapt2.exe", "$tools\d8.bat", "$tools\zipalign.exe", "$tools\apksigner.bat")) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required local Android SDK file missing: $file" }
}
foreach ($command in @('javac', 'jar', 'keytool', 'java')) { Get-Command $command -ErrorAction Stop | Out-Null }
$apk = Join-Path $output 'Li-OS-Android-Launcher-preview.apk'
if (Test-Path -LiteralPath $apk) { throw 'Preview APK already exists; preserve it or choose a separately reviewed build.' }
New-Item -ItemType Directory -Path $output -Force | Out-Null
$work = Join-Path $output ([Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
$classes = Join-Path $work 'classes'
$dex = Join-Path $work 'dex'
New-Item -ItemType Directory -Path $classes, $dex | Out-Null
function Invoke-BuildTool([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Local build tool failed: $Command" }
}
$compiled = Join-Path $work 'resources.zip'
$unsigned = Join-Path $work 'unsigned.apk'
$aligned = Join-Path $work 'aligned.apk'
Invoke-BuildTool "$tools\aapt2.exe" @('compile', '--dir', "$component\res", '-o', $compiled)
Invoke-BuildTool "$tools\aapt2.exe" @('link', '-I', $androidJar, '--manifest', "$component\AndroidManifest.xml", '-o', $unsigned, $compiled)
Invoke-BuildTool 'javac' @('-encoding', 'UTF-8', '-source', '8', '-target', '8', '-bootclasspath', $androidJar, '-d', $classes, "$component\src\com\lios\browserlauncher\MainActivity.java")
$classFiles = @(Get-ChildItem -LiteralPath $classes -Recurse -Filter '*.class' | ForEach-Object { $_.FullName })
Invoke-BuildTool "$tools\d8.bat" (@('--min-api', '26', '--lib', $androidJar, '--output', $dex) + $classFiles)
Invoke-BuildTool 'jar' @('uf', $unsigned, '-C', $dex, 'classes.dex')
Invoke-BuildTool "$tools\zipalign.exe" @('-p', '4', $unsigned, $aligned)

# A development-only signing identity, NOT a production/distribution credential.
# Private key remains under ignored dist/. Do not publish or commit this keystore.
$keystore = Join-Path $output 'preview-signing.keystore'
if (-not (Test-Path -LiteralPath $keystore)) {
    Invoke-BuildTool 'keytool' @('-genkeypair', '-keystore', $keystore, '-storetype', 'JKS', '-alias', 'androiddebugkey', '-storepass', 'android', '-keypass', 'android', '-keyalg', 'RSA', '-keysize', '3072', '-validity', '3650', '-dname', 'CN=Li OS Local Preview, O=Development Only, C=SE')
}
Invoke-BuildTool "$tools\apksigner.bat" @('sign', '--ks', $keystore, '--ks-key-alias', 'androiddebugkey', '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', $apk, $aligned)
Invoke-BuildTool "$tools\apksigner.bat" @('verify', '--verbose', '--print-certs', $apk)
Invoke-BuildTool "$tools\zipalign.exe" @('-c', '4', $apk)
Get-FileHash -LiteralPath $apk -Algorithm SHA256
Write-Output "PASS: locally built, aligned and signature-verified preview APK: $apk"
Write-Output 'No device install, browser launch, provider call or cloud change performed.'
