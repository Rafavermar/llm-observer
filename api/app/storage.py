from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_settings


EVENT_COLUMNS = [
    "id",
    "ts",
    "source",
    "user_id",
    "user_name",
    "role",
    "team",
    "department",
    "app",
    "workflow",
    "provider",
    "model",
    "input_tokens",
    "output_tokens",
    "cached_tokens",
    "latency_ms",
    "status",
    "retry_count",
    "request_id",
    "total_tokens",
    "cost_input",
    "cost_cached",
    "cost_output",
    "total_cost",
    "cache_hit",
    "context_ratio",
    "model_tier",
    "raw_json",
    "created_at",
]


def _db_path(db_path: str | None = None) -> str:
    return db_path or get_settings().db_path


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    path = Path(_db_path(db_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | None = None) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_events (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                source TEXT NOT NULL,
                user_id TEXT,
                user_name TEXT,
                role TEXT,
                team TEXT,
                department TEXT,
                app TEXT,
                workflow TEXT,
                provider TEXT,
                model TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cached_tokens INTEGER,
                latency_ms INTEGER,
                status TEXT,
                retry_count INTEGER,
                request_id TEXT,
                total_tokens INTEGER,
                cost_input REAL,
                cost_cached REAL,
                cost_output REAL,
                total_cost REAL,
                cache_hit INTEGER,
                context_ratio REAL,
                model_tier TEXT,
                raw_json TEXT,
                created_at TEXT
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_llm_events_ts ON llm_events(ts)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_llm_events_user_id ON llm_events(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_llm_events_team ON llm_events(team)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_llm_events_provider ON llm_events(provider)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_llm_events_model ON llm_events(model)")


def health_check(db_path: str | None = None) -> bool:
    try:
        init_db(db_path)
        with _connect(db_path) as connection:
            connection.execute("SELECT 1").fetchone()
        return True
    except sqlite3.Error:
        return False


def _serialize_event(event: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    serialized = {column: event.get(column) for column in EVENT_COLUMNS}
    serialized["cache_hit"] = 1 if event.get("cache_hit") else 0
    serialized["raw_json"] = json.dumps(event.get("raw") or {}, sort_keys=True)
    serialized["created_at"] = event.get("created_at") or now
    return serialized


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    event = dict(row)
    event["cache_hit"] = bool(event.get("cache_hit"))
    raw_json = event.pop("raw_json", None)
    try:
        event["raw"] = json.loads(raw_json or "{}")
    except json.JSONDecodeError:
        event["raw"] = {}
    return event


def insert_event(event: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    serialized = _serialize_event(event)
    placeholders = ", ".join("?" for _ in EVENT_COLUMNS)
    columns = ", ".join(EVENT_COLUMNS)

    with _connect(db_path) as connection:
        connection.execute(
            f"INSERT INTO llm_events ({columns}) VALUES ({placeholders})",
            [serialized[column] for column in EVENT_COLUMNS],
        )
        row = connection.execute("SELECT * FROM llm_events WHERE id = ?", (serialized["id"],)).fetchone()
    return _row_to_event(row)


def _like_pattern(value: str) -> str:
    escaped = (
        value.strip()
        .lower()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


def _append_like_filter(
    where: list[str],
    params: list[Any],
    columns: list[str],
    value: str | None,
) -> None:
    if not value or not value.strip():
        return

    pattern = _like_pattern(value)
    clauses = [f"LOWER(COALESCE({column}, '')) LIKE ? ESCAPE '\\'" for column in columns]
    where.append(f"({' OR '.join(clauses)})")
    params.extend([pattern] * len(columns))


def list_events(
    *,
    limit: int = 100,
    offset: int = 0,
    since: str | None = None,
    user_id: str | None = None,
    team: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    db_path: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    where = []
    params: list[Any] = []

    if since:
        where.append("ts >= ?")
        params.append(since)

    _append_like_filter(where, params, ["user_id", "user_name"], user_id)
    _append_like_filter(where, params, ["team"], team)
    _append_like_filter(where, params, ["provider"], provider)
    _append_like_filter(where, params, ["model"], model)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    safe_limit = min(max(limit, 1), 5000)
    safe_offset = max(offset, 0)

    with _connect(db_path) as connection:
        count = connection.execute(f"SELECT COUNT(*) AS count FROM llm_events {where_sql}", params).fetchone()["count"]
        rows = connection.execute(
            f"""
            SELECT * FROM llm_events
            {where_sql}
            ORDER BY ts DESC
            LIMIT ? OFFSET ?
            """,
            [*params, safe_limit, safe_offset],
        ).fetchall()

    return [_row_to_event(row) for row in rows], int(count)


def list_all_events(db_path: str | None = None) -> list[dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute("SELECT * FROM llm_events ORDER BY ts DESC").fetchall()
    return [_row_to_event(row) for row in rows]


def clear_events(db_path: str | None = None) -> int:
    with _connect(db_path) as connection:
        cursor = connection.execute("DELETE FROM llm_events")
    return int(cursor.rowcount)

