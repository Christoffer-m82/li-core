[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedBackupSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedMigrationSha256,
    [Parameter(Mandatory = $true)][ValidatePattern('^li-os-migration-042-rehearsal-[a-z0-9-]+$')]
    [string]$ContainerName,
    [Parameter(Mandatory = $true)][ValidatePattern('^li_os_restore_pre042_[a-z0-9_]+$')]
    [string]$DatabaseName,
    [ValidateRange(49152, 65535)][int]$Port = 55446,
    [switch]$ConfirmDisposableTarget
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$image = 'supabase/postgres:17.6.1.136@sha256:f371b5f3f2ac0a05703f33d6e6134515fb2498cab708fb948a0aeb7481467c00'
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$migrationPath = Join-Path $repositoryRoot 'memory\migrations\042_private_portfolio_workspace.sql'
$restoreTool = Join-Path $PSScriptRoot 'restore-encrypted-backup.ps1'
$localPassword = $null
$localPasswordSecure = $null
$restorePasswordVariable = 'liOsMigration042LocalPasswordSecure'

if (-not $ConfirmDisposableTarget) {
    throw 'Refusing to create or modify a local database without -ConfirmDisposableTarget.'
}
if (Get-Variable -Name $restorePasswordVariable -Scope Global -ErrorAction SilentlyContinue) {
    throw 'Refusing to overwrite an existing global restore-password handoff variable.'
}
$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
if ((Get-Item -LiteralPath $resolvedBackup).PSIsContainer) {
    throw 'BackupPath must identify a file.'
}
$backupHash = (Get-FileHash -LiteralPath $resolvedBackup -Algorithm SHA256).Hash.ToLowerInvariant()
if ($backupHash -cne $ExpectedBackupSha256.ToLowerInvariant()) {
    throw 'Backup SHA-256 does not match the independently recorded value.'
}
$migrationHash = (Get-FileHash -LiteralPath $migrationPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($migrationHash -cne $ExpectedMigrationSha256.ToLowerInvariant()) {
    throw 'Migration 042 SHA-256 does not match the independently reviewed value.'
}

$docker = (Get-Command docker -ErrorAction Stop).Source
$psql = (Get-Command psql -ErrorAction Stop).Source
$dockerHost = (& $docker context inspect --format '{{.Endpoints.docker.Host}}').Trim()
if ($LASTEXITCODE -ne 0 -or $dockerHost -notmatch '^(npipe:|unix:)') {
    throw 'Docker must use a verified local named-pipe or Unix-socket context.'
}
$existingContainers = @(& $docker ps -a --filter "name=^/$ContainerName$" --format '{{.Names}}')
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the local Docker engine.' }
if ($existingContainers.Count -ne 0) {
    throw 'The exact disposable container name already exists. Do not reuse a prior target.'
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw 'The requested localhost port is already in use.'
}

function Invoke-PrivatePsql {
    param(
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Label,
        [string]$TargetDatabase
    )
    $selectedDatabase = if ([string]::IsNullOrWhiteSpace($TargetDatabase)) {
        $DatabaseName
    }
    else {
        $TargetDatabase
    }
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $psql
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    $startInfo.Environment['PGPASSWORD'] = $script:localPassword
    $startInfo.Environment['LC_MESSAGES'] = 'C'
    foreach ($argument in @(
        '--host', '127.0.0.1', '--port', $Port.ToString(), '--dbname', $selectedDatabase,
        '--username', 'supabase_admin', '--no-password', '--no-psqlrc',
        '--set', 'ON_ERROR_STOP=1'
    ) + $Arguments) {
        $startInfo.ArgumentList.Add($argument)
    }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        $null = $process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $null = $stderrTask.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) {
            throw "$Label failed with exit code $($process.ExitCode). Output is suppressed because restored data may be present."
        }
        return $stdout.Trim()
    }
    finally {
        $startInfo.Environment.Remove('PGPASSWORD') | Out-Null
        $process.Dispose()
    }
}

