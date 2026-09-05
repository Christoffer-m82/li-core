import json
import re
from pathlib import Path


ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "backend" / "evaluations" / "improvement-benchmark-v1.json"


def test_permanent_improvement_benchmark_maps_all_synthetic_scenarios_to_existing_tests():
    benchmark = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert benchmark["schema"] == "li_improvement_benchmark_v1"
    assert benchmark["fixture_policy"] == "synthetic_only"
    assert benchmark["content_logging"] is False
    assert benchmark["live_provider_required"] is False
    assert {case["id"] for case in benchmark["scenarios"]} == {
        f"R{number}" for number in range(1, 15)
    }
    for case in benchmark["scenarios"]:
        assert case["tests"]
        for selector in case["tests"]:
            relative, _, test_name = selector.partition("::")
            path = (ROOT / "backend" / relative).resolve()
            assert path.is_relative_to(ROOT) and path.exists(), selector
            if test_name:
                source = path.read_text(encoding="utf-8")
                assert re.search(rf"^def {re.escape(test_name)}\(", source, re.MULTILINE), selector
