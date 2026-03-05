from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.domain.models import ObservationEvent, now_utc_iso


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


class PostgresObservationEventRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = str(database_url or "").strip()
        if not self._database_url:
            raise ValueError("database_url is required for PostgresObservationEventRepository")
        self._ensure_schema()

    def _connect(self):  # type: ignore[no-untyped-def]
        try:
            import psycopg
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError("psycopg is required for postgres backend") from exc
        return psycopg.connect(self._database_url, autocommit=True)

    def _json_value(self, value: dict[str, Any]):  # type: ignore[no-untyped-def]
        from psycopg.types.json import Json

        return Json(value)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS observation_events (
                        observation_id TEXT PRIMARY KEY,
                        principal_id TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        payload_json JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_observation_events_created
                    ON observation_events(created_at DESC)
                    """
                )

    def append(
        self,
        principal_id: str,
        channel: str,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> ObservationEvent:
        row = ObservationEvent(
            observation_id=str(uuid.uuid4()),
            principal_id=str(principal_id or "").strip(),
            channel=str(channel or "unknown").strip(),
            event_type=str(event_type or "unknown").strip(),
            payload=dict(payload or {}),
            created_at=now_utc_iso(),
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO observation_events
                    (observation_id, principal_id, channel, event_type, payload_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row.observation_id,
                        row.principal_id,
                        row.channel,
                        row.event_type,
                        self._json_value(row.payload),
                        row.created_at,
                    ),
                )
        return row

    def list_recent(self, limit: int = 50) -> list[ObservationEvent]:
        n = max(1, min(500, int(limit or 50)))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT observation_id, principal_id, channel, event_type, payload_json, created_at
                    FROM observation_events
                    ORDER BY created_at DESC, observation_id DESC
                    LIMIT %s
                    """,
                    (n,),
                )
                rows = cur.fetchall()
        return [
            ObservationEvent(
                observation_id=str(observation_id),
                principal_id=str(principal_id),
                channel=str(channel),
                event_type=str(event_type),
                payload=dict(payload_json or {}),
                created_at=_to_iso(created_at),
            )
            for observation_id, principal_id, channel, event_type, payload_json, created_at in rows
        ]
