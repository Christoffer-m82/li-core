[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSha256,
    [Parameter(Mandatory = $true)][string]$HostName,
    [Parameter(Mandatory = $true)][ValidateRange(1, 65535)][int]$Port,
    [Parameter(Mandatory = $true)][string]$DatabaseName,
    [Parameter(Mandatory = $true)][string]$UserName,
    [string]$ExpectedSchemaVersion = "0.39",
    [switch]$ConfirmIsolatedTarget
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function ConvertFrom-PrivateSecureString {
    param([Parameter(Mandatory = $true)][securestring]$Value)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Read-ExactBytes {
    param(
        [Parameter(Mandatory = $true)][System.IO.Stream]$Stream,
        [Parameter(Mandatory = $true)][int]$Count
    )

    $result = [byte[]]::new($Count)
    $offset = 0
    while ($offset -lt $Count) {
        $read = $Stream.Read($result, $offset, $Count - $offset)
        if ($read -eq 0) {
            throw "Encrypted backup ended unexpectedly."
        }
        $offset += $read
    }
    return ,$result
}

function New-FrameAad {
    param([long]$Index, [int]$Length)

    $aad = [System.Collections.Generic.List[byte]]::new()
    $aad.AddRange([Text.Encoding]::ASCII.GetBytes("LIOSBKP1"))
    $aad.AddRange([BitConverter]::GetBytes($Index))
    $aad.AddRange([BitConverter]::GetBytes($Length))
    return $aad.ToArray()
}

function Invoke-PostgresQuery {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string]$Password,
        [Parameter(Mandatory = $true)][string]$Sql
    )

    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Executable
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    $startInfo.Environment["PGPASSWORD"] = $Password
    foreach ($argument in @(
        "--host", $HostName,
        "--port", $Port.ToString(),
        "--dbname", $DatabaseName,
        "--username", $UserName,
        "--no-password",
        "--no-psqlrc",
        "--set", "ON_ERROR_STOP=1",
        "--tuples-only",
        "--no-align",
        "--command", $Sql
    )) {
        $startInfo.ArgumentList.Add($argument)
    }

    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $null = $process.Start()
    $output = $process.StandardOutput.ReadToEnd()
    $errorText = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        throw "PostgreSQL validation failed with exit code $($process.ExitCode): $errorText"
    }
    return $output.Trim()
}

if (-not $ConfirmIsolatedTarget) {
    throw "Refusing to restore without -ConfirmIsolatedTarget. Use only a disposable, non-production database."
}
if ($DatabaseName -notmatch '^li_os_(restore|recovery|drill)_[a-z0-9_]+$') {
    throw "The target database name must begin with li_os_restore_, li_os_recovery_, or li_os_drill_."
}

$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
if ((Get-Item -LiteralPath $resolvedBackup).PSIsContainer) {
    throw "BackupPath must identify a file."
}
$actualHash = (Get-FileHash -LiteralPath $resolvedBackup -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -cne $ExpectedSha256.ToLowerInvariant()) {
    throw "Backup SHA-256 does not match the independently recorded value."
}

$psql = (Get-Command psql -ErrorAction Stop).Source
$pgRestore = (Get-Command pg_restore -ErrorAction Stop).Source
$databaseSecret = Read-Host "Enter the isolated target database password" -AsSecureString
$databasePassword = ConvertFrom-PrivateSecureString $databaseSecret
if ([string]::IsNullOrWhiteSpace($databasePassword)) {
    throw "Target database password was empty."
}

$nonSystemTableCount = Invoke-PostgresQuery -Executable $psql -Password $databasePassword -Sql @"
SELECT count(*)
FROM pg_catalog.pg_class AS c
JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname !~ '^pg_(toast|temp_)';
"@
if ($nonSystemTableCount -ne "0") {
    $databasePassword = ""
    throw "Refusing to restore because the isolated target already contains non-system tables."
}

$backupSecret = Read-Host "Enter the backup encryption passphrase" -AsSecureString
$backupPassword = ConvertFrom-PrivateSecureString $backupSecret
if ([string]::IsNullOrWhiteSpace($backupPassword)) {
    $databasePassword = ""
    throw "Backup passphrase was empty."
}

