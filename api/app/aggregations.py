from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from .hygiene import calculate_company_hygiene_score, top_issue_title


def _rate(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _round_money(value: float) -> float:
    return round(value, 6)


def build_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    total_events = len(events)
    total_cost = sum(float(event.get("total_cost") or 0.0) for event in events)
    total_tokens = sum(int(event.get("total_tokens") or 0) for event in events)
    total_input_tokens = sum(int(event.get("input_tokens") or 0) for event in events)
    total_cached_tokens = sum(int(event.get("cached_tokens") or 0) for event in events)
    latency_values = [int(event.get("latency_ms") or 0) for event in events if event.get("latency_ms") is not None]
    active_users = {event.get("user_id") for event in events if event.get("user_id")}

    return {
        "total_events": total_events,
        "total_cost": _round_money(total_cost),
        "total_tokens": total_tokens,
        "cache_hit_rate": round(_rate(total_cached_tokens, total_input_tokens), 4),
        "avg_latency_ms": round(mean(latency_values), 2) if latency_values else 0,
        "active_users": len(active_users),
        "hygiene_score": calculate_company_hygiene_score(events),
    }


def build_developer_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[event.get("user_id") or "unknown"].append(event)

    rows = []
    for user_id, user_events in grouped.items():
        first = user_events[0]
        total_input = sum(int(event.get("input_tokens") or 0) for event in user_events)
        total_cached = sum(int(event.get("cached_tokens") or 0) for event in user_events)
        rows.append(
            {
                "user_id": user_id,
                "user_name": first.get("user_name") or user_id,
                "role": first.get("role") or "developer",
                "team": first.get("team") or "unknown",
                "department": first.get("department") or "unknown",
                "total_events": len(user_events),
                "total_cost": _round_money(sum(float(event.get("total_cost") or 0.0) for event in user_events)),
                "total_tokens": sum(int(event.get("total_tokens") or 0) for event in user_events),
                "cache_hit_rate": round(_rate(total_cached, total_input), 4),
                "avg_context_ratio": round(
                    mean(float(event.get("context_ratio") or 0.0) for event in user_events),
                    4,
                ),
                "hygiene_score": calculate_company_hygiene_score(user_events),
            }
        )

    return sorted(rows, key=lambda row: row["total_cost"], reverse=True)


def build_team_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[event.get("team") or "unknown"].append(event)

    rows = []
    for team, team_events in grouped.items():
        first = team_events[0]
        total_input = sum(int(event.get("input_tokens") or 0) for event in team_events)
        total_cached = sum(int(event.get("cached_tokens") or 0) for event in team_events)
        users = {event.get("user_id") for event in team_events if event.get("user_id")}
        rows.append(
            {
                "team": team,
                "department": first.get("department") or "unknown",
                "users": len(users),
                "total_events": len(team_events),
                "total_cost": _round_money(sum(float(event.get("total_cost") or 0.0) for event in team_events)),
                "cache_hit_rate": round(_rate(total_cached, total_input), 4),
                "avg_context_ratio": round(
                    mean(float(event.get("context_ratio") or 0.0) for event in team_events),
                    4,
                ),
                "top_issue": top_issue_title(team_events),
            }
        )

    return sorted(rows, key=lambda row: row["total_cost"], reverse=True)

