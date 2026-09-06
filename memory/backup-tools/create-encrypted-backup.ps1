[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$HostName,
    [Parameter(Mandatory = $true)][ValidateRange(1, 65535)][int]$Port,
    [Parameter(Mandatory = $true)][string]$DatabaseName,
    [Parameter(Mandatory = $true)][string]$UserName,
    [Parameter(Mandatory = $true)][ValidatePattern('\.pgdump\.liosenc$')][string]$OutputPath,
    [switch]$RequirePre041
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Get-SafePgDumpFailure {
    param([AllowEmptyString()][string]$Diagnostic)

    # Never return matched text, object names, SQL, or connection details.
    # These categories guide diagnosis; they do not prove a root cause.
    if ($Diagnostic -match 'password authentication failed|no password supplied|SASL authentication failed') {
        return 'AUTHENTICATION'
    }
    if ($Diagnostic -match 'server version mismatch') {
        return 'VERSION_MISMATCH'
    }
    if ($Diagnostic -match 'permission denied|must be owner|must be superuser') {
        return 'PERMISSION'
    }
    if ($Diagnostic -match 'SSL error|certificate verify failed|server does not support SSL') {
        return 'TLS'
    }
    if ($Diagnostic -match 'Connection refused|timeout expired|could not translate host name|could not connect to server|server closed the connection unexpectedly') {
        return 'CONNECTION'
    }
    return 'UNKNOWN'
}

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

$resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
$parent = Split-Path -Parent $resolvedOutput
if (Test-Path -LiteralPath $resolvedOutput) {
    throw "Refusing to overwrite an existing encrypted backup. Choose a new dated OutputPath."
}
if (-not (Test-Path -LiteralPath $parent)) {
    $null = New-Item -ItemType Directory -Path $parent
}
$partialPath = "$resolvedOutput.partial"
if (Test-Path -LiteralPath $partialPath) {
    throw "A partial output already exists. Review and remove it through a separate cleanup step."
}

$pgDump = (Get-Command pg_dump -ErrorAction Stop).Source
$pgRestore = (Get-Command pg_restore -ErrorAction Stop).Source
$key = $null
$partialCreated = $false
$dump = $null
$restore = $null
$encrypted = $null

try {
$databaseSecret = Read-Host "Enter the source database password" -AsSecureString
$databasePassword = ConvertFrom-PrivateSecureString $databaseSecret
if ([string]::IsNullOrWhiteSpace($databasePassword)) {
    throw "Database password was empty."
}
if ($RequirePre041) {
    # Use the same private credential and client installation as the export.
    # No password is requested a second time or passed on a command line.
    $preflightInfo = [Diagnostics.ProcessStartInfo]::new()
    $clientName = if ($IsWindows) { 'psql.exe' } else { 'psql' }
    $preflightInfo.FileName = Join-Path (Split-Path -Parent $pgDump) $clientName
    $preflightInfo.UseShellExecute = $false
    $preflightInfo.RedirectStandardOutput = $true
    $preflightInfo.RedirectStandardError = $true
    $preflightInfo.CreateNoWindow = $true
    $preflightInfo.Environment['PGPASSWORD'] = $databasePassword
    $preflightInfo.Environment['LC_MESSAGES'] = 'C'
    $preflightInfo.Environment['PGCONNECT_TIMEOUT'] = '15'
    $preflightSql = @'
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SELECT CASE WHEN
  EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version = '0.40')
  AND NOT EXISTS (SELECT 1 FROM li_memory.schema_versions
                 WHERE string_to_array(version, '.')::integer[] > ARRAY[0,40])
  AND (SELECT COUNT(*) FROM li_memory.users WHERE user_key='christoffer' AND status='active')=1
  AND to_regprocedure('li_api.mark_chat_turn_effect_started(uuid,text,uuid)') IS NULL
THEN 'PRE041_READY' ELSE 'PRE041_BLOCKED' END;
ROLLBACK;
'@
    foreach ($argument in @('--no-psqlrc', '--no-password', '--host', $HostName,
        '--port', $Port.ToString(), '--dbname', $DatabaseName, '--username', $UserName,
        '--quiet', '--tuples-only', '--no-align', '--set', 'ON_ERROR_STOP=1',
        '--command', $preflightSql)) {
        $preflightInfo.ArgumentList.Add($argument)
    }
    $preflight = [Diagnostics.Process]::new()
    $preflight.StartInfo = $preflightInfo
    try {
        $null = $preflight.Start()
        $preflightOutputTask = $preflight.StandardOutput.ReadToEndAsync()
        $preflightErrorTask = $preflight.StandardError.ReadToEndAsync()
        $preflight.WaitForExit()
        $preflightOutput = $preflightOutputTask.GetAwaiter().GetResult()
        $preflightDiagnostic = $preflightErrorTask.GetAwaiter().GetResult()
        if ($preflight.ExitCode -ne 0) {
            $failureCategory = Get-SafePgDumpFailure -Diagnostic $preflightDiagnostic
            throw "Source preflight failed. Category: $failureCategory. Raw output remains suppressed. No backup was started."
        }
        if ($preflightOutput.Trim() -cne 'PRE041_READY') {
            throw 'Source preflight prerequisites failed. No backup was started.'
        }
    }
    finally {
        $preflightDiagnostic = $null
        $preflightOutput = $null
        $preflightInfo.Environment.Remove('PGPASSWORD') | Out-Null
        $preflight.Dispose()
    }
    Write-Host 'PASS: schema 0.40, no later schema, one active owner, effect function absent.'
    Write-Host 'The export will use the same database password. No second database password entry is needed.'
}
$backupSecret = Read-Host "Create a new backup encryption passphrase" -AsSecureString
$backupConfirmation = Read-Host "Repeat the new backup encryption passphrase" -AsSecureString
$backupPassword = ConvertFrom-PrivateSecureString $backupSecret
$backupPasswordConfirmation = ConvertFrom-PrivateSecureString $backupConfirmation

if ([string]::IsNullOrWhiteSpace($databasePassword)) {
    throw "Database password was empty."
}
if ($backupPassword.Length -lt 16) {
    throw "Backup passphrase must contain at least 16 characters."
}
if ($backupPassword -cne $backupPasswordConfirmation) {
    throw "Backup passphrases did not match."
}

$magic = [Text.Encoding]::ASCII.GetBytes("LIOSBKP1")
$salt = [byte[]]::new(16)
[Security.Cryptography.RandomNumberGenerator]::Fill($salt)
$iterations = 600000
$chunkSize = 1024 * 1024
$derive = [Security.Cryptography.Rfc2898DeriveBytes]::new(
    $backupPassword,
    $salt,
    $iterations,
    [Security.Cryptography.HashAlgorithmName]::SHA256
)
$key = $derive.GetBytes(32)
$derive.Dispose()
    $dumpInfo = [Diagnostics.ProcessStartInfo]::new()
    $dumpInfo.FileName = $pgDump
    $dumpInfo.UseShellExecute = $false
    $dumpInfo.RedirectStandardOutput = $true
    $dumpInfo.RedirectStandardError = $true
    $dumpInfo.CreateNoWindow = $true
    $dumpInfo.Environment["PGPASSWORD"] = $databasePassword
    $dumpInfo.Environment["LC_MESSAGES"] = "C"
    foreach ($argument in @(
        "--host", $HostName,
        "--port", $Port.ToString(),
        "--dbname", $DatabaseName,
        "--username", $UserName,
        "--format", "custom",
        "--compress", "6",
        "--no-password"
    )) {
        $dumpInfo.ArgumentList.Add($argument)
    }

    $dump = [Diagnostics.Process]::new()
    $dump.StartInfo = $dumpInfo
    $null = $dump.Start()
    $dumpErrorTask = $dump.StandardError.ReadToEndAsync()

    $file = [IO.File]::Open($partialPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $partialCreated = $true
    try {
        $file.Write($magic)
        $file.Write($salt)
        $file.Write([BitConverter]::GetBytes($iterations))
        $file.Write([BitConverter]::GetBytes($chunkSize))

        $aes = [Security.Cryptography.AesGcm]::new($key, 16)
        try {
            $buffer = [byte[]]::new($chunkSize)
            [long]$frame = 0
            while (($count = $dump.StandardOutput.BaseStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $plaintext = if ($count -eq $buffer.Length) {
                    $buffer
                }
                else {
                    $buffer[0..($count - 1)]
                }
                $nonce = [byte[]]::new(12)
                [Security.Cryptography.RandomNumberGenerator]::Fill($nonce)
                $ciphertext = [byte[]]::new($count)
                $tag = [byte[]]::new(16)
                $aes.Encrypt($nonce, $plaintext, $ciphertext, $tag, (New-FrameAad -Index $frame -Length $count))
                $file.Write([BitConverter]::GetBytes($count))
                $file.Write($nonce)
                $file.Write($tag)
                $file.Write($ciphertext)
                if (-not [object]::ReferenceEquals($plaintext, $buffer)) {
                    [Array]::Clear($plaintext, 0, $plaintext.Length)
                }
                $frame++
            }

            $nonce = [byte[]]::new(12)
            [Security.Cryptography.RandomNumberGenerator]::Fill($nonce)
            $tag = [byte[]]::new(16)
            $aes.Encrypt($nonce, [byte[]]::new(0), [byte[]]::new(0), $tag, (New-FrameAad -Index $frame -Length 0))
            $file.Write([BitConverter]::GetBytes(0))
            $file.Write($nonce)
            $file.Write($tag)
            $file.Flush($true)
        }
        finally {
            if ($null -ne $buffer) {
                [Array]::Clear($buffer, 0, $buffer.Length)
            }
            if ($null -ne $aes) {
                $aes.Dispose()
            }
        }
    }
    finally {
        $file.Dispose()
    }

    $dump.WaitForExit()
    $dumpDiagnostic = $dumpErrorTask.GetAwaiter().GetResult()
    if ($dump.ExitCode -ne 0) {
        $failureCategory = Get-SafePgDumpFailure -Diagnostic $dumpDiagnostic
        $dumpDiagnostic = $null
        throw "pg_dump failed with exit code $($dump.ExitCode). Category: $failureCategory. Raw output remains suppressed. No validated backup was created."
    }
    $dumpDiagnostic = $null

    $restoreInfo = [Diagnostics.ProcessStartInfo]::new()
    $restoreInfo.FileName = $pgRestore
    $restoreInfo.UseShellExecute = $false
    $restoreInfo.RedirectStandardInput = $true
    $restoreInfo.RedirectStandardOutput = $true
    $restoreInfo.RedirectStandardError = $true
    $restoreInfo.CreateNoWindow = $true
    $restoreInfo.ArgumentList.Add("--list")

    $restore = [Diagnostics.Process]::new()
    $restore.StartInfo = $restoreInfo
    $null = $restore.Start()
    $restoreOutputTask = $restore.StandardOutput.ReadToEndAsync()
    $restoreErrorTask = $restore.StandardError.ReadToEndAsync()
    $restoreInputOpen = $true

    $encrypted = [IO.File]::OpenRead($partialPath)
    $readMagic = Read-ExactBytes -Stream $encrypted -Count 8
    if ([Text.Encoding]::ASCII.GetString($readMagic) -cne "LIOSBKP1") {
        throw "Invalid encrypted backup header."
    }
    $readSalt = Read-ExactBytes -Stream $encrypted -Count 16
    $readIterations = [BitConverter]::ToInt32((Read-ExactBytes -Stream $encrypted -Count 4), 0)
    $readChunkSize = [BitConverter]::ToInt32((Read-ExactBytes -Stream $encrypted -Count 4), 0)
    if ($readIterations -lt 100000 -or $readChunkSize -lt 1 -or $readChunkSize -gt 16777216) {
        throw "Invalid encrypted backup parameters."
    }
    $readDerive = [Security.Cryptography.Rfc2898DeriveBytes]::new(
        $backupPassword,
        $readSalt,
        $readIterations,
        [Security.Cryptography.HashAlgorithmName]::SHA256
    )
    $readKey = $readDerive.GetBytes(32)
    $readDerive.Dispose()
    $readAes = [Security.Cryptography.AesGcm]::new($readKey, 16)
    try {
        [long]$frame = 0
        while ($true) {
            $length = [BitConverter]::ToInt32((Read-ExactBytes -Stream $encrypted -Count 4), 0)
            if ($length -lt 0 -or $length -gt $readChunkSize) {
                throw "Invalid encrypted frame length."
            }
            $nonce = Read-ExactBytes -Stream $encrypted -Count 12
            $tag = Read-ExactBytes -Stream $encrypted -Count 16
            $ciphertext = Read-ExactBytes -Stream $encrypted -Count $length
            $plaintext = [byte[]]::new($length)
            $readAes.Decrypt($nonce, $ciphertext, $tag, $plaintext, (New-FrameAad -Index $frame -Length $length))
            if ($length -eq 0) {
                break
            }
            if ($restoreInputOpen) {
                try {
                    $restore.StandardInput.BaseStream.Write($plaintext, 0, $plaintext.Length)
                }
                catch [System.IO.IOException] {
                    $restoreInputOpen = $false
                }
            }
            [Array]::Clear($plaintext, 0, $plaintext.Length)
            $frame++
        }
        if ($encrypted.Position -ne $encrypted.Length) {
            throw "Unexpected bytes follow the authenticated backup terminator."
        }
    }
    finally {
        $readAes.Dispose()
        [Array]::Clear($readKey, 0, $readKey.Length)
    }

    try {
        $restore.StandardInput.BaseStream.Close()
    }
    catch [System.IO.IOException] {
    }
    $restore.WaitForExit()
    $archiveList = $restoreOutputTask.GetAwaiter().GetResult()
    $null = $restoreErrorTask.GetAwaiter().GetResult()
    if ($restore.ExitCode -ne 0) {
        throw "Encrypted archive validation failed with exit code $($restore.ExitCode). Output is suppressed."
    }
    $archiveEntries = ($archiveList -split "`r?`n" | Where-Object { $_ -match '^\d+;' }).Count
    if ($archiveEntries -lt 1) {
        throw "The backup archive contains no restorable catalogue entries."
    }

    $encrypted.Dispose()
    $encrypted = $null
    Move-Item -LiteralPath $partialPath -Destination $resolvedOutput
    $partialCreated = $false
    $hash = (Get-FileHash -LiteralPath $resolvedOutput -Algorithm SHA256).Hash.ToLowerInvariant()
    $size = (Get-Item -LiteralPath $resolvedOutput).Length
    Write-Host "Encrypted backup created and authenticated archive validation passed."
    Write-Host "Path: $resolvedOutput"
    Write-Host "Bytes: $size"
    Write-Host "SHA256: $hash"
    Write-Host "Archive entries: $archiveEntries"
}
catch {
    if ($null -ne $restore -and -not $restore.HasExited) {
        try { $restore.StandardInput.Close() } catch { }
        $restore.Kill($true)
    }
    throw
}
finally {
    if ($null -ne $dump -and -not $dump.HasExited) {
        $dump.Kill($true)
    }
    if ($null -ne $encrypted) {
        $encrypted.Dispose()
    }
    if ($partialCreated -and (Test-Path -LiteralPath $partialPath)) {
        Remove-Item -LiteralPath $partialPath -Force
    }
    if ($null -ne $key) {
        [Array]::Clear($key, 0, $key.Length)
    }
    $databasePassword = ""
    $backupPassword = ""
    $backupPasswordConfirmation = ""
    if ($null -ne $dumpInfo) { $dumpInfo.Environment.Remove('PGPASSWORD') | Out-Null }
    foreach ($secret in @($databaseSecret, $backupSecret, $backupConfirmation)) {
        if ($null -ne $secret) { $secret.Dispose() }
    }
}
