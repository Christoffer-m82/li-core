from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESTORE_TOOL = ROOT / "memory" / "backup-tools" / "restore-encrypted-backup.ps1"
CREATE_TOOL = ROOT / "memory" / "backup-tools" / "create-encrypted-backup.ps1"
REHEARSE_042_TOOL = ROOT / "memory" / "backup-tools" / "rehearse-migration-042.ps1"


def _tool_text() -> str:
    return RESTORE_TOOL.read_text(encoding="utf-8")


def _create_tool_text() -> str:
    return CREATE_TOOL.read_text(encoding="utf-8")


def _rehearse_042_tool_text() -> str:
    return REHEARSE_042_TOOL.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("diagnostic", "expected"),
    [
        ('FATAL: password authentication failed for user "synthetic-private"', "AUTHENTICATION"),
        ('error: aborting because of server version mismatch', "VERSION_MISMATCH"),
        ('ERROR: permission denied for table synthetic_private', "PERMISSION"),
        ('connection to server at "synthetic-private" failed: Connection refused', "CONNECTION"),
        ('connection to server failed: timeout expired', "CONNECTION"),
        ('could not translate host name "synthetic-private" to address', "CONNECTION"),
        ('SSL error: certificate verify failed synthetic-private', "TLS"),
        ('ERROR: query failed: synthetic-private unrecognized error', "UNKNOWN"),
        ('', "UNKNOWN"),
    ],
)
def test_dump_diagnostic_returns_only_fixed_categories(diagnostic: str, expected: str) -> None:
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell 7 is required for executable backup-tool tests")
    # Extract only the pure function: never execute backup code or secret prompts.
    command = r"""
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    'memory/backup-tools/create-encrypted-backup.ps1', [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'PowerShell parse failed' }
$fn = $ast.Find({param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -eq 'Get-SafePgDumpFailure'
}, $true)
if ($null -eq $fn) { throw 'Missing safe diagnostic function' }
. ([scriptblock]::Create($fn.Extent.Text))
$inputText = [Console]::In.ReadToEnd() | ConvertFrom-Json
Get-SafePgDumpFailure -Diagnostic $inputText
"""
    result = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=ROOT, input=json.dumps(diagnostic), text=True, capture_output=True,
        timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected
    assert result.stderr == ""


def test_dump_failure_stays_closed_and_does_not_render_raw_diagnostic() -> None:
    text = _create_tool_text()
    assert 'Get-SafePgDumpFailure -Diagnostic $dumpDiagnostic' in text
    assert 'Category: $failureCategory. Raw output remains suppressed.' in text
    assert 'throw $dumpDiagnostic' not in text
    assert 'Write-Host $dumpDiagnostic' not in text


def test_pre041_gate_uses_same_password_before_encryption_prompts() -> None:
    text = _create_tool_text()
    assert text.count('Read-Host "Enter the source database password"') == 1
    assert "$preflightInfo.Environment['PGPASSWORD'] = $databasePassword" in text
    assert '$dumpInfo.Environment["PGPASSWORD"] = $databasePassword' in text
    assert "BEGIN READ ONLY;" in text
    assert "string_to_array(version, '.')::integer[] > ARRAY[0,40]" in text
    assert "user_key='christoffer' AND status='active'" in text
    assert "to_regprocedure('li_api.mark_chat_turn_effect_started(uuid,text,uuid)') IS NULL" in text
    assert "$expectedPreflight = 'PRE041_READY'" in text
    gate = text.index("$preflightOutput.Trim() -cne $expectedPreflight")
    assert gate < text.index('Read-Host "Create a new backup encryption passphrase"')
    assert gate < text.index('$dump.Start()')


