from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESTORE_TOOL = ROOT / "memory" / "backup-tools" / "restore-encrypted-backup.ps1"


def _tool_text() -> str:
    return RESTORE_TOOL.read_text(encoding="utf-8")


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
