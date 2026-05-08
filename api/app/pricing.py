from __future__ import annotations

from typing import Any


PRICING: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-4o": {"input": 2.50, "output": 10.00, "cached": 1.25},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60, "cached": 0.075},
    },
    "anthropic": {
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00, "cached": 0.30},
        "claude-3-haiku": {"input": 0.25, "output": 1.25, "cached": 0.03},
    },
    "azure_openai": {
        "gpt-4o": {"input": 2.70, "output": 10.80, "cached": 1.35},
    },
    "databricks": {
        "dbrx-instruct": {"input": 0.75, "output": 2.25, "cached": 0.375},
        "llama-3-70b": {"input": 0.54, "output": 1.62, "cached": 0.27},
    },
}

CONTEXT_WINDOWS = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "claude-3-5-sonnet": 200_000,
    "claude-3-haiku": 200_000,
    "dbrx-instruct": 32_768,
    "llama-3-70b": 8_192,
}

PREMIUM_MODELS = {"gpt-4o", "claude-3-5-sonnet"}


def normalize_provider(provider: str | None) -> str:
    value = (provider or "unknown").strip().lower().replace("-", "_")
    if value in {"azure", "azureopenai"}:
        return "azure_openai"
    return value


def normalize_model_name(model: str | None) -> str:
    value = (model or "unknown").strip().lower()
    if "/" in value:
        value = value.split("/", 1)[1]
    return value


def resolve_model_key(provider: str | None, model: str | None) -> str | None:
    normalized_provider = normalize_provider(provider)
    normalized_model = normalize_model_name(model)
    provider_prices = PRICING.get(normalized_provider, {})

    if normalized_model in provider_prices:
        return normalized_model

    for candidate in sorted(provider_prices, key=len, reverse=True):
        if normalized_model.startswith(candidate) or candidate in normalized_model:
            return candidate

    return None


def infer_model_tier(model: str | None, provider: str | None = None) -> str:
    model_key = resolve_model_key(provider, model)
    if model_key in PREMIUM_MODELS:
        return "premium"
    return "standard"


def context_ratio(provider: str | None, model: str | None, input_tokens: int) -> float:
    model_key = resolve_model_key(provider, model) or normalize_model_name(model)
    context_window = CONTEXT_WINDOWS.get(model_key, 16_000)
    if context_window <= 0:
        return 0.0
    return min(max(input_tokens / context_window, 0.0), 1.0)


def calculate_cost(
    provider: str | None,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int,
) -> dict[str, Any]:
    normalized_provider = normalize_provider(provider)
    model_key = resolve_model_key(normalized_provider, model)
    billable_input_tokens = max(input_tokens - cached_tokens, 0)

    result: dict[str, Any] = {
        "cost_input": 0.0,
        "cost_cached": 0.0,
        "cost_output": 0.0,
        "total_cost": 0.0,
        "model_tier": infer_model_tier(model, normalized_provider),
    }

    if not model_key:
        result["pricing_warning"] = (
            f"No pricing configured for provider={normalized_provider}, model={model or 'unknown'}"
        )
        return result

    prices = PRICING[normalized_provider][model_key]
    cost_input = billable_input_tokens * prices["input"] / 1_000_000
    cost_cached = cached_tokens * prices["cached"] / 1_000_000
    cost_output = output_tokens * prices["output"] / 1_000_000

    result.update(
        {
            "cost_input": cost_input,
            "cost_cached": cost_cached,
            "cost_output": cost_output,
            "total_cost": cost_input + cost_cached + cost_output,
        }
    )
    return result

