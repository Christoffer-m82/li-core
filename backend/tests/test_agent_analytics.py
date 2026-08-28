from datetime import UTC, datetime, timedelta

from app.agent_analytics import calculate_analytics, generate_recommendations, period_bounds

NOW = datetime(2026, 8, 28, tzinfo=UTC)
ROSTER = [{"id": "nora", "name": "Nora", "role": "Research"},
          {"id": "victor", "name": "Victor", "role": "Strategy"}]


def event(agent="nora", days=1, request="r1", seconds=10, **extra):
    started = NOW - timedelta(days=days)
    return {"specialist_key": agent, "request_id": request, "status": "completed",
            "started_at": started, "completed_at": started + timedelta(seconds=seconds),
            "topic_keys": [], **extra}


def test_period_comparison_and_measured_metrics():
    result = calculate_analytics(ROSTER, [event(), event(days=35, request="old")], "30d", NOW)
    nora = result["agents"][0]
    assert result["total_requests"] == 1
    assert nora["average_response_seconds"] == 10
    assert nora["trend_pct"] == 0
    assert nora["usage_share_pct"] == 100
    assert nora["workload_share_pct"] == 100


def test_solo_multi_explicit_and_contribution_metrics():
    rows = [event(request="shared", explicit_request=True, used_in_final=True, action_taken=True),
            event("victor", request="shared")]
    nora = calculate_analytics(ROSTER, rows, "30d", NOW)["agents"][0]
    assert (nora["solo_usage"], nora["multi_agent_usage"]) == (0, 1)
    assert (nora["explicit_user_usage"], nora["li_selected_usage"]) == (1, 0)
    assert nora["recommendation_contribution_rate"] == 1
    assert nora["action_conversion_rate"] == 1


def test_derived_metrics_are_labelled_and_missing_signals_are_honest():
    metrics = calculate_analytics(ROSTER, [], "all", NOW)["agents"][0]["derived_metrics"]
    assert metrics["impact_score"]["label"] == "inferred"
    assert metrics["depth_score"]["label"] == "not_available"
    assert metrics["user_value_score"]["value"] is None


def test_recommendations_are_approval_gated():
    recs = generate_recommendations(calculate_analytics(ROSTER, [], "90d", NOW))
    assert all(item["requires_owner_approval"] for item in recs)
    assert all(item["execution_status"] == "pending_approval" for item in recs)


def test_supported_periods_and_invalid_period():
    assert period_bounds("6m", NOW)[0] == NOW - timedelta(days=183)
    try:
        period_bounds("weekly", NOW)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid periods must fail")


def test_paused_and_archived_states_are_preserved():
    roster = [dict(ROSTER[0], state="paused"), dict(ROSTER[1], state="archived")]
    agents = calculate_analytics(roster, [], "all", NOW)["agents"]
    assert [agent["state"] for agent in agents] == ["paused", "archived"]


def test_repeated_topic_can_propose_new_agent_without_executing():
    rows = [event(request=f"r{i}", topic_keys=["tax"]) for i in range(8)]
    recs = generate_recommendations(calculate_analytics(ROSTER, rows, "30d", NOW))
    proposal = next(item for item in recs if item["action"] == "create")
    assert proposal["subject_agent"] == "new:tax"
    assert proposal["execution_status"] == "pending_approval"
