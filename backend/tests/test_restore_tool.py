from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESTORE_TOOL = ROOT / "memory" / "backup-tools" / "restore-encrypted-backup.ps1"
CREATE_TOOL = ROOT / "memory" / "backup-tools" / "create-encrypted-backup.ps1"


def _tool_text() -> str:
    return RESTORE_TOOL.read_text(encoding="utf-8")


def _create_tool_text() -> str:
    return CREATE_TOOL.read_text(encoding="utf-8")


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
