from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import aggregations, hygiene, identity, pricing, seed, storage
from .config import get_settings
from .models import (
    DeveloperRow,
    DirectoryUserOut,
    UserSyncRequest,
    UserSyncResponse,
    EventCreate,
    EventOut,
    EventsResponse,
    HygieneIssue,
    SeedRequest,
    SummaryResponse,
    TeamRow,
    VirtualKeyCreate,
    VirtualKeyIssued,
    VirtualKeyOut,
)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def enrich_event(payload: EventCreate | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, EventCreate):
        event = payload.model_dump()
    else:
        event = EventCreate.model_validate(payload).model_dump()

    event["id"] = event.get("id") or str(uuid.uuid4())
    event["ts"] = _iso_utc(event["ts"])
    event["provider"] = pricing.normalize_provider(event.get("provider"))
    event["total_tokens"] = int(event.get("input_tokens") or 0) + int(event.get("output_tokens") or 0)
    event["cache_hit"] = int(event.get("cached_tokens") or 0) > 0
    event["context_ratio"] = pricing.context_ratio(
        event.get("provider"),
        event.get("model"),
        int(event.get("input_tokens") or 0),
    )

    pricing_fields = pricing.calculate_cost(
        event.get("provider"),
        event.get("model"),
        int(event.get("input_tokens") or 0),
        int(event.get("output_tokens") or 0),
        int(event.get("cached_tokens") or 0),
    )
    event.update(pricing_fields)
    event["hygiene_flags"] = hygiene.event_hygiene_flags(event)
    return event


def _with_flags(event: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(event)
    enriched["hygiene_flags"] = hygiene.event_hygiene_flags(enriched)
    metadata = pricing.pricing_metadata(enriched.get("provider"))
    enriched.update({key: value for key, value in metadata.items() if key not in enriched or enriched[key] is None})
    return enriched


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.init_db(get_settings().db_path)
    yield


app = FastAPI(title="LLM Observer Tiny MVP", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    db_ok = storage.health_check(get_settings().db_path)
    return {"status": "ok" if db_ok else "degraded", "db": "ok" if db_ok else "error"}


@app.post("/api/events", response_model=EventOut)
def create_event(event: EventCreate) -> dict[str, Any]:
    enriched = enrich_event(event)
    stored = storage.insert_event(enriched)
    stored["pricing_warning"] = enriched.get("pricing_warning")
    stored["pricing_source"] = enriched.get("pricing_source")
    stored["pricing_unit"] = enriched.get("pricing_unit")
    stored["pricing_last_verified"] = enriched.get("pricing_last_verified")
    return _with_flags(stored)


@app.get("/api/events", response_model=EventsResponse)
def get_events(
    limit: int = Query(default=100, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    since: str | None = None,
    user_id: str | None = None,
    team: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    items, count = storage.list_events(
        limit=limit,
        offset=offset,
        since=since,
        user_id=user_id,
        team=team,
        provider=pricing.normalize_provider(provider) if provider else None,
        model=model,
    )
    return {"items": [_with_flags(item) for item in items], "count": count}


@app.get("/api/summary", response_model=SummaryResponse)
def get_summary() -> dict[str, Any]:
    return aggregations.build_summary(storage.list_all_events())


@app.get("/api/developers", response_model=list[DeveloperRow])
def get_developers() -> list[dict[str, Any]]:
    return aggregations.build_developer_rows(storage.list_all_events())


@app.get("/api/teams", response_model=list[TeamRow])
def get_teams() -> list[dict[str, Any]]:
    return aggregations.build_team_rows(storage.list_all_events())


@app.get("/api/hygiene/issues", response_model=list[HygieneIssue])
def get_hygiene_issues() -> list[dict[str, Any]]:
    return hygiene.detect_issues(storage.list_all_events())


@app.post("/api/demo/seed")
def seed_demo_data(request: SeedRequest | None = None) -> dict[str, Any]:
    body = request or SeedRequest()
    generated = seed.generate_demo_events(count=body.count, seed=body.seed)
    inserted = []
    for raw_event in generated:
        inserted.append(storage.insert_event(enrich_event(raw_event)))
    return {"inserted": len(inserted), "count": len(inserted)}


@app.post("/api/demo/clear")
def clear_demo_data() -> dict[str, Any]:
    deleted = storage.clear_events()
    return {"deleted": deleted}


@app.get("/api/users", response_model=list[DirectoryUserOut])
def get_users(
    active: bool | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    return storage.list_users(active=active, query=query)


@app.post("/api/users/sync", response_model=UserSyncResponse)
def sync_users(request: UserSyncRequest) -> dict[str, Any]:
    users = [user.model_dump() for user in request.users]
    synced = storage.upsert_users(users, source=request.source)
    return {"synced": len(synced), "users": synced}


@app.post("/api/users/sync/demo", response_model=UserSyncResponse)
def sync_demo_users() -> dict[str, Any]:
    synced = storage.sync_demo_users()
    return {"synced": len(synced), "users": synced}


@app.get("/api/virtual-keys", response_model=list[VirtualKeyOut])
def get_virtual_keys(
    user_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    return storage.list_virtual_keys(user_id=user_id, status=status)


@app.post("/api/virtual-keys", response_model=VirtualKeyIssued)
async def issue_virtual_key(request: VirtualKeyCreate) -> dict[str, Any]:
    user = storage.get_user(request.user_id)
    if not user or not user.get("active"):
        raise HTTPException(status_code=404, detail="Sync an active user before issuing a virtual key")

    settings = get_settings()
    litellm_payload = identity.build_litellm_generate_payload(request, user)
    litellm_curl = identity.build_litellm_generate_curl(litellm_payload, settings)
    litellm_result = None
    litellm_error = None
    source = "observer_local"
    key = identity.generate_observer_key()

    if request.try_litellm:
        litellm_result, litellm_key, litellm_error = await identity.try_generate_litellm_key(
            litellm_payload,
            settings,
        )
        if litellm_key:
            key = litellm_key
            source = "litellm"

    record = identity.build_virtual_key_record(
        key=key,
        request=request,
        user=user,
        source=source,
    )
    stored = storage.insert_virtual_key(record)
    return {
        **stored,
        "key": key,
        "litellm_generate_payload": litellm_payload,
        "litellm_generate_curl": litellm_curl,
        "litellm_result": litellm_result,
        "litellm_error": litellm_error,
    }

