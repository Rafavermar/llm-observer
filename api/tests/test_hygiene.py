from app.hygiene import calculate_company_hygiene_score, detect_issues


def _event(**overrides):
    event = {
        "user_id": "user@example.com",
        "user_name": "User Example",
        "team": "platform",
        "department": "engineering",
        "input_tokens": 2000,
        "output_tokens": 250,
        "cached_tokens": 0,
        "retry_count": 0,
        "context_ratio": 0.2,
        "model_tier": "standard",
    }
    event.update(overrides)
    return event


def test_hygiene_score_applies_deductions() -> None:
    events = [
        _event(model_tier="premium", output_tokens=100, retry_count=1, context_ratio=0.9)
        for _ in range(10)
    ]

    assert calculate_company_hygiene_score(events) == 20


def test_h02_detection() -> None:
    issues = detect_issues([_event(input_tokens=2500, cached_tokens=0) for _ in range(5)])

    assert any(issue["id"] == "H02" for issue in issues)
    h02 = next(issue for issue in issues if issue["id"] == "H02")
    assert h02["severity"] == "critical"
    assert h02["affected_users"][0]["user_id"] == "user@example.com"

