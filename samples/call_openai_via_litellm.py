from __future__ import annotations

import argparse
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from openai import OpenAI


def _usage_value(usage: Any, *names: str) -> int:
    for name in names:
        if usage is None:
            return 0
        value = getattr(usage, name, None)
        if value is None and isinstance(usage, dict):
            value = usage.get(name)
        if value is not None:
            return int(value)
    return 0


def _cached_tokens(usage: Any) -> int:
    details = getattr(usage, "prompt_tokens_details", None)
    if details is None and isinstance(usage, dict):
        details = usage.get("prompt_tokens_details")
    if isinstance(details, dict):
        return int(details.get("cached_tokens") or 0)
    return int(getattr(details, "cached_tokens", 0) or 0)


def _send_observer_event(response: Any, latency_ms: int) -> None:
    base_url = os.getenv("OBSERVER_PUBLIC_API_URL", "http://localhost:8080").rstrip("/")
    usage = getattr(response, "usage", None)
    input_tokens = _usage_value(usage, "prompt_tokens", "input_tokens")
    cached_tokens = min(_cached_tokens(usage), input_tokens)
    model = getattr(response, "model", None) or "gpt-4o-mini"

    event = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "sample-litellm-fallback",
        "user_id": os.getenv("OBSERVER_USER_ID", "demo.user@company.com"),
        "user_name": os.getenv("OBSERVER_USER_NAME", "Demo User"),
        "team": os.getenv("OBSERVER_TEAM", "data-platform"),
        "department": os.getenv("OBSERVER_DEPARTMENT", "engineering"),
        "app": os.getenv("OBSERVER_APP", "sample-app"),
        "workflow": os.getenv("OBSERVER_WORKFLOW", "demo-call"),
        "provider": "openai",
        "model": model.split("/", 1)[1] if "/" in model else model,
        "input_tokens": input_tokens,
        "output_tokens": _usage_value(usage, "completion_tokens", "output_tokens"),
        "cached_tokens": cached_tokens,
        "latency_ms": latency_ms,
        "status": "success",
        "retry_count": 0,
        "request_id": getattr(response, "id", None) or f"fallback-{uuid.uuid4()}",
        "raw": {"sample": "call_openai_via_litellm.py", "fallback": True},
    }
    result = requests.post(f"{base_url}/api/events", json=event, timeout=10)
    result.raise_for_status()
    print(f"Fallback Observer event inserted: {result.json()['id']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Call OpenAI through LiteLLM Proxy.")
    parser.add_argument(
        "--also-send-observer-event",
        action="store_true",
        help="Send a normalized Observer event directly after the LiteLLM call.",
    )
    args = parser.parse_args()

    client = OpenAI(
        base_url=os.getenv("LITELLM_BASE_URL", "http://localhost:4040/v1"),
        api_key=os.getenv("LITELLM_MASTER_KEY", "sk-litellm-master-key"),
    )

    started = time.perf_counter()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a concise demo assistant."},
            {"role": "user", "content": "Reply in one sentence: what does LLM Observer track?"},
        ],
        user=os.getenv("OBSERVER_USER_ID", "demo.user@company.com"),
        extra_body={
            "metadata": {
                "observer_user_id": os.getenv("OBSERVER_USER_ID", "demo.user@company.com"),
                "observer_user_name": os.getenv("OBSERVER_USER_NAME", "Demo User"),
                "observer_team": os.getenv("OBSERVER_TEAM", "data-platform"),
                "observer_department": os.getenv("OBSERVER_DEPARTMENT", "engineering"),
                "observer_app": os.getenv("OBSERVER_APP", "sample-app"),
                "observer_workflow": os.getenv("OBSERVER_WORKFLOW", "demo-call"),
            }
        },
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    print(response.choices[0].message.content)
    print(f"model: {response.model}")
    print(f"usage: {response.usage}")
    print("Observer should receive this through the LiteLLM callback.")

    if args.also_send_observer_event:
        _send_observer_event(response, latency_ms)


if __name__ == "__main__":
    main()

