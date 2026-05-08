from __future__ import annotations

import os
import random
import uuid
from datetime import datetime, timezone

import requests


def main() -> None:
    base_url = os.getenv("OBSERVER_PUBLIC_API_URL", "http://localhost:8080").rstrip("/")
    input_tokens = random.randint(900, 2600)
    cached_tokens = random.randint(0, input_tokens // 3)

    event = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "sample-script",
        "user_id": os.getenv("OBSERVER_USER_ID", "demo.user@company.com"),
        "user_name": os.getenv("OBSERVER_USER_NAME", "Demo User"),
        "team": os.getenv("OBSERVER_TEAM", "data-platform"),
        "department": os.getenv("OBSERVER_DEPARTMENT", "engineering"),
        "app": os.getenv("OBSERVER_APP", "sample-app"),
        "workflow": os.getenv("OBSERVER_WORKFLOW", "fake-event"),
        "provider": "openai",
        "model": "gpt-4o-mini",
        "input_tokens": input_tokens,
        "output_tokens": random.randint(120, 450),
        "cached_tokens": cached_tokens,
        "latency_ms": random.randint(550, 2500),
        "status": "success",
        "retry_count": 0,
        "request_id": f"fake-{uuid.uuid4()}",
        "raw": {"sample": "send_fake_event.py"},
    }

    response = requests.post(f"{base_url}/api/events", json=event, timeout=10)
    response.raise_for_status()
    enriched = response.json()

    print("Inserted Observer event")
    print(f"id: {enriched['id']}")
    print(f"model: {enriched['provider']}/{enriched['model']}")
    print(f"tokens: {enriched['total_tokens']}")
    print(f"cost: ${enriched['total_cost']:.6f}")
    print(f"hygiene flags: {', '.join(enriched['hygiene_flags']) or 'none'}")


if __name__ == "__main__":
    main()

