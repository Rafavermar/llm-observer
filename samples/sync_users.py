from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import requests


def _api_base() -> str:
    return os.getenv("OBSERVER_PUBLIC_API_URL", "http://localhost:8080").rstrip("/")


def _bool(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "n"}


def read_users(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        users = []
        for row in reader:
            users.append(
                {
                    "user_id": row["user_id"],
                    "user_name": row.get("user_name") or None,
                    "email": row.get("email") or row["user_id"],
                    "role": row.get("role") or "developer",
                    "team": row.get("team") or None,
                    "department": row.get("department") or None,
                    "active": _bool(row.get("active", "true")),
                }
            )
    return users


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync local directory users into Observer.")
    parser.add_argument("--csv", default="samples/users.csv", help="CSV path with user_id,user_name,team,department columns")
    parser.add_argument("--source", default="csv-sample", help="Source label stored with the synced users")
    args = parser.parse_args()

    users = read_users(Path(args.csv))
    response = requests.post(
        f"{_api_base()}/api/users/sync",
        json={"source": args.source, "users": users},
        timeout=10,
    )
    response.raise_for_status()
    body = response.json()
    print(f"Synced {body['synced']} users into Observer from {args.csv}")


if __name__ == "__main__":
    main()
