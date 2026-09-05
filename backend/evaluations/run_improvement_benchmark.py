"""Run the synthetic behavior scenarios referenced by the permanent benchmark manifest."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "backend" / "evaluations" / "improvement-benchmark-v1.json"


def main() -> int:
    benchmark = json.loads(MANIFEST.read_text(encoding="utf-8"))
    backend: list[str] = []
    frontend: list[str] = []
    for case in benchmark["scenarios"]:
        for selector in case["tests"]:
            if selector.startswith("../frontend/"):
                frontend.append(selector.removeprefix("../"))
            else:
                backend.append(selector)

    # These are the actual behavior tests, not a name/reference check. They use
    # synthetic fixtures and make no live model, cloud, migration, or paid calls.
    backend_result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
         *dict.fromkeys(backend)],
        cwd=ROOT / "backend", check=False,
    )
    if backend_result.returncode:
        return backend_result.returncode
    frontend_result = subprocess.run(
        ["node", "--test", *dict.fromkeys(frontend)],
        cwd=ROOT, check=False,
    )
    return frontend_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
