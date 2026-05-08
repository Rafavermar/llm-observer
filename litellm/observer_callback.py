from __future__ import annotations

import asyncio
import json
import os
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

try:
    from litellm.integrations.custom_logger import CustomLogger
except Exception:  # pragma: no cover - only used outside the LiteLLM container
    class CustomLogger:  # type: ignore[no-redef]
        pass


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    try:
        return dict(value)
    except Exception:
        return getattr(value, "__dict__", {}) or {}


def _get_nested(mapping: dict[str, Any], *path: str) -> Any:
    current: Any = mapping
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            current = getattr(current, key, None)
        if current is None:
            return None
    return current


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _duration_ms(start_time: Any, end_time: Any) -> int | None:
    try:
        if isinstance(start_time, datetime) and isinstance(end_time, datetime):
            return max(int((end_time - start_time).total_seconds() * 1000), 0)
        return max(int((float(end_time) - float(start_time)) * 1000), 0)
    except Exception:
        return None


def _provider_from_model(model: str | None) -> str:
    value = (model or "").lower()
    if "/" in value:
        prefix = value.split("/", 1)[0]
        if prefix == "azure":
            return "azure_openai"
        return prefix
    if value.startswith("claude"):
        return "anthropic"
    if value.startswith("dbrx") or value.startswith("llama"):
        return "databricks"
    return "openai"


def _usage_from_response(response: dict[str, Any], standard_log: dict[str, Any]) -> dict[str, int]:
    usage = _to_dict(response.get("usage")) or _to_dict(standard_log.get("usage"))
    prompt_details = _to_dict(usage.get("prompt_tokens_details")) or _to_dict(usage.get("input_token_details"))

    cached_tokens = (
        prompt_details.get("cached_tokens")
        or usage.get("cache_read_input_tokens")
        or usage.get("cached_tokens")
        or 0
    )

    return {
        "input_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or standard_log.get("prompt_tokens") or 0),
        "output_tokens": int(
            usage.get("completion_tokens")
            or usage.get("output_tokens")
            or standard_log.get("completion_tokens")
            or 0
        ),
        "cached_tokens": int(cached_tokens or 0),
    }


def _metadata(kwargs: dict[str, Any], standard_log: dict[str, Any]) -> dict[str, Any]:
    litellm_params = _to_dict(kwargs.get("litellm_params"))
    metadata = {}
    metadata.update(_to_dict(litellm_params.get("metadata")))
    metadata.update(_to_dict(kwargs.get("metadata")))
    metadata.update(_to_dict(standard_log.get("metadata")))
    return metadata


def _identity(metadata: dict[str, Any], kwargs: dict[str, Any]) -> dict[str, str | None]:
    return {
        "user_id": metadata.get("observer_user_id")
        or metadata.get("user_id")
        or kwargs.get("user")
        or os.getenv("OBSERVER_USER_ID"),
        "user_name": metadata.get("observer_user_name") or metadata.get("user_name") or os.getenv("OBSERVER_USER_NAME"),
        "team": metadata.get("observer_team") or metadata.get("team") or os.getenv("OBSERVER_TEAM"),
        "department": metadata.get("observer_department")
        or metadata.get("department")
        or os.getenv("OBSERVER_DEPARTMENT"),
        "app": metadata.get("observer_app") or metadata.get("app") or os.getenv("OBSERVER_APP"),
        "workflow": metadata.get("observer_workflow") or metadata.get("workflow") or os.getenv("OBSERVER_WORKFLOW"),
    }


def _post_event(event: dict[str, Any]) -> None:
    base_url = os.getenv("OBSERVER_API_URL", "http://observer-api:8080").rstrip("/")
    body = json.dumps(event).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/events",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2.0) as response:
        response.read()


class ObserverCallback(CustomLogger):
    def _build_event(
        self,
        kwargs: Any,
        response_obj: Any,
        start_time: Any,
        end_time: Any,
        status: str,
        error: Any = None,
    ) -> dict[str, Any]:
        kwargs_dict = _to_dict(kwargs)
        response = _to_dict(response_obj)
        standard_log = _to_dict(kwargs_dict.get("standard_logging_object"))
        metadata = _metadata(kwargs_dict, standard_log)
        usage = _usage_from_response(response, standard_log)

        model = (
            response.get("model")
            or standard_log.get("model")
            or standard_log.get("model_group")
            or kwargs_dict.get("model")
            or "unknown"
        )

        input_tokens = usage["input_tokens"]
        cached_tokens = min(usage["cached_tokens"], input_tokens)

        event = {
            "ts": _utc_now(),
            "source": "litellm",
            **_identity(metadata, kwargs_dict),
            "provider": metadata.get("provider") or _provider_from_model(model),
            "model": model.split("/", 1)[1] if "/" in model else model,
            "input_tokens": input_tokens,
            "output_tokens": usage["output_tokens"],
            "cached_tokens": cached_tokens,
            "latency_ms": _duration_ms(start_time, end_time),
            "status": status,
            "retry_count": int(_get_nested(standard_log, "retry_count") or kwargs_dict.get("num_retries") or 0),
            "request_id": response.get("id") or standard_log.get("id") or standard_log.get("call_id"),
            "raw": {
                "litellm_model": model,
                "metadata": metadata,
                "usage": usage,
                "response_cost": standard_log.get("response_cost") or kwargs_dict.get("response_cost"),
            },
        }
        if error is not None:
            event["raw"]["error"] = str(error)
        return event

    def _safe_send(
        self,
        kwargs: Any,
        response_obj: Any,
        start_time: Any,
        end_time: Any,
        status: str,
        error: Any = None,
    ) -> None:
        try:
            _post_event(self._build_event(kwargs, response_obj, start_time, end_time, status, error))
        except (urllib.error.URLError, TimeoutError, Exception) as exc:
            print(f"[observer_callback] failed to post Observer event: {exc}")
            print(traceback.format_exc())

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._safe_send(kwargs, response_obj, start_time, end_time, "success")

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        self._safe_send(kwargs, response_obj, start_time, end_time, "failure", response_obj)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        await asyncio.to_thread(self._safe_send, kwargs, response_obj, start_time, end_time, "success")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        await asyncio.to_thread(self._safe_send, kwargs, response_obj, start_time, end_time, "failure", response_obj)


proxy_handler_instance = ObserverCallback()

