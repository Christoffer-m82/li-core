from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

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


@pytest.mark.parametrize("observed", ["0.41", "unexpected", None])
def test_trial_rejects_database_not_matching_manifest(monkeypatch, observed):
    from acceptance.run_provider_trial import verify_trial_schema
    monkeypatch.setattr("app.database.database_health", lambda: {"schema_version": observed})
    with pytest.raises(TrialStopped, match="^runtime_database_health_failed$"):
        verify_trial_schema()


def test_trial_accepts_current_manifest_schema(monkeypatch):
    import json
    from acceptance.run_provider_trial import ROOT, verify_trial_schema
    manifest = json.loads((ROOT / "memory/migrations/manifest.json").read_text())
    expected = manifest["migrations"][-1]["logical_version"]
    monkeypatch.setattr("app.database.database_health", lambda: {"schema_version": expected})
    assert verify_trial_schema() == expected


@pytest.mark.parametrize("language", ["en", "sv"])
def test_correction_statement_is_not_exact_marker_and_remains_unproven(language):
    from acceptance.provider_trial import correction_observations
    marker = "synthetic-new-" + language
    statement = ("Prefers notebooks labelled " if language == "en" else
                 "Föredrar anteckningsböcker märkta ") + marker
    flags = correction_observations([
        {"value_text": statement, "source_reference": "turn:synthetic-identity"}],
        marker, "synthetic-identity")
    assert flags == {"exact_value_unique": False, "marker_present": True,
                     "current_turn_source_present": True}


@pytest.mark.parametrize("count", [0, 1, 2])
def test_correction_observation_preserves_unique_exact_requirement(count):
    from acceptance.provider_trial import correction_observations
    rows = [{"value_text": "synthetic-new", "source_reference": "another-turn"}] * count
    flags = correction_observations(rows, "synthetic-new", "this-turn")
    assert flags["exact_value_unique"] is (count == 1)
    assert flags["current_turn_source_present"] is False


@pytest.mark.parametrize("actions,expected", [
    ([], {
        "classifier_no_candidates": True,
        "classifier_exactly_one_correction_candidate": False,
        "classifier_multiple_correction_candidates": False,
        "classifier_other_action_present": False,
        "classifier_correction_fields_complete": False,
    }),
    (["correct_explicit"], {
        "classifier_no_candidates": False,
        "classifier_exactly_one_correction_candidate": True,
        "classifier_multiple_correction_candidates": False,
        "classifier_other_action_present": False,
        "classifier_correction_fields_complete": True,
    }),
    (["correct_explicit", "correct_explicit"], {
        "classifier_no_candidates": False,
        "classifier_exactly_one_correction_candidate": False,
        "classifier_multiple_correction_candidates": True,
        "classifier_other_action_present": False,
        "classifier_correction_fields_complete": False,
    }),
    (["store_explicit"], {
        "classifier_no_candidates": False,
        "classifier_exactly_one_correction_candidate": False,
        "classifier_multiple_correction_candidates": False,
        "classifier_other_action_present": True,
        "classifier_correction_fields_complete": False,
    }),
    (["correct_explicit", "ignore"], {
        "classifier_no_candidates": False,
        "classifier_exactly_one_correction_candidate": True,
        "classifier_multiple_correction_candidates": False,
        "classifier_other_action_present": True,
        "classifier_correction_fields_complete": True,
    }),
])
def test_classifier_observations_are_content_free(actions, expected):
    from acceptance.provider_trial import classifier_observations
    candidates = [SimpleNamespace(action=action, target_query="private target",
                                  value="private replacement") for action in actions]
    flags = classifier_observations(SimpleNamespace(candidates=candidates))
    assert flags == {
        "classifier_analysis_completed": True,
        "classifier_analysis_failed": False,
        **expected,
    }
    assert "private" not in repr(flags)


@pytest.mark.parametrize("target_query,value", [(None, "new"), ("target", None), (" ", "new"),
                                                   ("target", " ")])
def test_classifier_observations_require_complete_correction_fields(target_query, value):
    from acceptance.provider_trial import classifier_observations
    analysis = SimpleNamespace(candidates=[SimpleNamespace(
        action="correct_explicit", target_query=target_query, value=value)])
    assert classifier_observations(analysis)["classifier_correction_fields_complete"] is False


def test_recovery_pipeline_observations_start_content_free_and_false():
    from acceptance.provider_trial import recovery_pipeline_observations
    flags = recovery_pipeline_observations()
    assert flags and all(type(value) is bool and value is False for value in flags.values())


