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


class DirectoryUserIn(BaseModel):
    user_id: str = Field(min_length=3, max_length=320)
    user_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    role: str = Field(default="developer", max_length=100)
    team: str | None = Field(default=None, max_length=120)
    department: str | None = Field(default=None, max_length=120)
    active: bool = True

    @field_validator("user_id", "role")
    @classmethod
    def trim_required_user_strings(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value must not be blank")
        return trimmed

    @field_validator("user_name", "email", "team", "department")
    @classmethod
    def trim_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class UserSyncRequest(BaseModel):
    source: str = Field(default="manual", min_length=1, max_length=80)
    users: list[DirectoryUserIn] = Field(min_length=1, max_length=10_000)


class DirectoryUserOut(BaseModel):
    user_id: str
    user_name: str | None = None
    email: str | None = None
    role: str
    team: str | None = None
    department: str | None = None
    source: str
    active: bool
    created_at: str
    updated_at: str


class UserSyncResponse(BaseModel):
    synced: int
    users: list[DirectoryUserOut]


class VirtualKeyCreate(BaseModel):
    user_id: str = Field(min_length=3, max_length=320)
    app: str = Field(default="sample-app", max_length=120)
    workflow: str = Field(default="demo-call", max_length=120)
    provider: str = Field(default="openai", max_length=80)
    models: list[str] = Field(default_factory=lambda: ["gpt-4o-mini"], min_length=1, max_length=20)
    max_budget_usd: float | None = Field(default=None, ge=0)
    budget_duration: str | None = Field(default="30d", max_length=40)
    expires_at: datetime | None = None
    try_litellm: bool = False

    @field_validator("user_id", "app", "workflow", "provider")
    @classmethod
    def trim_required_key_strings(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value must not be blank")
        return trimmed

    @field_validator("budget_duration")
    @classmethod
    def trim_optional_key_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("models")
    @classmethod
    def trim_models(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value and value.strip()]
        if not cleaned:
            raise ValueError("models must include at least one model")
        return cleaned


class VirtualKeyOut(BaseModel):
    id: str
    key_prefix: str
    user_id: str
    user_name: str | None = None
    team: str | None = None
    department: str | None = None
    app: str
    workflow: str
    provider: str
    models: list[str]
    max_budget_usd: float | None = None
    budget_duration: str | None = None
    status: str
    source: str
    created_at: str
    expires_at: str | None = None
    last_used_at: str | None = None


class VirtualKeyIssued(VirtualKeyOut):
    key: str
    litellm_generate_payload: dict[str, Any]
    litellm_generate_curl: str
    litellm_result: dict[str, Any] | None = None
    litellm_error: str | None = None

