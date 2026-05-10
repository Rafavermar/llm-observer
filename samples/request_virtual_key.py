from __future__ import annotations

import argparse
import json
import os

import requests


def _api_base() -> str:
    return os.getenv("OBSERVER_PUBLIC_API_URL", "http://localhost:8080").rstrip("/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Request an Observer virtual key for a synced user.")
    parser.add_argument("--user-id", default="demo.user@company.com")
    parser.add_argument("--app", default="sample-app")
    parser.add_argument("--workflow", default="demo-call")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", action="append", dest="models", default=None)
    parser.add_argument("--max-budget-usd", type=float, default=5.0)
    parser.add_argument("--budget-duration", default="30d")
    parser.add_argument(
        "--try-litellm",
        action="store_true",
        help="Call LiteLLM /key/generate. Requires LiteLLM key management with Postgres.",
    )
    args = parser.parse_args()

    payload = {
        "user_id": args.user_id,
        "app": args.app,
        "workflow": args.workflow,
        "provider": args.provider,
        "models": args.models or ["gpt-4o-mini"],
        "max_budget_usd": args.max_budget_usd,
        "budget_duration": args.budget_duration,
        "try_litellm": args.try_litellm,
    }
    response = requests.post(f"{_api_base()}/api/virtual-keys", json=payload, timeout=15)
    response.raise_for_status()
    body = response.json()

    print("Virtual key issued. Store it securely; Observer only returns it once.")
    print(f"key: {body['key']}")
    print(f"source: {body['source']}")
    print(f"user: {body['user_id']}")
    print(f"team: {body.get('team')}")
    if body.get("litellm_error"):
        print(f"LiteLLM note: {body['litellm_error']}")
    print("\nLiteLLM /key/generate payload:")
    print(json.dumps(body["litellm_generate_payload"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