def test_pre042_gate_requires_clean_schema_041_portfolio_baseline() -> None:
    text = _create_tool_text()

    assert "[switch]$RequirePre042" in text
    assert "$RequirePre041 -and $RequirePre042" in text
    assert "WHERE version = '0.41'" in text
    assert "string_to_array(version, '.')::integer[] > ARRAY[0,41]" in text
    assert "to_regclass('li_runtime_data.portfolio_holdings') IS NULL" in text
    assert "to_regprocedure('li_api.list_portfolio_holdings(text)') IS NULL" in text
    assert "li_api.upsert_portfolio_holding(uuid,text,text,text,numeric,numeric,text,numeric,text)" in text
    assert "to_regprocedure('li_api.archive_portfolio_holding(uuid)') IS NULL" in text
    assert "$expectedPreflight = 'PRE042_READY'" in text


def test_source_schema_gates_are_mutually_exclusive(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell 7 is required for executable backup-tool tests")
    command = r"""
$ErrorActionPreference = 'Stop'
$settings = [Console]::In.ReadToEnd() | ConvertFrom-Json
$global:backupTestPromptCount = 0
function Read-Host { $global:backupTestPromptCount++; throw 'Unexpected prompt' }
try {
    & ./memory/backup-tools/create-encrypted-backup.ps1 -HostName invalid.example -Port 5432 `
        -DatabaseName synthetic -UserName synthetic -OutputPath $settings.output `
        -RequirePre041 -RequirePre042
    throw 'Unexpected completion'
} catch {
    if ($_.Exception.Message -notlike '*only one source-schema*') { throw }
}
if ($global:backupTestPromptCount -ne 0) { throw 'A secret prompt occurred before gate validation' }
Write-Output 'SAFE_STOP'
"""
    result = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=ROOT,
        input=json.dumps({"output": str(tmp_path / "test.pgdump.liosenc")}),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "SAFE_STOP"
    assert result.stderr == ""


def test_preflight_start_failure_stops_before_encryption_or_export(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("PowerShell 7 is required for executable backup-tool tests")
    # A nonexistent synthetic client prevents any database connection. No real
    # secrets are used, even in the masked-prompt substitute.
    command = r"""
$ErrorActionPreference = 'Stop'
$settings = [Console]::In.ReadToEnd() | ConvertFrom-Json
$global:backupTestPromptCount = 0
function Read-Host {
    param($Prompt, [switch]$AsSecureString)
    $global:backupTestPromptCount++
    if ($Prompt -ne 'Enter the source database password') { throw 'Unexpected prompt' }
    return ConvertTo-SecureString 'synthetic-test-only' -AsPlainText -Force
}
function Get-Command {
    param($Name, $ErrorAction)
    return [pscustomobject]@{ Source = (Join-Path $settings.directory 'missing-client.exe') }
}
try {
    & ./memory/backup-tools/create-encrypted-backup.ps1 -HostName invalid.example -Port 5432 `
        -DatabaseName synthetic -UserName synthetic -OutputPath $settings.output -RequirePre041
    throw 'Unexpected completion'
} catch {
    if ($_.Exception.Message -notlike '*start process*') { throw }
}
if ($global:backupTestPromptCount -ne 1) { throw 'Expected exactly one private prompt' }
if (Test-Path -LiteralPath $settings.output) { throw 'Unexpected output file' }
if (Test-Path -LiteralPath ($settings.output + '.partial')) { throw 'Unexpected partial file' }
Write-Output 'SAFE_STOP'
"""
    result = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=ROOT,
        input=json.dumps({"directory": str(tmp_path), "output": str(tmp_path / "test.pgdump.liosenc")}),
        text=True, capture_output=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "SAFE_STOP"
    assert result.stderr == ""


def test_create_tool_never_accepts_secrets_as_parameters_or_overwrites_output() -> None:
    text = _create_tool_text()

    assert "Read-Host \"Enter the source database password\" -AsSecureString" in text
    assert "Read-Host \"Create a new backup encryption passphrase\" -AsSecureString" in text
    assert "DatabasePassword" not in text
    assert "BackupPassword" not in text
    assert "Refusing to overwrite an existing encrypted backup" in text
    assert "Move-Item -LiteralPath $partialPath -Destination $resolvedOutput" in text


def test_create_tool_authenticates_all_frames_when_pg_restore_closes_early() -> None:
    text = _create_tool_text()

    assert "catch [System.IO.IOException]" in text
    assert "$restoreInputOpen = $false" in text
    assert "Unexpected bytes follow the authenticated backup terminator." in text
    assert "Encrypted archive validation failed" in text
    assert "The backup archive contains no restorable catalogue entries." in text


def test_restore_tool_requires_explicit_isolated_target_and_schema_version() -> None:
    text = _tool_text()

    assert "[Parameter(Mandatory = $true)][ValidatePattern('^0\\.[0-9]+$')]" in text
    assert "if (-not $ConfirmIsolatedTarget)" in text
    assert "^li_os_(restore|recovery|drill)_" in text
    assert "ExpectedSchemaVersion =" not in text


def test_restore_tool_reconstructs_authoritative_role_classes_without_passwords() -> None:
    text = _tool_text()

    for role in (
        "li_memory_function_owner",
        "li_memory_api",
        "li_memory_theo",
        "li_memory_owner_confirmation",
        "li_artifact_retention",
        "li_backend_runtime",
        "li_theo_runtime",
        "li_owner_runtime",
        "li_retention_runtime",
        "anon",
        "authenticated",
        "service_role",
    ):
        assert f"CREATE ROLE {role}" in text

    for membership in (
        "GRANT li_memory_api TO li_backend_runtime",
        "GRANT li_memory_theo TO li_theo_runtime",
        "GRANT li_memory_owner_confirmation TO li_owner_runtime",
        "GRANT li_artifact_retention TO li_retention_runtime",
    ):
        assert membership in text

    assert text.count("PASSWORD NULL") == 4
    assert "PASSWORD '" not in text
    assert "PASSWORD \"" not in text


def test_restore_tool_keeps_supabase_platform_objects_out_but_restores_li_authority() -> None:
    text = _tool_text()

    for schema in (
        "li_memory",
        "li_api",
        "li_conversation",
        "li_runtime_data",
        "li_tasks",
    ):
        assert f'"--schema", "{schema}"' in text

    assert '"--no-owner"' not in text
    assert '"--no-privileges"' not in text
    assert "Output is suppressed because it may contain restored data." in text


def test_migration_042_rehearsal_is_local_hash_pinned_and_non_destructive() -> None:
    text = _rehearse_042_tool_text()

    assert "-not $ConfirmDisposableTarget" in text
    assert "^li-os-migration-042-rehearsal-[a-z0-9-]+$" in text
    assert "^li_os_restore_pre042_[a-z0-9_]+$" in text
    assert "127.0.0.1:$Port`:5432" in text
    assert "supabase/postgres:17.6.1.136@sha256:" in text
    assert "--env 'POSTGRES_DB=postgres'" in text
    assert '"CREATE DATABASE $DatabaseName;"' in text
    assert '"GRANT CREATE ON DATABASE $DatabaseName TO postgres;' in text
    assert "The new disposable cluster has an unexpected database inventory" in text
    assert "DROP OWNED BY anon, authenticated, service_role;" in text
    assert "DROP ROLE anon, authenticated, service_role;" in text
    assert "dockerHost -notmatch '^(npipe:|unix:)'" in text
    assert "ExpectedSchemaVersion '0.41'" in text
    assert "ExpectedMigrationSha256" in text
    assert "Refusing to overwrite an existing global restore-password handoff variable" in text
    assert "Remove-Variable -Name $restorePasswordVariable -Scope Global" in text
    assert "MIGRATION_042_READY" in text
    assert "SET SESSION AUTHORIZATION li_backend_runtime" in text
    assert "ROLLBACK;" in text
    assert "docker rm" not in text
    assert "Remove-Item" not in text
    assert "Supabase database password" not in text


def test_migration_042_rehearsal_checks_every_denied_authority() -> None:
    text = _rehearse_042_tool_text()

    for role in (
        "li_memory_theo",
        "li_memory_owner_confirmation",
        "li_owner_runtime",
        "li_artifact_retention",
        "li_retention_runtime",
        "anon",
        "authenticated",
        "service_role",
    ):
        assert role in text
    assert "Backend direct portfolio table read" in text
    assert "Protected canonical or conversation counts changed" in text
    assert text.count("NOT has_function_privilege(role_name,") == 3
