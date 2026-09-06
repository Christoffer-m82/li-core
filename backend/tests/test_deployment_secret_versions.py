from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "deployment" / "cloud-run"


def test_deployable_assets_never_use_mutable_latest_references() -> None:
    deployable_assets = [
        *DEPLOYMENT.glob("*.yaml"),
        *DEPLOYMENT.glob("*.yml"),
        *DEPLOYMENT.glob("*.ps1"),
    ]

    findings = []
    for path in sorted(deployable_assets):
        text = path.read_text(encoding="utf-8")
        if ":latest" in text or "key: latest" in text:
            findings.append(path.relative_to(ROOT).as_posix())

    assert findings == []


def test_secret_templates_require_explicit_pinned_version_placeholders() -> None:
    expected_placeholders = {
        "web-service.template.yaml": {
            "PINNED_LI_OS_API_TOKEN_VERSION",
            "PINNED_LI_OS_OWNER_API_TOKEN_VERSION",
            "PINNED_LI_WEB_SESSION_SECRET_VERSION",
            "PINNED_LI_WEB_GOOGLE_CLIENT_ID_VERSION",
            "PINNED_LI_WEB_GOOGLE_CLIENT_SECRET_VERSION",
        },
        "retention-job.template.yaml": {
            "PINNED_LI_RETENTION_DB_HOST_VERSION",
            "PINNED_LI_RETENTION_DB_USER_VERSION",
            "PINNED_LI_RETENTION_DB_PASSWORD_VERSION",
        },
        "native-gateway-service.template.yaml": {
            "PINNED_NATIVE_API_TOKEN_VERSION",
            "PINNED_SIGNING_KEY_VERSION",
        },
        "service.template.yaml": {
            "PINNED_NATIVE_API_TOKEN_VERSION",
        },
    }

    for filename, placeholders in expected_placeholders.items():
        text = (DEPLOYMENT / filename).read_text(encoding="utf-8")
        for placeholder in placeholders:
            assert placeholder in text


def test_provisioning_scripts_reject_non_numeric_secret_versions() -> None:
    numeric_version_validation = "[ValidatePattern('^[1-9][0-9]*$')]"

    retention = (DEPLOYMENT / "provision-retention.ps1").read_text(encoding="utf-8")
    assert retention.count(numeric_version_validation) == 3
    for parameter in (
        "$DbHostSecretVersion",
        "$DbUserSecretVersion",
        "$DbPasswordSecretVersion",
    ):
        assert parameter in retention

    gateway = (DEPLOYMENT / "provision-native-gateway.ps1").read_text(encoding="utf-8")
    assert gateway.count(numeric_version_validation) == 2
