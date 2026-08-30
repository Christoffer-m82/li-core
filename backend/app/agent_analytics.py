"""Measured specialist analytics and conservative relevance recommendations."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

PERIOD_DAYS = {"30d": 30, "90d": 90, "6m": 183, "12m": 365, "all": None}


def period_bounds(period: str, now: datetime | None = None) -> tuple[datetime | None, datetime, datetime | None]:
    if period not in PERIOD_DAYS:
        raise ValueError("Unsupported analytics period")
    end = now or datetime.now(UTC)
    days = PERIOD_DAYS[period]
    if days is None:
        return None, end, None
    start = end - timedelta(days=days)
    return start, end, start - timedelta(days=days)


def _duration(event: dict[str, Any]) -> float | None:
    start, end = event.get("started_at"), event.get("completed_at")
    if not start or not end:
        return None
    return max(0.0, (end - start).total_seconds())


def calculate_analytics(
    roster: Iterable[dict[str, Any]], events: list[dict[str, Any]], period: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    roster = list(roster)
    start, end, previous_start = period_bounds(period, now)
    current = [e for e in events if e["started_at"] <= end and (start is None or e["started_at"] >= start)]
    previous = [] if start is None else [e for e in events if previous_start <= e["started_at"] < start]
    total_requests = len({e["request_id"] for e in current})
    total_agent_calls = len(current)
    total_workload = sum(value for value in (_duration(event) for event in current) if value is not None)
    request_sizes = Counter(e["request_id"] for e in current)
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    previous_counts = Counter(e["specialist_key"] for e in previous)
    for event in current:
        by_agent[event["specialist_key"]].append(event)

    agents = []
    for profile in roster:
        key = profile["id"]
        rows = by_agent[key]
        durations = [value for value in (_duration(row) for row in rows) if value is not None]
        multi = sum(request_sizes[row["request_id"]] > 1 for row in rows)
        explicit = sum(bool(row.get("explicit_request")) for row in rows)
        measured_contributions = [
            bool(row["used_in_final"])
            for row in rows if row.get("used_in_final") is not None
        ]
        contribution = sum(measured_contributions)
        measured_actions = [
            bool(row["action_taken"])
            for row in rows
            if row.get("used_in_final") is True and row.get("action_taken") is not None
        ]
        actions = sum(measured_actions)
        topics = Counter(topic for row in rows for topic in row.get("topic_keys", []))
        previous_count = previous_counts[key]
        overlap_peers = {other["specialist_key"] for row in rows for other in current
                         if other["request_id"] == row["request_id"] and other["specialist_key"] != key}
        agents.append({**profile, "state": profile.get("state", "idle"),
            "active": any(row["status"] == "active" for row in rows),
            "last_used": max((row["started_at"] for row in rows), default=None),
            "request_count": len(rows), "active_days": len({row["started_at"].date() for row in rows}),
            "usage_share_pct": round(100 * len(rows) / total_agent_calls, 1) if total_agent_calls else 0.0,
            "workload_share_pct": round(100 * sum(durations) / total_workload, 1) if total_workload else None,
            "total_workload_seconds": round(sum(durations), 2),
            "average_workload_seconds": round(sum(durations) / len(durations), 2) if durations else None,
            "average_response_seconds": round(sum(durations) / len(durations), 2) if durations else None,
            "solo_usage": len(rows) - multi, "multi_agent_usage": multi,
            "explicit_user_usage": explicit, "li_selected_usage": len(rows) - explicit,
            "recommendation_contribution_rate": (
                round(contribution / len(measured_contributions), 3)
                if measured_contributions else None
            ),
            "action_conversion_rate": (
                round(actions / len(measured_actions), 3)
                if measured_actions else None
            ),
            "recurring_topic_count": sum(count >= 2 for count in topics.values()),
            "recurring_topics": [{"topic": topic, "count": count} for topic, count in topics.most_common(5) if count >= 2],
            "overlap_score": round(len(overlap_peers) / max(1, len(roster) - 1), 3),
            "trend_pct": None if previous_count == 0 else round(100 * (len(rows) - previous_count) / previous_count, 1),
            "recent_activity": sorted(rows, key=lambda row: row["started_at"], reverse=True)[:3],
            "derived_metrics": {"impact_score": {"value": (
                round(100 * contribution / len(measured_contributions), 1)
                if measured_contributions else None
            ),
                "label": "inferred", "basis": "validated outputs marked as used in Li's final answer"},
                "depth_score": {"value": None, "label": "not_available", "basis": "no reliable depth signal"},
                "uniqueness_score": {"value": round(100 * (1 - len(overlap_peers) / max(1, len(roster) - 1)), 1),
                    "label": "inferred", "basis": "inverse co-use overlap"},
                "dependency_score": {"value": round(100 * multi / len(rows), 1) if rows else None,
                    "label": "inferred", "basis": "share of calls used in multi-agent requests"},
                "user_value_score": {"value": None, "label": "not_available", "basis": "no explicit owner feedback signal"}}})
    return {"period": period, "period_start": start, "period_end": end,
            "total_requests": total_requests, "total_agent_calls": total_agent_calls, "agents": agents}


def generate_recommendations(analytics: dict[str, Any]) -> list[dict[str, Any]]:
    recommendations = []
    for agent in analytics["agents"]:
        if agent["request_count"] == 0:
            action, reason = "keep", "No usage was recorded in this period; more evidence is needed before a permanent change."
        elif agent["overlap_score"] >= 0.6 and agent["request_count"] >= 5:
            action, reason = "merge", "Frequent multi-agent co-use indicates material overlap; review boundaries before merging."
        else:
            action, reason = "keep", f"Used {agent['request_count']} times with {agent['usage_share_pct']}% of specialist calls."
        recommendations.append({"subject_agent": agent["id"], "action": action, "rationale": reason,
            "requires_owner_approval": True, "execution_status": "pending_approval"})
        for topic in agent["recurring_topics"]:
            if topic["count"] >= 3 and agent["request_count"] >= 8:
                recommendations.append({"subject_agent": f"new:{topic['topic']}", "action": "create",
                    "rationale": f"The uncovered topic '{topic['topic']}' recurred {topic['count']} times within an overloaded {agent['name']} workload; review whether a dedicated boundary is warranted.",
                    "requires_owner_approval": True, "execution_status": "pending_approval"})
    return recommendations
