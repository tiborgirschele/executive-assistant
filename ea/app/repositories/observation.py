from __future__ import annotations

import uuid
from typing import Dict, List, Protocol

from app.domain.models import ObservationEvent, now_utc_iso


class ObservationEventRepository(Protocol):
    def append(
        self,
        principal_id: str,
        channel: str,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> ObservationEvent:
        ...

    def list_recent(self, limit: int = 50) -> list[ObservationEvent]:
        ...


class InMemoryObservationEventRepository:
    def __init__(self) -> None:
        self._rows: Dict[str, ObservationEvent] = {}
        self._order: List[str] = []

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
        self._rows[row.observation_id] = row
        self._order.append(row.observation_id)
        return row

    def list_recent(self, limit: int = 50) -> list[ObservationEvent]:
        n = max(1, min(500, int(limit or 50)))
        ids = list(reversed(self._order[-n:]))
        return [self._rows[i] for i in ids if i in self._rows]
