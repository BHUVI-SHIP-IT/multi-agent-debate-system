import asyncio
import importlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from settings import settings

try:
    psycopg = importlib.import_module("psycopg")
except Exception:  # pragma: no cover - optional dependency
    psycopg = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DebateRecord:
    debate_id: str
    topic: str
    status: str
    current_node: str
    state_json: str
    error: str
    created_at: str
    updated_at: str


class BaseStateStore:
    async def startup(self) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError

    async def create_debate(self, debate_id: str, topic: str, initial_state: dict[str, Any]) -> None:
        raise NotImplementedError

    async def save_state(self, debate_id: str, node_name: str, state: dict[str, Any]) -> None:
        raise NotImplementedError

    async def update_status(self, debate_id: str, status: str, error: str = "") -> None:
        raise NotImplementedError

    async def get_debate(self, debate_id: str) -> Optional[dict[str, Any]]:
        raise NotImplementedError


class InMemoryStateStore(BaseStateStore):
    def __init__(self) -> None:
        self._records: dict[str, DebateRecord] = {}
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        return

    async def close(self) -> None:
        return

    async def create_debate(self, debate_id: str, topic: str, initial_state: dict[str, Any]) -> None:
        now = _utc_now()
        record = DebateRecord(
            debate_id=debate_id,
            topic=topic,
            status="queued",
            current_node="",
            state_json=json.dumps(initial_state, ensure_ascii=True),
            error="",
            created_at=now,
            updated_at=now,
        )
        async with self._lock:
            self._records[debate_id] = record

    async def save_state(self, debate_id: str, node_name: str, state: dict[str, Any]) -> None:
        async with self._lock:
            record = self._records.get(debate_id)
            if not record:
                return
            record.current_node = node_name
            record.state_json = json.dumps(state, ensure_ascii=True)
            record.updated_at = _utc_now()

    async def update_status(self, debate_id: str, status: str, error: str = "") -> None:
        async with self._lock:
            record = self._records.get(debate_id)
            if not record:
                return
            record.status = status
            record.error = error
            record.updated_at = _utc_now()

    async def get_debate(self, debate_id: str) -> Optional[dict[str, Any]]:
        async with self._lock:
            record = self._records.get(debate_id)
            if not record:
                return None
            return {
                "debate_id": record.debate_id,
                "topic": record.topic,
                "status": record.status,
                "current_node": record.current_node,
                "state": json.loads(record.state_json),
                "error": record.error,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }


