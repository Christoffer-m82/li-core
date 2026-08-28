from pathlib import Path


def test_dockerfile_packages_required_li_runtime_files() -> None:
    dockerfile = Path(__file__).resolve().parents[1] / "Dockerfile"
    contents = dockerfile.read_text(encoding="utf-8")

    assert "COPY CONSTITUTION.md /CONSTITUTION.md" in contents
    assert "COPY li /li" in contents
    assert "COPY agents /agents" in contents