function Assert-PrivatePsqlDenied {
    param(
        [Parameter(Mandatory = $true)][string]$Sql,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $psql
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    $startInfo.Environment['PGPASSWORD'] = $script:localPassword
    $startInfo.Environment['LC_MESSAGES'] = 'C'
    foreach ($argument in @(
        '--host', '127.0.0.1', '--port', $Port.ToString(), '--dbname', $DatabaseName,
        '--username', 'supabase_admin', '--no-password', '--no-psqlrc',
        '--set', 'ON_ERROR_STOP=1', '--command', $Sql
    )) {
        $startInfo.ArgumentList.Add($argument)
    }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        $null = $process.Start()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $null = $stdoutTask.GetAwaiter().GetResult()
        $diagnostic = $stderrTask.GetAwaiter().GetResult()
        if ($process.ExitCode -eq 0 -or $diagnostic -notmatch 'permission denied') {
            throw "$Label did not produce the expected permission denial. Output is suppressed."
        }
    }
    finally {
        $startInfo.Environment.Remove('PGPASSWORD') | Out-Null
        $process.Dispose()
    }
}

try {
    $randomBytes = [byte[]]::new(32)
    [Security.Cryptography.RandomNumberGenerator]::Fill($randomBytes)
    $localPassword = [Convert]::ToBase64String($randomBytes)
    [Array]::Clear($randomBytes, 0, $randomBytes.Length)
    $localPasswordSecure = ConvertTo-SecureString $localPassword -AsPlainText -Force

    & $docker run --detach --name $ContainerName --publish "127.0.0.1:$Port`:5432" `
        --env "POSTGRES_PASSWORD=$localPassword" --env 'POSTGRES_DB=postgres' $image | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the exact disposable PostgreSQL container.' }
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        & $docker exec $ContainerName pg_isready -U postgres -h localhost | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        throw 'The disposable PostgreSQL container did not become ready. Leave it for exact-ID review.'
    }

    $null = Invoke-PrivatePsql -Label 'Empty rehearsal database creation' `
        -TargetDatabase 'postgres' -Arguments @('--command', "CREATE DATABASE $DatabaseName;")
    $null = Invoke-PrivatePsql -Label 'Empty rehearsal database grant' -Arguments @(
        '--command', "GRANT CREATE ON DATABASE $DatabaseName TO postgres; GRANT CREATE ON SCHEMA public TO postgres;"
    )
    $databaseInventoryText = Invoke-PrivatePsql -Label 'Fresh cluster database inventory' `
        -TargetDatabase 'postgres' -Arguments @(
            '--tuples-only', '--no-align', '--command',
            'SELECT datname FROM pg_database WHERE datallowconn ORDER BY datname;'
        )
    $databaseInventory = @($databaseInventoryText -split "`r?`n")
    $expectedDatabases = @($DatabaseName, 'postgres', 'template1')
    $unexpectedDatabases = @($databaseInventory | Where-Object { $_ -notin $expectedDatabases })
    $missingDatabases = @($expectedDatabases | Where-Object { $_ -notin $databaseInventory })
    if ($unexpectedDatabases.Count -ne 0 -or $missingDatabases.Count -ne 0) {
        throw 'The new disposable cluster has an unexpected database inventory; leave it for exact-ID review.'
    }
    # The pinned Supabase image initializes these compatibility roles with platform
    # grants. This fresh, exact-named cluster contains no user data. Remove only
    # their initial grants and roles so the restore tool can recreate the archive's
    # deliberately restricted compatibility boundary and verify it from scratch.
    foreach ($freshDatabase in $expectedDatabases) {
        $null = Invoke-PrivatePsql -Label 'Fresh compatibility-grant removal' `
            -TargetDatabase $freshDatabase -Arguments @(
                '--command', 'DROP OWNED BY anon, authenticated, service_role;'
            )
    }
    $null = Invoke-PrivatePsql -Label 'Fresh compatibility-role removal' `
        -TargetDatabase 'postgres' -Arguments @(
            '--command', 'DROP ROLE anon, authenticated, service_role;'
        )

    Set-Variable -Name $restorePasswordVariable -Scope Global -Value $localPasswordSecure
    function Read-Host {
        param([string]$Prompt, [switch]$AsSecureString)
        if ($Prompt -eq 'Enter the isolated target database password') {
            return $global:liOsMigration042LocalPasswordSecure
        }
        if ($Prompt -eq 'Enter the backup encryption passphrase') {
            return Microsoft.PowerShell.Utility\Read-Host -Prompt $Prompt -AsSecureString
        }
        throw 'Unexpected secret prompt.'
    }
    & $restoreTool -BackupPath $resolvedBackup -ExpectedSha256 $backupHash `
        -HostName 127.0.0.1 -Port $Port -DatabaseName $DatabaseName `
        -UserName supabase_admin -ExpectedSchemaVersion '0.41' -ConfirmIsolatedTarget

    $beforeCounts = Invoke-PrivatePsql -Label 'Pre-migration protected-count check' -Arguments @(
        '--tuples-only', '--no-align', '--command', @'
SELECT concat_ws('|',
  (SELECT count(*) FROM li_memory.users),
  (SELECT count(*) FROM li_memory.memory_records),
  (SELECT count(*) FROM li_conversation.conversations),
  (SELECT count(*) FROM li_conversation.messages));
'@
    )
    $preflight = Invoke-PrivatePsql -Label 'Restored schema-0.41 preflight' -Arguments @(
        '--tuples-only', '--no-align', '--command', @'
SELECT CASE WHEN
  (SELECT version FROM li_memory.schema_versions ORDER BY applied_at DESC LIMIT 1)='0.41'
  AND NOT EXISTS (SELECT 1 FROM li_memory.schema_versions WHERE version='0.42')
  AND (SELECT count(*) FROM li_memory.users
       WHERE user_key='christoffer' AND status='active')=1
  AND to_regclass('li_runtime_data.portfolio_holdings') IS NULL
  AND to_regprocedure('li_api.list_portfolio_holdings(text)') IS NULL
THEN 'RESTORED_PRE042_READY' ELSE 'RESTORED_PRE042_BLOCKED' END;
'@
    )
    if ($preflight -cne 'RESTORED_PRE042_READY') {
        throw 'The restored database is not the expected clean schema-0.41 source.'
    }

    $null = Invoke-PrivatePsql -Label 'Migration 042 application' -Arguments @(
        '--quiet', '--file', $migrationPath
    )
    $postflight = Invoke-PrivatePsql -Label 'Migration 042 authority validation' -Arguments @(
        '--tuples-only', '--no-align', '--command', @'
SELECT CASE WHEN
  (SELECT count(*) FROM li_memory.schema_versions WHERE version='0.42')=1
  AND (SELECT count(*) FROM li_memory.users
       WHERE user_key='christoffer' AND status='active')=1
  AND (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
       WHERE n.nspname='li_api'
         AND p.proname IN ('list_portfolio_holdings','upsert_portfolio_holding','archive_portfolio_holding')
         AND pg_get_userbyid(p.proowner)='li_memory_function_owner')=3
  AND has_function_privilege('li_backend_runtime','li_api.list_portfolio_holdings(text)','EXECUTE')
  AND has_function_privilege('li_backend_runtime',
      'li_api.upsert_portfolio_holding(uuid,text,text,text,numeric,numeric,text,numeric,text)','EXECUTE')
  AND has_function_privilege('li_backend_runtime','li_api.archive_portfolio_holding(uuid)','EXECUTE')
  AND NOT has_table_privilege('li_backend_runtime','li_runtime_data.portfolio_holdings','SELECT')
  AND NOT has_table_privilege('li_memory_api','li_runtime_data.portfolio_holdings','SELECT')
  AND (SELECT bool_and(
         NOT has_function_privilege(role_name,
           'li_api.list_portfolio_holdings(text)','EXECUTE')
         AND NOT has_function_privilege(role_name,
           'li_api.upsert_portfolio_holding(uuid,text,text,text,numeric,numeric,text,numeric,text)',
           'EXECUTE')
         AND NOT has_function_privilege(role_name,
           'li_api.archive_portfolio_holding(uuid)','EXECUTE'))
       FROM unnest(ARRAY['li_memory_theo','li_memory_owner_confirmation','li_owner_runtime',
         'li_artifact_retention','li_retention_runtime','anon','authenticated','service_role']) role_name)
  AND (SELECT c.relrowsecurity AND c.relforcerowsecurity
       FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
       WHERE n.nspname='li_runtime_data' AND c.relname='portfolio_holdings')
THEN 'MIGRATION_042_READY' ELSE 'MIGRATION_042_BLOCKED' END;
'@
    )
    if ($postflight -cne 'MIGRATION_042_READY') {
        throw 'Migration 042 committed, but its authority validation failed.'
    }

    $null = Invoke-PrivatePsql -Label 'Synthetic portfolio transaction' -Arguments @(
        '--command', @'
BEGIN;
SET SESSION AUTHORIZATION li_backend_runtime;
DO $synthetic$
DECLARE
  created JSONB;
  holding UUID;
  listed INTEGER;
BEGIN
  created := li_api.upsert_portfolio_holding(
    NULL,'avanza','LIOS-042','Synthetic migration rehearsal',10,25,'SEK',30,'SEK');
  holding := (created->>'holding_id')::UUID;
  IF created->>'quote_source' <> 'owner_manual' OR created->>'price_as_of' IS NULL THEN
    RAISE EXCEPTION 'Synthetic quote metadata failed';
  END IF;
  SELECT count(*) INTO listed FROM li_api.list_portfolio_holdings('avanza')
   WHERE holding_id=holding AND symbol='LIOS-042';
  IF listed <> 1 THEN RAISE EXCEPTION 'Synthetic list failed'; END IF;
  PERFORM li_api.upsert_portfolio_holding(
    holding,'avanza','LIOS-042','Synthetic migration rehearsal',12,25,'SEK',31,'SEK');
  BEGIN
    PERFORM li_api.upsert_portfolio_holding(
      NULL,'avanza','LIOS-042','Duplicate synthetic holding',1,1,'SEK',NULL,NULL);
    RAISE EXCEPTION 'Duplicate synthetic holding was accepted';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  IF NOT li_api.archive_portfolio_holding(holding) THEN
    RAISE EXCEPTION 'Synthetic archive failed';
  END IF;
  SELECT count(*) INTO listed FROM li_api.list_portfolio_holdings('avanza')
   WHERE holding_id=holding;
  IF listed <> 0 THEN RAISE EXCEPTION 'Archived synthetic holding remained active'; END IF;
END
$synthetic$;
ROLLBACK;
'@
    )

    foreach ($role in @('li_memory_theo','li_memory_owner_confirmation','li_owner_runtime',
        'li_artifact_retention','li_retention_runtime','anon','authenticated','service_role')) {
        Assert-PrivatePsqlDenied -Label "$role portfolio execution" -Sql (
            "SET SESSION AUTHORIZATION $role; SELECT * FROM li_api.list_portfolio_holdings(NULL);"
        )
    }
    Assert-PrivatePsqlDenied -Label 'Backend direct portfolio table read' -Sql (
        'SET SESSION AUTHORIZATION li_backend_runtime; ' +
        'SELECT count(*) FROM li_runtime_data.portfolio_holdings;'
    )

    $afterCounts = Invoke-PrivatePsql -Label 'Post-migration protected-count check' -Arguments @(
        '--tuples-only', '--no-align', '--command', @'
SELECT concat_ws('|',
  (SELECT count(*) FROM li_memory.users),
  (SELECT count(*) FROM li_memory.memory_records),
  (SELECT count(*) FROM li_conversation.conversations),
  (SELECT count(*) FROM li_conversation.messages));
'@
    )
    if ($afterCounts -cne $beforeCounts) {
        throw 'Protected canonical or conversation counts changed during rehearsal.'
    }

    Write-Host 'Migration 042 isolated restore and rehearsal passed.'
    Write-Host "Backup SHA256: $backupHash"
    Write-Host "Migration SHA256: $migrationHash"
    Write-Host "Target: $ContainerName / $DatabaseName on 127.0.0.1:$Port"
    Write-Host 'Schema: 0.42; Li/backend allowed; reviewed authorities and direct table access denied.'
    Write-Host 'Synthetic create, list, update, duplicate rejection and archive passed inside a rolled-back transaction.'
    Write-Host 'No Supabase migration, cloud deployment, provider call or personal-record value was performed or displayed.'
    Write-Host 'The isolated target is retained for exact-name review; deletion is a separate action.'
}
finally {
    Remove-Variable -Name $restorePasswordVariable -Scope Global -ErrorAction SilentlyContinue
    if ($null -ne $localPasswordSecure) { $localPasswordSecure.Dispose() }
    $localPassword = ''
}
