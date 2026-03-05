from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Dict, List, Protocol

from app.domain.models import DeliveryOutboxItem, now_utc_iso


class DeliveryOutboxRepository(Protocol):
    def enqueue(
        self,
        channel: str,
        recipient: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> DeliveryOutboxItem:
        ...

    def mark_sent(self, delivery_id: str) -> DeliveryOutboxItem | None:
        ...

    def list_pending(self, limit: int = 50) -> list[DeliveryOutboxItem]:
        ...


class InMemoryDeliveryOutboxRepository:
    def __init__(self) -> None:
        self._rows: Dict[str, DeliveryOutboxItem] = {}
        self._order: List[str] = []

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
        self._rows[row.delivery_id] = row
        self._order.append(row.delivery_id)
        return row

    def mark_sent(self, delivery_id: str) -> DeliveryOutboxItem | None:
        found = self._rows.get(str(delivery_id or ""))
        if not found:
            return None
        updated = replace(found, status="sent", sent_at=now_utc_iso())
        self._rows[updated.delivery_id] = updated
        return updated

    def list_pending(self, limit: int = 50) -> list[DeliveryOutboxItem]:
        n = max(1, min(500, int(limit or 50)))
        pending_ids = [i for i in self._order if self._rows.get(i) and self._rows[i].status == "queued"]
        ids = list(reversed(pending_ids[-n:]))
        return [self._rows[i] for i in ids if i in self._rows]
