"""No real provider, memory, cloud or action calls."""

import json
from types import SimpleNamespace

import pytest

from app import voice_evaluation as evaluation
from app.li_runtime import build_li_system_prompt


def plan():
    return {
        "commits": {"baseline": "old", "candidate": "new"},
        "prompts": {"baseline": "old prompt", "candidate": "new prompt"},
        "scenarios": [{"id": "SV01", "context": "Fictional context", "assess": "RUBRIC",
                       "turns": ["Hej", "Tack"]}],
        "repeats": 3, "max_calls": 12,
    }


def test_documented_cases_are_complete_and_preserve_swedish():
    cases = evaluation.scenarios(evaluation.SCENARIOS.read_text(encoding="utf-8"))
    assert len(cases) == 20
    assert cases[1]["turns"][0] == "Tåget blev inställt så jag missade middagen."
    assert next(c for c in cases if c["id"] == "EN06")["context"].startswith("Earlier user context:")
    with pytest.raises(ValueError):
        evaluation.scenarios("| SV01 | malformed | nope |")


def test_current_extracted_prompt_matches_real_builder():
    # Reading Git is offline and never executes code from the historical revision.
    assert evaluation.core_prompt(evaluation.revision("HEAD")) == build_li_system_prompt()


@pytest.mark.parametrize("ref", ["--help", "HEAD~1", "main; echo secret", ""])
def test_reject_unsafe_or_unsupported_refs(ref):
    with pytest.raises(ValueError):
        evaluation.revision(ref)


def test_dry_run_never_initializes_provider(monkeypatch, capsys):
    monkeypatch.setattr(evaluation, "make_plan", lambda *a: plan())
    monkeypatch.setattr(evaluation, "provider", lambda: pytest.fail("Provider reached"))
    assert evaluation.main(["--baseline", "old"]) == 0
    assert "Dry run only" in capsys.readouterr().out


def test_budget_blocks_before_provider(monkeypatch):
    monkeypatch.setattr(evaluation, "make_plan", lambda *a: plan())
    monkeypatch.setattr(evaluation, "provider", lambda: pytest.fail("Provider reached"))
    assert evaluation.main(["--baseline", "old", "--live", "--max-calls", "1"]) == 1


def test_no_production_key_fallback(monkeypatch):
    monkeypatch.delenv("LI_OS_EVAL_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LI_OS_ANTHROPIC_API_KEY", "synthetic-unused")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-unused")
    with pytest.raises(ValueError, match="test-only"):
        evaluation.provider()


@pytest.mark.parametrize("stop_reason", ["end_turn", "max_tokens"])
def test_provider_adapter_is_bounded_and_rejects_truncation(monkeypatch, stop_reason):
    import anthropic

    monkeypatch.setenv("LI_OS_EVAL_ANTHROPIC_API_KEY", "synthetic-test-key")

    def create(**kwargs):
        assert kwargs["model"] == "verified-test-model"
        assert kwargs["max_tokens"] == 512
        assert "tools" not in kwargs
        return SimpleNamespace(stop_reason=stop_reason,
                               content=[SimpleNamespace(type="text", text="Hej")],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=2))

    def client(**kwargs):
        assert kwargs == {"api_key": "synthetic-test-key", "max_retries": 0,
                          "timeout": 60, "base_url": "https://api.anthropic.com"}
        return SimpleNamespace(messages=SimpleNamespace(create=create))

    monkeypatch.setattr(anthropic, "Anthropic", client)
    generate = evaluation.provider()
    if stop_reason == "end_turn":
        generated = generate("test system", "test turn", "verified-test-model", 512)
        assert generated["text"] == "Hej"
        assert generated["telemetry"]["input_tokens"] == 10
        assert generated["telemetry"]["output_tokens"] == 2
    else:
        with pytest.raises(ValueError, match="Incomplete"):
            generate("test system", "test turn", "verified-test-model", 512)


def test_history_blinding_and_no_automatic_scores(tmp_path):
    calls = []

    def fake(system, turn, model, max_tokens):
        calls.append((system, turn))
        assert "RUBRIC" not in system
        assert model == "test-model"
        assert max_tokens == 2048
        if turn == "Tack":
            assert '"li": "Svar på Hej"' in system
        else:
            assert "Recent conversation" not in system
        return "Svar på " + turn

    output = tmp_path / "run"
    evaluation.execute(plan(), fake, output, "test-model", 2048)
    assert len(calls) == 12
    records = [json.loads(line) for line in (output / "review.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == 6
    assert {r["id"] for r in records} == {f"SV01-{n}-{v}" for n in range(1, 4) for v in "AB"}
    for record in records:
        assert "variant" not in record
        assert record["status"] == "generated_unreviewed"
        assert all(value is None for value in record["scores"].values())
        assert all(value is None for value in record["gates"].values())
        assert len(record["call_telemetry"]) == 2
        assert all(call["usage_available"] is False for call in record["call_telemetry"])
    assert not json.loads((output / "completion.json").read_text())["release_approved"]
    with pytest.raises(FileExistsError):
        evaluation.execute(plan(), fake, output, "test-model", 2048)


def test_failure_redacts_exceptions_and_preserves_partial_run(tmp_path):
    def failure(*args):
        raise ValueError("synthetic-sensitive-exception")

    output = tmp_path / "failure"
    with pytest.raises(RuntimeError, match="partial review"):
        evaluation.execute(plan(), failure, output, "test-model", 2048)
    text = (output / "review.jsonl").read_text(encoding="utf-8")
    assert "synthetic-sensitive-exception" not in text
    assert json.loads(text)["status"] == "provider_failed"
    assert not (output / "completion.json").exists()


def test_output_cannot_enter_repository():
    with pytest.raises(ValueError, match="outside the repository"):
        evaluation.execute(plan(), lambda *a: pytest.fail("Provider reached"),
                           evaluation.ROOT / "output/evaluation", "test-model", 2048)
