from __future__ import annotations

from collections import defaultdict
from typing import Any


ISSUE_TEMPLATES: dict[str, dict[str, Any]] = {
    "H01": {
        "id": "H01",
        "severity": "warning",
        "title": "Context Bloat",
        "description": "A user is regularly sending prompts near the model context limit. This usually means long histories, repeated instructions or large retrieved chunks are being forwarded every time.",
        "fix": "Trim conversation history, summarize older turns and cap retrieved chunks before calling the model.",
        "code_snippet": "messages = summarize_old_turns(messages, keep_last=6)\ncontext = top_k_chunks(chunks, k=5)",
        "estimated_saving_pct": 15,
    },
    "H02": {
        "id": "H02",
        "severity": "critical",
        "title": "Caching Not Active",
        "description": "Large prompts are being sent with little or no cached-token reuse. Repeated system prompts, schemas and tool instructions are likely being paid for on every call.",
        "fix": "Enable prompt caching for stable prefixes and keep reusable instructions before request-specific content.",
        "code_snippet": "messages = [stable_system_prompt, reusable_schema, user_request]\n# Keep stable content byte-identical between calls.",
        "estimated_saving_pct": 40,
    },
    "H03": {
        "id": "H03",
        "severity": "warning",
        "title": "Premium Model Overuse",
        "description": "Premium models are often returning very short answers. These calls may be classification, routing or extraction tasks that a cheaper model can handle.",
        "fix": "Route short deterministic tasks to a standard model and reserve premium models for complex reasoning or generation.",
        "code_snippet": "model = 'gpt-4o-mini' if task in {'classify', 'extract'} else 'gpt-4o'",
        "estimated_saving_pct": 35,
    },
    "H04": {
        "id": "H04",
        "severity": "info",
        "title": "Verbose Instructions",
        "description": "Prompts are long but still far from the context limit. The likely issue is verbose boilerplate rather than true context pressure.",
        "fix": "Move repeated policies into shorter reusable templates and delete duplicate examples.",
        "code_snippet": "system_prompt = render_template('support_agent_short.md', policy=policy_id)",
        "estimated_saving_pct": 20,
    },
    "H05": {
        "id": "H05",
        "severity": "warning",
        "title": "High Retry Rate",
        "description": "A high share of calls require retries. This increases latency and spend and may hide rate-limit, timeout or provider stability problems.",
        "fix": "Log retry reasons, reduce max tokens for timeout-prone calls and add provider fallback only where retries are expected.",
        "code_snippet": "response = call_llm(timeout=20, max_retries=2, fallback_model='gpt-4o-mini')",
        "estimated_saving_pct": 8,
    },
    "H06": {
        "id": "H06",
        "severity": "info",
        "title": "Possible JSON Bloat",
        "description": "Inputs are large and close to the context budget. Repeated JSON schemas or full objects may be included in each request.",
        "fix": "Send compact schemas, field allowlists and IDs instead of complete JSON documents when possible.",
        "code_snippet": "payload = {'customer_id': customer.id, 'fields': ['plan', 'risk_score']}",
        "estimated_saving_pct": 15,
    },
    "H07": {
        "id": "H07",
        "severity": "info",
        "title": "Long Unstructured Output",
        "description": "Responses are long on average. This can make downstream parsing slow and expensive.",
        "fix": "Ask for structured output with explicit length limits and stop generating sections the app does not use.",
        "code_snippet": "response_format = {'type': 'json_object'}\nmax_tokens = 400",
        "estimated_saving_pct": 12,
    },
    "H08": {
        "id": "H08",
        "severity": "critical",
        "title": "Large Context, No Cache",
        "description": "Very large prompts are being sent without enough cached-token reuse. This is the highest-impact caching opportunity in the current dataset.",
        "fix": "Split stable instructions from request data, turn on provider prompt caching and avoid changing stable prompt bytes between calls.",
        "code_snippet": "cached_prefix = build_static_prefix(system_prompt, tools_schema)\nmessages = [cached_prefix, dynamic_user_message]",
        "estimated_saving_pct": 50,
    },
}

SEVERITY_RANK = {"critical": 3, "warning": 2, "info": 1}


