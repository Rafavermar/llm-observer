from __future__ import annotations

import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


USERS = [
    ("context.bloat@company.com", "Casey Context", "developer", "agent-platform", "engineering"),
    ("no.cache@company.com", "Nora Cache", "developer", "data-platform", "engineering"),
    ("premium.overuse@company.com", "Priya Premium", "developer", "growth-ai", "product"),
    ("flaky.retries@company.com", "Finn Retry", "developer", "support-ops", "operations"),
    ("huge.context@company.com", "Harper Huge", "developer", "legal-ai", "legal"),
    ("demo.user@company.com", "Demo User", "developer", "data-platform", "engineering"),
    ("maya.ml@company.com", "Maya ML", "ml engineer", "agent-platform", "engineering"),
    ("sam.sales@company.com", "Sam Sales", "developer", "revenue-ai", "sales"),
    ("olivia.ops@company.com", "Olivia Ops", "developer", "support-ops", "operations"),
    ("liam.legal@company.com", "Liam Legal", "developer", "legal-ai", "legal"),
]

APPS = [
    ("sample-app", "demo-call"),
    ("support-copilot", "ticket-summary"),
    ("sales-assistant", "account-research"),
    ("data-agent", "sql-generation"),
    ("legal-review", "clause-extraction"),
]

MODELS_BY_PROVIDER = {
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "anthropic": ["claude-3-5-sonnet", "claude-3-haiku"],
    "azure_openai": ["gpt-4o"],
    "databricks": ["dbrx-instruct", "llama-3-70b"],
}


def _ts(rng: random.Random) -> str:
    now = datetime.now(timezone.utc)
    when = now - timedelta(
        days=rng.randint(0, 29),
        hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59),
        seconds=rng.randint(0, 59),
    )
    return when.isoformat().replace("+00:00", "Z")


def _base_event(rng: random.Random, user: tuple[str, str, str, str, str]) -> dict[str, Any]:
    app, workflow = rng.choice(APPS)
    provider = rng.choice(list(MODELS_BY_PROVIDER))
    model = rng.choice(MODELS_BY_PROVIDER[provider])
    input_tokens = rng.randint(250, 2800)
    cached_tokens = rng.randint(0, int(input_tokens * 0.45))
    output_tokens = rng.randint(80, 650)

    return {
        "id": str(uuid.uuid4()),
        "ts": _ts(rng),
        "source": "demo-seed",
        "user_id": user[0],
        "user_name": user[1],
        "role": user[2],
        "team": user[3],
        "department": user[4],
        "app": app,
        "workflow": workflow,
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "latency_ms": rng.randint(350, 4200),
        "status": "success",
        "retry_count": 1 if rng.random() < 0.03 else 0,
        "request_id": f"demo-{uuid.uuid4()}",
        "raw": {"kind": "synthetic-demo"},
    }


def _pattern_event(
    rng: random.Random,
    user: tuple[str, str, str, str, str],
    provider: str,
    model: str,
    input_range: tuple[int, int],
    output_range: tuple[int, int],
    cached_ratio: float,
    retry_count: int = 0,
) -> dict[str, Any]:
    event = _base_event(rng, user)
    input_tokens = rng.randint(*input_range)
    cached_tokens = int(input_tokens * cached_ratio)
    event.update(
        {
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": rng.randint(*output_range),
            "cached_tokens": cached_tokens,
            "retry_count": retry_count,
            "latency_ms": rng.randint(900, 6500),
        }
    )
    return event


def generate_demo_events(count: int = 500, seed: int | None = None) -> list[dict[str, Any]]:
    rng = random.Random(seed if seed is not None else int(time.time()))
    events: list[dict[str, Any]] = []

    pattern_specs = [
        (USERS[0], "databricks", "llama-3-70b", (7550, 8150), (220, 420), 0.12, 0, 7),
        (USERS[1], "openai", "gpt-4o-mini", (1900, 3600), (180, 420), 0.02, 0, 8),
        (USERS[2], "openai", "gpt-4o", (450, 1300), (40, 170), 0.04, 0, 8),
        (USERS[3], "anthropic", "claude-3-haiku", (650, 1800), (150, 450), 0.18, 1, 8),
        (USERS[4], "databricks", "dbrx-instruct", (9200, 12500), (180, 380), 0.05, 0, 7),
    ]

    for user, provider, model, input_range, output_range, cached_ratio, retry_count, repeats in pattern_specs:
        for _ in range(repeats):
            events.append(
                _pattern_event(
                    rng,
                    user,
                    provider,
                    model,
                    input_range,
                    output_range,
                    cached_ratio,
                    retry_count,
                )
            )

    demo_noise_users = USERS[5:]
    while len(events) < count:
        user = rng.choice(demo_noise_users)
        events.append(_base_event(rng, user))

    rng.shuffle(events)
    return events[:count]
