from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    ts: datetime = Field(default_factory=utc_now)
    source: str = Field(min_length=1)
    user_id: str | None = None
    user_name: str | None = None
    role: str | None = "developer"
    team: str | None = None
    department: str | None = None
    app: str | None = None
    workflow: str | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    status: str = "success"
    retry_count: int = Field(default=0, ge=0)
    request_id: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source", "status")
    @classmethod
    def trim_required_strings(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_cached_tokens(self) -> Self:
        if self.cached_tokens > self.input_tokens:
            raise ValueError("cached_tokens must be less than or equal to input_tokens")
        return self


class EventOut(BaseModel):
    id: str
    ts: str
    source: str
    user_id: str | None = None
    user_name: str | None = None
    role: str | None = None
    team: str | None = None
    department: str | None = None
    app: str | None = None
    workflow: str | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    latency_ms: int | None = None
    status: str
    retry_count: int
    request_id: str | None = None
    total_tokens: int
    cost_input: float
    cost_cached: float
    cost_output: float
    total_cost: float
    cache_hit: bool
    context_ratio: float
    model_tier: str
    hygiene_flags: list[str] = Field(default_factory=list)
    pricing_warning: str | None = None
    pricing_source: str | None = None
    pricing_unit: str | None = None
    pricing_last_verified: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class EventsResponse(BaseModel):
    items: list[EventOut]
    count: int


class SummaryResponse(BaseModel):
    total_events: int
    total_cost: float
    total_tokens: int
    cache_hit_rate: float
    avg_latency_ms: float
    active_users: int
    hygiene_score: int


class DeveloperRow(BaseModel):
    user_id: str
    user_name: str
    role: str
    team: str
    department: str
    total_events: int
    total_cost: float
    total_tokens: int
    cache_hit_rate: float
    avg_context_ratio: float
    hygiene_score: int


class TeamRow(BaseModel):
    team: str
    department: str
    users: int
    total_events: int
    total_cost: float
    cache_hit_rate: float
    avg_context_ratio: float
    top_issue: str


class HygieneIssue(BaseModel):
    id: str
    severity: str
    title: str
    description: str
    fix: str
    code_snippet: str
    estimated_saving_pct: int
    affected_users: list[dict[str, str]]


class SeedRequest(BaseModel):
    count: int = Field(default=500, ge=1, le=10_000)
    seed: int | None = None