def _rate(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def calculate_company_hygiene_score(events: list[dict[str, Any]]) -> int:
    if not events:
        return 100

    total_input_tokens = sum(int(event.get("input_tokens") or 0) for event in events)
    total_cached_tokens = sum(int(event.get("cached_tokens") or 0) for event in events)
    cache_hit_rate = _rate(total_cached_tokens, total_input_tokens)

    avg_context_ratio = sum(float(event.get("context_ratio") or 0) for event in events) / len(events)
    retry_rate = _rate(sum(int(event.get("retry_count") or 0) for event in events), len(events))
    premium_short_calls = sum(
        1
        for event in events
        if event.get("model_tier") == "premium" and int(event.get("output_tokens") or 0) < 200
    )
    overspend_rate = _rate(premium_short_calls, len(events))

    score = 100
    if cache_hit_rate < 0.30:
        score -= 25
    if avg_context_ratio > 0.85:
        score -= 20
    if retry_rate > 0.05:
        score -= 15
    if overspend_rate > 0.20:
        score -= 20

    return max(0, min(100, score))


def event_hygiene_flags(event: dict[str, Any]) -> list[str]:
    input_tokens = int(event.get("input_tokens") or 0)
    output_tokens = int(event.get("output_tokens") or 0)
    cached_tokens = int(event.get("cached_tokens") or 0)
    cache_hit_rate = _rate(cached_tokens, input_tokens)
    flags: list[str] = []

    if float(event.get("context_ratio") or 0) > 0.90:
        flags.append("H01")
    if cache_hit_rate < 0.20 and input_tokens > 1500:
        flags.append("H02")
    if event.get("model_tier") == "premium" and output_tokens < 200:
        flags.append("H03")
    if int(event.get("retry_count") or 0) > 0:
        flags.append("H05")
    if input_tokens > 1000 and float(event.get("context_ratio") or 0) > 0.80:
        flags.append("H06")
    if output_tokens > 500:
        flags.append("H07")
    if input_tokens > 8000 and cache_hit_rate < 0.40:
        flags.append("H08")

    return flags


def _build_user_metrics(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "events": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "retry_count": 0,
            "context_ratio_sum": 0.0,
            "premium_short_calls": 0,
        }
    )

    for event in events:
        user_id = event.get("user_id") or "unknown"
        metric = grouped[user_id]
        metric["events"].append(event)
        metric["input_tokens"] += int(event.get("input_tokens") or 0)
        metric["output_tokens"] += int(event.get("output_tokens") or 0)
        metric["cached_tokens"] += int(event.get("cached_tokens") or 0)
        metric["retry_count"] += int(event.get("retry_count") or 0)
        metric["context_ratio_sum"] += float(event.get("context_ratio") or 0)
        if event.get("model_tier") == "premium" and int(event.get("output_tokens") or 0) < 200:
            metric["premium_short_calls"] += 1

    metrics: list[dict[str, Any]] = []
    for user_id, metric in grouped.items():
        user_events = metric["events"]
        first = user_events[0]
        count = len(user_events)
        metrics.append(
            {
                "user_id": user_id,
                "user_name": first.get("user_name") or user_id,
                "team": first.get("team") or "unknown",
                "department": first.get("department") or "unknown",
                "event_count": count,
                "avg_input_tokens": _rate(metric["input_tokens"], count),
                "avg_output_tokens": _rate(metric["output_tokens"], count),
                "cache_hit_rate": _rate(metric["cached_tokens"], metric["input_tokens"]),
                "avg_context_ratio": _rate(metric["context_ratio_sum"], count),
                "retry_rate": _rate(metric["retry_count"], count),
                "premium_short_rate": _rate(metric["premium_short_calls"], count),
                "events": user_events,
            }
        )
    return metrics


def detect_issues(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    affected_by_issue: dict[str, list[dict[str, str]]] = defaultdict(list)

    for metric in _build_user_metrics(events):
        user_ref = {
            "user_id": metric["user_id"],
            "user_name": metric["user_name"],
            "team": metric["team"],
            "department": metric["department"],
        }

        if metric["avg_context_ratio"] > 0.90 and metric["event_count"] >= 5:
            affected_by_issue["H01"].append(user_ref)
        if metric["cache_hit_rate"] < 0.20 and metric["avg_input_tokens"] > 1500:
            affected_by_issue["H02"].append(user_ref)
        if metric["premium_short_rate"] > 0.20:
            affected_by_issue["H03"].append(user_ref)
        if metric["avg_input_tokens"] > 2000 and metric["avg_context_ratio"] < 0.50:
            affected_by_issue["H04"].append(user_ref)
        if metric["retry_rate"] > 0.08:
            affected_by_issue["H05"].append(user_ref)
        if metric["avg_input_tokens"] > 1000 and metric["avg_context_ratio"] > 0.80:
            affected_by_issue["H06"].append(user_ref)
        if metric["avg_output_tokens"] > 500:
            affected_by_issue["H07"].append(user_ref)
        if metric["avg_input_tokens"] > 8000 and metric["cache_hit_rate"] < 0.40:
            affected_by_issue["H08"].append(user_ref)

    issues = []
    for issue_id, affected_users in affected_by_issue.items():
        issue = dict(ISSUE_TEMPLATES[issue_id])
        issue["affected_users"] = affected_users
        issues.append(issue)

    return sorted(
        issues,
        key=lambda issue: (
            -SEVERITY_RANK.get(issue["severity"], 0),
            issue["id"],
        ),
    )


def top_issue_title(events: list[dict[str, Any]]) -> str:
    issues = detect_issues(events)
    if not issues:
        return "None"
    return issues[0]["title"]

