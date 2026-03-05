from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.domain.models import DeliveryOutboxItem, now_utc_iso


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


class PostgresDeliveryOutboxRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = str(database_url or "").strip()
        if not self._database_url:
            raise ValueError("database_url is required for PostgresDeliveryOutboxRepository")
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
                    CREATE TABLE IF NOT EXISTS delivery_outbox (
                        delivery_id TEXT PRIMARY KEY,
                        channel TEXT NOT NULL,
                        recipient TEXT NOT NULL,
                        content TEXT NOT NULL,
                        status TEXT NOT NULL,
                        metadata_json JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        sent_at TIMESTAMPTZ NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_delivery_outbox_status_created
                    ON delivery_outbox(status, created_at DESC)
                    """
                )

    def enqueue(
        self,
        channel: str,
        recipient: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> DeliveryOutboxItem:
        row = DeliveryOutboxItem(
            delivery_id=str(uuid.uuid4()),
            channel=str(channel or "unknown").strip(),
            recipient=str(recipient or "").strip(),
            content=str(content or ""),
            status="queued",
            metadata=dict(metadata or {}),
            created_at=now_utc_iso(),
            sent_at=None,
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO delivery_outbox
                    (delivery_id, channel, recipient, content, status, metadata_json, created_at, sent_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row.delivery_id,
                        row.channel,
                        row.recipient,
                        row.content,
                        row.status,
                        self._json_value(row.metadata),
                        row.created_at,
                        row.sent_at,
                    ),
                )
        return row

    def mark_sent(self, delivery_id: str) -> DeliveryOutboxItem | None:
        did = str(delivery_id or "")
        if not did:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE delivery_outbox
                    SET status = 'sent', sent_at = %s
                    WHERE delivery_id = %s
                    RETURNING delivery_id, channel, recipient, content, status, metadata_json, created_at, sent_at
                    """,
                    (now_utc_iso(), did),
                )
                row = cur.fetchone()
        if not row:
            return None
        delivery_id, channel, recipient, content, status, metadata_json, created_at, sent_at = row
        return DeliveryOutboxItem(
            delivery_id=str(delivery_id),
            channel=str(channel),
            recipient=str(recipient),
            content=str(content),
            status=str(status),
            metadata=dict(metadata_json or {}),
            created_at=_to_iso(created_at),
            sent_at=_to_iso(sent_at) if sent_at else None,
        )

    def list_pending(self, limit: int = 50) -> list[DeliveryOutboxItem]:
        n = max(1, min(500, int(limit or 50)))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT delivery_id, channel, recipient, content, status, metadata_json, created_at, sent_at
                    FROM delivery_outbox
                    WHERE status = 'queued'
                    ORDER BY created_at DESC, delivery_id DESC
                    LIMIT %s
                    """,
                    (n,),
                )
                rows = cur.fetchall()
        return [
            DeliveryOutboxItem(
                delivery_id=str(delivery_id),
                channel=str(channel),
                recipient=str(recipient),
                content=str(content),
                status=str(status),
                metadata=dict(metadata_json or {}),
                created_at=_to_iso(created_at),
                sent_at=_to_iso(sent_at) if sent_at else None,
            )
            for delivery_id, channel, recipient, content, status, metadata_json, created_at, sent_at in rows
        ]