class SqliteStateStore(BaseStateStore):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def _run(self, fn, *args, **kwargs):
        return asyncio.to_thread(fn, *args, **kwargs)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _startup_sync(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS debates (
                    debate_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_node TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    async def startup(self) -> None:
        await self._run(self._startup_sync)

    async def close(self) -> None:
        return

    def _create_debate_sync(self, debate_id: str, topic: str, initial_state: dict[str, Any]) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO debates (
                    debate_id, topic, status, current_node, state_json, error, created_at, updated_at
                ) VALUES (?, ?, 'queued', '', ?, '', ?, ?)
                """,
                (debate_id, topic, json.dumps(initial_state, ensure_ascii=True), now, now),
            )
            conn.commit()

    async def create_debate(self, debate_id: str, topic: str, initial_state: dict[str, Any]) -> None:
        await self._run(self._create_debate_sync, debate_id, topic, initial_state)

    def _save_state_sync(self, debate_id: str, node_name: str, state: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE debates
                SET current_node = ?, state_json = ?, updated_at = ?
                WHERE debate_id = ?
                """,
                (node_name, json.dumps(state, ensure_ascii=True), _utc_now(), debate_id),
            )
            conn.commit()

    async def save_state(self, debate_id: str, node_name: str, state: dict[str, Any]) -> None:
        await self._run(self._save_state_sync, debate_id, node_name, state)

    def _update_status_sync(self, debate_id: str, status: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE debates
                SET status = ?, error = ?, updated_at = ?
                WHERE debate_id = ?
                """,
                (status, error, _utc_now(), debate_id),
            )
            conn.commit()

    async def update_status(self, debate_id: str, status: str, error: str = "") -> None:
        await self._run(self._update_status_sync, debate_id, status, error)

    def _get_debate_sync(self, debate_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT debate_id, topic, status, current_node, state_json, error, created_at, updated_at
                FROM debates
                WHERE debate_id = ?
                """,
                (debate_id,),
            ).fetchone()

        if row is None:
            return None

        return {
            "debate_id": row["debate_id"],
            "topic": row["topic"],
            "status": row["status"],
            "current_node": row["current_node"],
            "state": json.loads(row["state_json"]),
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    async def get_debate(self, debate_id: str) -> Optional[dict[str, Any]]:
        return await self._run(self._get_debate_sync, debate_id)


class PostgresStateStore(BaseStateStore):
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _run(self, fn, *args, **kwargs):
        return asyncio.to_thread(fn, *args, **kwargs)

    def _startup_sync(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS debates (
                        debate_id TEXT PRIMARY KEY,
                        topic TEXT NOT NULL,
                        status TEXT NOT NULL,
                        current_node TEXT NOT NULL,
                        state_json JSONB NOT NULL,
                        error TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
            conn.commit()

    async def startup(self) -> None:
        await self._run(self._startup_sync)

    async def close(self) -> None:
        return

    def _create_debate_sync(self, debate_id: str, topic: str, initial_state: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO debates (debate_id, topic, status, current_node, state_json, error, created_at, updated_at)
                    VALUES (%s, %s, 'queued', '', %s::jsonb, '', %s, %s)
                    ON CONFLICT (debate_id) DO UPDATE
                    SET topic = EXCLUDED.topic,
                        status = EXCLUDED.status,
                        current_node = EXCLUDED.current_node,
                        state_json = EXCLUDED.state_json,
                        error = EXCLUDED.error,
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (debate_id, topic, json.dumps(initial_state, ensure_ascii=True), now, now),
                )
            conn.commit()

    async def create_debate(self, debate_id: str, topic: str, initial_state: dict[str, Any]) -> None:
        await self._run(self._create_debate_sync, debate_id, topic, initial_state)

    def _save_state_sync(self, debate_id: str, node_name: str, state: dict[str, Any]) -> None:
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE debates
                    SET current_node = %s, state_json = %s::jsonb, updated_at = %s
                    WHERE debate_id = %s
                    """,
                    (node_name, json.dumps(state, ensure_ascii=True), datetime.now(timezone.utc), debate_id),
                )
            conn.commit()

    async def save_state(self, debate_id: str, node_name: str, state: dict[str, Any]) -> None:
        await self._run(self._save_state_sync, debate_id, node_name, state)

    def _update_status_sync(self, debate_id: str, status: str, error: str) -> None:
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE debates
                    SET status = %s, error = %s, updated_at = %s
                    WHERE debate_id = %s
                    """,
                    (status, error, datetime.now(timezone.utc), debate_id),
                )
            conn.commit()

    async def update_status(self, debate_id: str, status: str, error: str = "") -> None:
        await self._run(self._update_status_sync, debate_id, status, error)

    def _get_debate_sync(self, debate_id: str) -> Optional[dict[str, Any]]:
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT debate_id, topic, status, current_node, state_json, error, created_at, updated_at
                    FROM debates
                    WHERE debate_id = %s
                    """,
                    (debate_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return {
            "debate_id": row[0],
            "topic": row[1],
            "status": row[2],
            "current_node": row[3],
            "state": row[4],
            "error": row[5],
            "created_at": row[6].isoformat(),
            "updated_at": row[7].isoformat(),
        }

    async def get_debate(self, debate_id: str) -> Optional[dict[str, Any]]:
        return await self._run(self._get_debate_sync, debate_id)


def build_state_store() -> BaseStateStore:
    if settings.state_store == "postgres":
        dsn = settings.state_store_path
        if psycopg is not None and dsn:
            return PostgresStateStore(dsn)
        # Fallback if dependencies or DSN are missing.
        return SqliteStateStore("./debate_state.sqlite3")

    if settings.state_store == "memory":
        return InMemoryStateStore()

    return SqliteStateStore(settings.state_store_path)