def test_checkpoint_is_durable_and_contains_only_safe_booleans(budget, tmp_path):
    import json
    budget.checkpoint("sv", "recovery_precondition", {"exact_value_unique": False})
    events = [json.loads(line) for line in (tmp_path / "journal.jsonl").read_text().splitlines()]
    assert events[-1] == {"event": "checkpoint", "language": "sv",
                          "case": "recovery_precondition", "flags": {"exact_value_unique": False}}


@pytest.mark.parametrize("case,flag", [
    ("recovery_classifier", "classifier_analysis_completed"),
    ("recovery_apply", "target_resolution_failed"),
    ("recovery_pipeline", "correction_dispatch_started"),
])
def test_content_free_recovery_checkpoints_are_allowed(budget, tmp_path, case, flag):
    import json
    budget.checkpoint("en", case, {flag: False})
    event = json.loads((tmp_path / "journal.jsonl").read_text().splitlines()[-1])
    assert event == {"event": "checkpoint", "language": "en", "case": case,
                     "flags": {flag: False}}


def test_checkpoint_rejects_allowlisted_flag_in_wrong_case(budget):
    with pytest.raises(TrialStopped, match="trial_checkpoint_not_allowed"):
        budget.checkpoint("en", "privacy", {"correction_dispatch_started": False})


@pytest.mark.parametrize("language,case,flags", [
    ("raw content", "privacy", {"marker_present": True}),
    ("en", "raw content", {"marker_present": True}),
    ("en", "privacy", {"raw content": True}),
    ("en", "privacy", {"marker_present": "raw content"}),
    ("en", "privacy", {"marker_present": 1}),
])
def test_checkpoint_rejects_arbitrary_diagnostics(budget, tmp_path, language, case, flags):
    with pytest.raises(TrialStopped, match="trial_checkpoint_not_allowed"):
        budget.checkpoint(language, case, flags)
    assert "raw content" not in (tmp_path / "journal.jsonl").read_text()


@pytest.fixture
def correction_proof():
    source = "li-chat:synthetic-conversation:synthetic-turn"
    value = "Prefers notebooks labelled synthetic-new"
    arguments = {"memory_id": "seed", "new_value": value, "source_reference": source}
    result = {"previous_memory_id": "seed", "memory_id": "replacement",
              "outcome": "created_replacement"}
    row = {"memory_id": "replacement", "value_text": value, "source_reference": source,
           "memory_class": "explicit_preference", "truth_status": "confirmed",
           "temporal_status": "current", "domain": "notebooks"}
    return [row], [(arguments, result)]


@pytest.mark.parametrize("value", ["synthetic-new", "Prefers synthetic-new notebooks",
                                   "Föredrar anteckningsböcker märkta synthetic-new"])
def test_governed_correction_proof_accepts_preserved_statement(correction_proof, value):
    from acceptance.provider_trial import verified_correction
    rows, receipts = correction_proof
    rows[0]["value_text"] = receipts[0][0]["new_value"] = value
    assert verified_correction(rows, receipts, "seed", "synthetic-new", "synthetic-old",
                               "synthetic-turn") is rows[0]


@pytest.mark.parametrize("target,key,value", [
    ("arguments", "memory_id", "wrong-seed"),
    ("arguments", "source_reference", "li-chat:synthetic-conversation:wrong-turn"),
    ("arguments", "new_value", "synthetic-old instead of synthetic-new"),
    ("arguments", "new_value", "unrelated preference"),
    ("result", "previous_memory_id", "wrong-seed"),
    ("result", "memory_id", "seed"),
    ("result", "outcome", "no_change"),
    ("row", "memory_id", "unrelated-record"),
    ("row", "value_text", "different stored content"),
    ("row", "source_reference", "wrong-source"),
    ("row", "truth_status", "outdated"),
    ("row", "temporal_status", "historical"),
    ("row", "memory_class", "explicit_fact"),
])
def test_governed_correction_proof_rejects_false_positive(correction_proof, target, key, value):
    from acceptance.provider_trial import verified_correction
    rows, receipts = correction_proof
    {"arguments": receipts[0][0], "result": receipts[0][1], "row": rows[0]}[target][key] = value
    with pytest.raises(TrialStopped):
        verified_correction(rows, receipts, "seed", "synthetic-new", "synthetic-old", "synthetic-turn")


@pytest.mark.parametrize("row_count,receipt_count", [(0, 1), (2, 1), (1, 0), (1, 2)])
def test_governed_correction_proof_requires_unique_write_and_row(correction_proof, row_count, receipt_count):
    from acceptance.provider_trial import verified_correction
    rows, receipts = correction_proof
    with pytest.raises(TrialStopped):
        verified_correction(rows * row_count, receipts * receipt_count,
                            "seed", "synthetic-new", "synthetic-old", "synthetic-turn")


