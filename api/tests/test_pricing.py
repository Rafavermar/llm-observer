from app.pricing import calculate_cost, infer_model_tier


def test_pricing_calculates_standard_cost() -> None:
    result = calculate_cost(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=500,
        cached_tokens=0,
    )

    assert result["cost_input"] == 0.00015
    assert result["cost_output"] == 0.0003
    assert result["total_cost"] == 0.00045
    assert result["model_tier"] == "standard"


def test_pricing_calculates_cached_token_cost() -> None:
    result = calculate_cost(
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=0,
        cached_tokens=400,
    )

    assert result["cost_input"] == 0.00009
    assert result["cost_cached"] == 0.00003
    assert result["total_cost"] == 0.00012


def test_unknown_model_does_not_crash() -> None:
    result = calculate_cost(
        provider="unknown-provider",
        model="not-a-model",
        input_tokens=1000,
        output_tokens=100,
        cached_tokens=0,
    )

    assert result["total_cost"] == 0.0
    assert "pricing_warning" in result


def test_infers_premium_model_tier() -> None:
    assert infer_model_tier("openai/gpt-4o", "openai") == "premium"
    assert infer_model_tier("gpt-4o-mini", "openai") == "standard"

