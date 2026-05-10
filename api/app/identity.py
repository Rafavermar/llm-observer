from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import Settings
from .models import VirtualKeyCreate


def utc_iso(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_observer_key() -> str:
    return f"sk-obsv-{secrets.token_urlsafe(32)}"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def key_prefix(key: str) -> str:
    if len(key) <= 18:
        return key
    return f"{key[:12]}...{key[-4:]}"


def build_litellm_generate_payload(
    request: VirtualKeyCreate,
    user: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "models": request.models,
        "user_id": request.user_id,
        "metadata": {
            "observer_user_id": request.user_id,
            "user_name": user.get("user_name"),
            "team": user.get("team"),
            "department": user.get("department"),
            "app": request.app,
            "workflow": request.workflow,
            "provider": request.provider,
        },
    }
    if request.max_budget_usd is not None:
        payload["max_budget"] = request.max_budget_usd
    if request.budget_duration:
        payload["budget_duration"] = request.budget_duration
    if request.expires_at:
        payload["duration"] = None
        payload["expires"] = utc_iso(request.expires_at)
    return payload


def build_litellm_generate_curl(payload: dict[str, Any], settings: Settings) -> str:
    import json

    body = json.dumps(payload, indent=2, sort_keys=True)
    return "\n".join(
        [
            f"curl -X POST {settings.litellm_public_url}/key/generate \\",
            '  -H "Authorization: Bearer <LITELLM_MASTER_KEY>" \\',
            '  -H "Content-Type: application/json" \\',
            f"  -d '{body}'",
        ]
    )


def extract_litellm_key(response: dict[str, Any]) -> str | None:
    for key in ("key", "token", "virtual_key"):
        value = response.get(key)
        if isinstance(value, str) and value.startswith("sk-"):
            return value
    info = response.get("info")
    if isinstance(info, dict):
        token = info.get("token")
        if isinstance(token, str) and token.startswith("sk-"):
            return token
    return None


async def try_generate_litellm_key(
    payload: dict[str, Any],
    settings: Settings,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    if not settings.litellm_master_key:
        return None, None, "LITELLM_MASTER_KEY is not configured"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{settings.litellm_internal_url}/key/generate",
                headers={
                    "Authorization": f"Bearer {settings.litellm_master_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        body = response.json()
        return body, extract_litellm_key(body), None
    except httpx.HTTPStatusError as exc:
        text = exc.response.text[:500]
        return None, None, f"LiteLLM returned {exc.response.status_code}: {text}"
    except (httpx.HTTPError, ValueError) as exc:
        return None, None, f"LiteLLM key generation failed: {exc}"


def build_virtual_key_record(
    *,
    key: str,
    request: VirtualKeyCreate,
    user: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "key_hash": hash_key(key),
        "key_prefix": key_prefix(key),
        "user_id": request.user_id,
        "user_name": user.get("user_name"),
        "team": user.get("team"),
        "department": user.get("department"),
        "app": request.app,
        "workflow": request.workflow,
        "provider": request.provider,
        "models": request.models,
        "max_budget_usd": request.max_budget_usd,
        "budget_duration": request.budget_duration,
        "status": "active",
        "source": source,
        "created_at": utc_iso(),
        "expires_at": utc_iso(request.expires_at) if request.expires_at else None,
        "last_used_at": None,
    }
