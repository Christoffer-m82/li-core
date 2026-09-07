from concurrent.futures import ThreadPoolExecutor

import pytest

from acceptance.trial_budget import MODEL, TrialBudget, TrialStopped, reservation


def request(**changes):
    return dict(model=MODEL, max_tokens=128,
                messages=[{"role": "user", "content": "synthetic åäö"}], **changes)


@pytest.fixture
def budget(tmp_path):
    trial = TrialBudget(tmp_path / "journal.jsonl")
    trial.turn("synthetic-turn")
    yield trial
    trial.close()


@pytest.mark.parametrize("change", [
    {"model": "another-model"}, {"max_tokens": 4096}, {"max_tokens": True},
    {"tools": []}, {"thinking": {"type": "enabled"}}, {"stream": True},
    {"cache_control": {}}, {"system": [{"text": "block"}]},
    {"messages": [{"role": "user", "content": [{"type": "image"}]}]},
    {"messages": [{"role": "user", "content": "x" * 100_001}]},
    {"output_config": {"effort": "high"}},
])
def test_nonstandard_requests_never_reserve(budget, change):
    with pytest.raises(TrialStopped):
        budget.reserve(request() | change)
    assert not budget.calls


def test_utf8_and_schema_are_included():
    base = reservation(request())[0]
    assert reservation(request(system="å" * 100))[0] >= base + 200
    assert reservation(request(output_config={"format": {
        "type": "json_schema", "schema": {"description": "x" * 100}}}))[0] > base + 100


def test_concurrent_reservations_cannot_overspend(budget):
    def reserve(_):
        try:
            return budget.reserve(request())
        except TrialStopped:
            return None
    with ThreadPoolExecutor(max_workers=16) as pool:
        tickets = list(pool.map(reserve, range(30)))
    assert 0 < sum(t is not None for t in tickets) < 16
    assert budget.charged_bound <= 500_000


def test_call_limit_survives_successful_low_usage(budget):
    for _ in range(16):
        ticket = budget.reserve(request())
        budget.settle(ticket, {"input_tokens": 10, "output_tokens": 2})
    with pytest.raises(TrialStopped):
        budget.reserve(request())


def test_unknown_outcome_keeps_reservation_and_stops(budget):
    budget.reserve(request())
    before = budget.charged_bound
    budget.fail()
    assert budget.charged_bound == before > 0
    with pytest.raises(TrialStopped):
        budget.reserve(request())


@pytest.mark.parametrize("usage", [
    {}, {"input_tokens": -1, "output_tokens": 1},
    {"input_tokens": True, "output_tokens": 1},
    {"input_tokens": 1, "output_tokens": 9999},
    {"input_tokens": 999_999, "output_tokens": 1},
    {"input_tokens": 1, "output_tokens": 1, "cache_creation_input_tokens": 100},
])
def test_bad_usage_requires_reconciliation(budget, usage):
    ticket = budget.reserve(request())
    before = budget.charged_bound
    with pytest.raises(TrialStopped):
        budget.settle(ticket, usage)
    assert budget.stopped and budget.charged_bound == before


def test_four_turns_and_only_exact_replays(budget):
    for i in range(3):
        budget.turn(str(i))
    budget.turn("synthetic-turn", replay=True)
    with pytest.raises(TrialStopped):
        budget.reserve(request())
    with pytest.raises(TrialStopped):
        budget.turn("fifth")
    with pytest.raises(TrialStopped):
        budget.turn("new-replay", replay=True)


def test_existing_journal_cannot_reset_trial(tmp_path):
    path = tmp_path / "journal.jsonl"
    trial = TrialBudget(path)
    trial.close()
    with pytest.raises(FileExistsError):
        TrialBudget(path)


def test_write_failure_prevents_dispatch(budget, monkeypatch):
    def fail(_):
        raise OSError("synthetic disk full")
    monkeypatch.setattr("acceptance.trial_budget.os.fsync", fail)
    with pytest.raises(TrialStopped, match="trial_journal_failed"):
        budget.reserve(request())
    assert budget.stopped and not budget.calls


def test_guarded_messages_redacts_sdk_failure_and_never_retries(budget):
    from types import SimpleNamespace
    from acceptance.provider_trial import GuardedMessages
    calls = []
    def fail(**kwargs):
        calls.append(1)
        raise RuntimeError("sensitive provider packet must not surface")
    guarded = GuardedMessages(budget, SimpleNamespace(create=fail))
    with pytest.raises(TrialStopped, match="^provider_trial_call_failed$") as error:
        guarded.create(**request())
    assert error.value.__suppress_context__ and len(calls) == 1
    assert budget.charged_bound > 0 and budget.stopped
    with pytest.raises(TrialStopped):
        guarded.create(**request())
    assert len(calls) == 1


def test_guarded_messages_settles_usage_without_content_in_journal(budget, tmp_path):
    from types import SimpleNamespace
    from acceptance.provider_trial import GuardedMessages
    response = SimpleNamespace(usage=SimpleNamespace(model_dump=lambda: {
        "input_tokens": 12, "output_tokens": 3}))
    guarded = GuardedMessages(budget, SimpleNamespace(create=lambda **kwargs: response))
    assert guarded.create(**request()) is response
    assert budget.charged_bound == 81
    assert "synthetic åäö" not in (tmp_path / "journal.jsonl").read_text()


def test_child_environment_excludes_external_configuration(monkeypatch):
    from acceptance.run_provider_trial import isolated_environment
    for key in ("LI_OS_DB_HOST", "LI_OS_ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL",
                "HTTPS_PROXY", "PGSERVICE", "PGPASSFILE", "GOOGLE_APPLICATION_CREDENTIALS",
                "DOCKER_HOST", "DOCKER_CONTEXT"):
        monkeypatch.setenv(key, "must-not-inherit")
    clean = isolated_environment()
    assert "must-not-inherit" not in clean.values()
    assert clean["PGHOST"] == "127.0.0.1"


def test_live_requires_fresh_coverage_before_local_resource_creation(monkeypatch):
    from acceptance.run_provider_trial import run
    monkeypatch.setattr("acceptance.run_provider_trial.command", lambda *a, **k: pytest.fail("blocked"))
    with pytest.raises(TrialStopped):
        run(True, None, None, False)


def test_coverage_expiry_blocks_even_after_private_prompt_delay(tmp_path, monkeypatch):
    monkeypatch.setattr("acceptance.trial_budget.time.time", lambda: 101)
    trial = TrialBudget(tmp_path / "expired.jsonl", expires_at=100)
    trial.turn("synthetic")
    try:
        with pytest.raises(TrialStopped, match="trial_coverage_expired"):
            trial.reserve(request())
        assert not trial.calls
    finally:
        trial.close()


def test_docker_uses_explicit_local_socket_not_remote_context(monkeypatch):
    from acceptance.run_provider_trial import docker_command
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.invalid:2376")
    monkeypatch.setenv("DOCKER_CONTEXT", "remote")
    seen = []
    monkeypatch.setattr("acceptance.run_provider_trial.command",
                        lambda args, env: seen.append((args, env)))
    docker_command("ps")
    args, env = seen[0]
    assert args[:2] == ["docker", "--host"]
    assert args[2].startswith(("npipe:", "unix:"))
    assert "DOCKER_HOST" not in env and "DOCKER_CONTEXT" not in env