@pytest.fixture
def separate_trial(tmp_path, monkeypatch):
    import hashlib
    from acceptance import run_provider_trial as runner
    old = tmp_path / "original.jsonl"
    old.write_bytes(b'{"event":"synthetic-predecessor"}\n')
    new = tmp_path / "new.jsonl"
    monkeypatch.setattr(runner, "JOURNAL", old)
    monkeypatch.setattr(runner, "PR104_JOURNAL", new)
    monkeypatch.setattr(runner, "PREDECESSOR_SHA256", hashlib.sha256(old.read_bytes()).hexdigest())
    return runner, old, new


def test_separate_authorized_trial_preserves_and_links_predecessor(separate_trial):
    import json
    runner, old, new = separate_trial
    before = old.read_bytes()
    path, digest = runner.trial_journal(True, True)
    assert path == new and digest == runner.PREDECESSOR_SHA256
    trial = TrialBudget(path, predecessor_sha256=digest)
    trial.close()
    event = json.loads(new.read_text())
    assert event["predecessor_sha256"] == digest
    assert event["predecessor_ledger"] == "kr011-provider-20260907.jsonl"
    assert event["reviewed_pr"] == 104
    assert event["max_calls"] == 16 and event["max_turns"] == 4
    assert event["max_micro_usd"] == 500_000
    assert old.read_bytes() == before
    with pytest.raises(TrialStopped, match="trial_ledger_already_exists_reconcile_only"):
        runner.trial_journal(True, True)


def test_old_live_command_remains_blocked(separate_trial):
    runner, _, new = separate_trial
    with pytest.raises(TrialStopped, match="trial_ledger_already_exists_reconcile_only"):
        runner.trial_journal(True, False)
    assert not new.exists()


@pytest.mark.parametrize("missing", [False, True])
def test_separate_trial_requires_unchanged_original(separate_trial, missing):
    runner, old, new = separate_trial
    if missing:
        old.unlink()
    else:
        old.write_bytes(b"changed synthetic fixture")
    with pytest.raises(TrialStopped, match="preserved_predecessor"):
        runner.trial_journal(True, True)
    assert not new.exists()


def test_separate_fake_rehearsal_does_not_consume_live_ledger(separate_trial):
    runner, old, new = separate_trial
    before = old.read_bytes()
    path, digest = runner.trial_journal(False, True)
    assert path not in {old, new} and "dry" in path.name
    assert digest == runner.PREDECESSOR_SHA256
    assert old.read_bytes() == before and not new.exists()


def test_exclusive_creation_rejects_racing_ledger(separate_trial):
    runner, _, new = separate_trial
    path, digest = runner.trial_journal(True, True)
    new.write_bytes(b"another process owns this synthetic fixture")
    before = new.read_bytes()
    with pytest.raises(FileExistsError):
        TrialBudget(path, predecessor_sha256=digest)
    assert new.read_bytes() == before


@pytest.mark.parametrize("invalid", ["raw provider text", "", "a" * 63, 123])
def test_predecessor_provenance_rejects_non_hash(tmp_path, invalid):
    path = tmp_path / "new.jsonl"
    with pytest.raises(TrialStopped, match="trial_predecessor_hash_invalid"):
        TrialBudget(path, predecessor_sha256=invalid)
    assert not path.exists()


@pytest.mark.parametrize("changed", [False, True])
def test_key_entry_attempt_preserves_both_ledgers(separate_trial, monkeypatch, changed):
    import hashlib
    import json
    runner, old, stopped = separate_trial
    stopped.write_bytes(b'{"event":"created"}\n')
    old_before, stopped_before = old.read_bytes(), stopped.read_bytes()
    monkeypatch.setattr(runner, "PRE_DISPATCH_SHA256", hashlib.sha256(stopped_before).hexdigest())
    new = old.with_name("third.jsonl")
    monkeypatch.setattr(runner, "KEY_ENTRY_JOURNAL", new)
    if changed:
        stopped.write_bytes(b"changed fixture")
        with pytest.raises(TrialStopped, match="preserved_pre_dispatch_ledger_required"):
            runner.trial_journal(True, False, True)
        assert not new.exists()
        return
    path, digest = runner.trial_journal(True, False, True)
    trial = TrialBudget(path, predecessor_sha256=digest,
                        pre_dispatch_sha256=runner.PRE_DISPATCH_SHA256)
    trial.close()
    event = json.loads(new.read_text())
    assert event["pre_dispatch_sha256"] == runner.PRE_DISPATCH_SHA256
    assert old.read_bytes() == old_before and stopped.read_bytes() == stopped_before
    with pytest.raises(TrialStopped, match="trial_ledger_already_exists"):
        runner.trial_journal(True, False, True)
    with pytest.raises(TrialStopped, match="select_one_authorized_batch_only"):
        runner.trial_journal(True, True, True)