$encrypted = $null
$key = $null
$restore = $null
$startedAt = [DateTimeOffset]::UtcNow
try {
    $encrypted = [IO.File]::OpenRead($resolvedBackup)
    $magic = Read-ExactBytes -Stream $encrypted -Count 8
    if ([Text.Encoding]::ASCII.GetString($magic) -cne "LIOSBKP1") {
        throw "Invalid encrypted backup header."
    }
    $salt = Read-ExactBytes -Stream $encrypted -Count 16
    $iterations = [BitConverter]::ToInt32((Read-ExactBytes -Stream $encrypted -Count 4), 0)
    $chunkSize = [BitConverter]::ToInt32((Read-ExactBytes -Stream $encrypted -Count 4), 0)
    if ($iterations -lt 100000 -or $chunkSize -lt 1 -or $chunkSize -gt 16777216) {
        throw "Invalid encrypted backup parameters."
    }

    $derive = [Security.Cryptography.Rfc2898DeriveBytes]::new(
        $backupPassword,
        $salt,
        $iterations,
        [Security.Cryptography.HashAlgorithmName]::SHA256
    )
    $key = $derive.GetBytes(32)
    $derive.Dispose()

    $restoreInfo = [Diagnostics.ProcessStartInfo]::new()
    $restoreInfo.FileName = $pgRestore
    $restoreInfo.UseShellExecute = $false
    $restoreInfo.RedirectStandardInput = $true
    $restoreInfo.RedirectStandardOutput = $true
    $restoreInfo.RedirectStandardError = $true
    $restoreInfo.CreateNoWindow = $true
    $restoreInfo.Environment["PGPASSWORD"] = $databasePassword
    foreach ($argument in @(
        "--host", $HostName,
        "--port", $Port.ToString(),
        "--dbname", $DatabaseName,
        "--username", $UserName,
        "--no-password",
        "--exit-on-error",
        "--no-owner",
        "--no-privileges"
    )) {
        $restoreInfo.ArgumentList.Add($argument)
    }

    $restore = [Diagnostics.Process]::new()
    $restore.StartInfo = $restoreInfo
    $null = $restore.Start()
    $restoreOutputTask = $restore.StandardOutput.ReadToEndAsync()
    $restoreErrorTask = $restore.StandardError.ReadToEndAsync()

    $aes = [Security.Cryptography.AesGcm]::new($key, 16)
    try {
        [long]$frame = 0
        while ($true) {
            $length = [BitConverter]::ToInt32((Read-ExactBytes -Stream $encrypted -Count 4), 0)
            if ($length -lt 0 -or $length -gt $chunkSize) {
                throw "Invalid encrypted frame length."
            }
            $nonce = Read-ExactBytes -Stream $encrypted -Count 12
            $tag = Read-ExactBytes -Stream $encrypted -Count 16
            $ciphertext = Read-ExactBytes -Stream $encrypted -Count $length
            $plaintext = [byte[]]::new($length)
            $aes.Decrypt($nonce, $ciphertext, $tag, $plaintext, (New-FrameAad -Index $frame -Length $length))
            if ($length -eq 0) {
                break
            }
            try {
                $restore.StandardInput.BaseStream.Write($plaintext, 0, $plaintext.Length)
            }
            finally {
                [Array]::Clear($plaintext, 0, $plaintext.Length)
            }
            $frame++
        }
        if ($encrypted.Position -ne $encrypted.Length) {
            throw "Unexpected bytes follow the authenticated backup terminator."
        }
        $restore.StandardInput.BaseStream.Close()
    }
    finally {
        $aes.Dispose()
    }

    $restore.WaitForExit()
    $restoreOutput = $restoreOutputTask.GetAwaiter().GetResult()
    $restoreError = $restoreErrorTask.GetAwaiter().GetResult()
    if ($restore.ExitCode -ne 0) {
        throw "pg_restore failed with exit code $($restore.ExitCode). Output is suppressed because it may contain restored data."
    }

    $validation = Invoke-PostgresQuery -Executable $psql -Password $databasePassword -Sql @"
SELECT concat_ws('|',
    (SELECT version FROM li_memory.schema_versions ORDER BY applied_at DESC LIMIT 1),
    (SELECT count(*) FROM li_memory.users),
    (SELECT count(*) FROM li_memory.memory_records),
    (SELECT count(*) FROM information_schema.tables
       WHERE table_schema IN ('li_memory', 'li_conversation', 'li_runtime_data', 'li_tasks'))
);
"@
    $parts = $validation -split '\|', 4
    if ($parts.Count -ne 4 -or $parts[0] -cne $ExpectedSchemaVersion) {
        throw "Restored schema validation failed or returned an unexpected schema version."
    }

    $completedAt = [DateTimeOffset]::UtcNow
    $elapsed = $completedAt - $startedAt
    Write-Host "Isolated restore and retrieval validation passed."
    Write-Host "Backup SHA256: $actualHash"
    Write-Host "Target: $DatabaseName on $HostName"
    Write-Host "Schema version: $($parts[0])"
    Write-Host "Owners: $($parts[1])"
    Write-Host "Canonical memory records: $($parts[2])"
    Write-Host "Canonical tables: $($parts[3])"
    Write-Host "Restore validation seconds: $([Math]::Round($elapsed.TotalSeconds, 2))"
    Write-Host "RPO must be calculated separately from the backup creation time and the recovery incident time."
    Write-Host "The isolated target is intentionally retained for operator review; deletion requires a separate exact action."
}
catch {
    $failureMessage = $_.Exception.Message
    if ($null -ne $restore -and -not $restore.HasExited) {
        try { $restore.StandardInput.Close() } catch { }
        $restore.Kill($true)
    }
    throw "Restore drill failed. Treat the target as partial and do not reuse it: $failureMessage"
}
finally {
    if ($null -ne $encrypted) {
        $encrypted.Dispose()
    }
    if ($null -ne $key) {
        [Array]::Clear($key, 0, $key.Length)
    }
    $databasePassword = ""
    $backupPassword = ""
}
