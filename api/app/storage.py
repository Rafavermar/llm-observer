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

USER_COLUMNS = [
    "user_id",
    "user_name",
    "email",
    "role",
    "team",
    "department",
    "source",
    "active",
    "created_at",
    "updated_at",
]

VIRTUAL_KEY_COLUMNS = [
    "id",
    "key_hash",
    "key_prefix",
    "user_id",
    "user_name",
    "team",
    "department",
    "app",
    "workflow",
    "provider",
    "models_json",
    "max_budget_usd",
    "budget_duration",
    "status",
    "source",
    "created_at",
    "expires_at",
    "last_used_at",
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS observer_users (
                user_id TEXT PRIMARY KEY,
                user_name TEXT,
                email TEXT,
                role TEXT,
                team TEXT,
                department TEXT,
                source TEXT,
                active INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_observer_users_team ON observer_users(team)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_observer_users_department ON observer_users(department)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_observer_users_active ON observer_users(active)")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS observer_virtual_keys (
                id TEXT PRIMARY KEY,
                key_hash TEXT NOT NULL UNIQUE,
                key_prefix TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT,
                team TEXT,
                department TEXT,
                app TEXT,
                workflow TEXT,
                provider TEXT,
                models_json TEXT,
                max_budget_usd REAL,
                budget_duration TEXT,
                status TEXT,
                source TEXT,
                created_at TEXT,
                expires_at TEXT,
                last_used_at TEXT
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_observer_virtual_keys_user_id ON observer_virtual_keys(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_observer_virtual_keys_status ON observer_virtual_keys(status)")


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _row_to_user(row: sqlite3.Row) -> dict[str, Any]:
    user = dict(row)
    user["active"] = bool(user.get("active"))
    return user


def upsert_users(users: list[dict[str, Any]], source: str, db_path: str | None = None) -> list[dict[str, Any]]:
    now = _now_iso()
    synced_ids = [user["user_id"] for user in users]

    with _connect(db_path) as connection:
        for user in users:
            existing = connection.execute(
                "SELECT created_at FROM observer_users WHERE user_id = ?",
                (user["user_id"],),
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            connection.execute(
                """
                INSERT INTO observer_users (
                    user_id, user_name, email, role, team, department, source, active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    user_name = excluded.user_name,
                    email = excluded.email,
                    role = excluded.role,
                    team = excluded.team,
                    department = excluded.department,
                    source = excluded.source,
                    active = excluded.active,
                    updated_at = excluded.updated_at
                """,
                (
                    user["user_id"],
                    user.get("user_name"),
                    user.get("email") or user["user_id"],
                    user.get("role") or "developer",
                    user.get("team"),
                    user.get("department"),
                    source,
                    1 if user.get("active", True) else 0,
                    created_at,
                    now,
                ),
            )

        placeholders = ", ".join("?" for _ in synced_ids)
        rows = connection.execute(
            f"SELECT * FROM observer_users WHERE user_id IN ({placeholders}) ORDER BY user_id",
            synced_ids,
        ).fetchall()

    return [_row_to_user(row) for row in rows]


def sync_demo_users(db_path: str | None = None) -> list[dict[str, Any]]:
    from . import seed

    users = [
        {
            "user_id": user_id,
            "email": user_id,
            "user_name": user_name,
            "role": role,
            "team": team,
            "department": department,
            "active": True,
        }
        for user_id, user_name, role, team, department in seed.USERS
    ]
    return upsert_users(users, source="demo-seed", db_path=db_path)


def list_users(
    *,
    active: bool | None = None,
    query: str | None = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []

    if active is not None:
        where.append("active = ?")
        params.append(1 if active else 0)

    _append_like_filter(where, params, ["user_id", "user_name", "email", "team", "department"], query)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with _connect(db_path) as connection:
        rows = connection.execute(
            f"SELECT * FROM observer_users {where_sql} ORDER BY team, user_name, user_id",
            params,
        ).fetchall()

    return [_row_to_user(row) for row in rows]


def get_user(user_id: str, db_path: str | None = None) -> dict[str, Any] | None:
    with _connect(db_path) as connection:
        row = connection.execute("SELECT * FROM observer_users WHERE user_id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def _row_to_virtual_key(row: sqlite3.Row) -> dict[str, Any]:
    virtual_key = dict(row)
    virtual_key.pop("key_hash", None)
    try:
        virtual_key["models"] = json.loads(virtual_key.pop("models_json") or "[]")
    except json.JSONDecodeError:
        virtual_key["models"] = []
    return virtual_key


def insert_virtual_key(virtual_key: dict[str, Any], db_path: str | None = None) -> dict[str, Any]:
    serialized = {column: virtual_key.get(column) for column in VIRTUAL_KEY_COLUMNS}
    serialized["models_json"] = json.dumps(virtual_key.get("models") or [], sort_keys=True)
    serialized["created_at"] = virtual_key.get("created_at") or _now_iso()
    placeholders = ", ".join("?" for _ in VIRTUAL_KEY_COLUMNS)
    columns = ", ".join(VIRTUAL_KEY_COLUMNS)

    with _connect(db_path) as connection:
        connection.execute(
            f"INSERT INTO observer_virtual_keys ({columns}) VALUES ({placeholders})",
            [serialized[column] for column in VIRTUAL_KEY_COLUMNS],
        )
        row = connection.execute(
            "SELECT * FROM observer_virtual_keys WHERE id = ?",
            (serialized["id"],),
        ).fetchone()

    return _row_to_virtual_key(row)


def list_virtual_keys(
    *,
    user_id: str | None = None,
    status: str | None = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []

    if user_id:
        where.append("user_id = ?")
        params.append(user_id)

    if status:
        where.append("status = ?")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    with _connect(db_path) as connection:
        rows = connection.execute(
            f"SELECT * FROM observer_virtual_keys {where_sql} ORDER BY created_at DESC",
            params,
        ).fetchall()

    return [_row_to_virtual_key(row) for row in rows]

