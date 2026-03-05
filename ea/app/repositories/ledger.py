from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Dict, List, Protocol

from app.domain.models import ExecutionEvent, ExecutionSession, IntentSpecV3, now_utc_iso


class ExecutionLedgerRepository(Protocol):
    def start_session(self, intent: IntentSpecV3) -> ExecutionSession:
        ...

    def complete_session(self, session_id: str, status: str = "completed") -> ExecutionSession | None:
        ...

    def append_event(self, session_id: str, name: str, payload: dict[str, object] | None = None) -> ExecutionEvent:
        ...

    def get_session(self, session_id: str) -> ExecutionSession | None:
        ...

    def events_for(self, session_id: str) -> list[ExecutionEvent]:
        ...


class InMemoryExecutionLedgerRepository:
    def __init__(self) -> None:
        self._sessions: Dict[str, ExecutionSession] = {}
        self._events: Dict[str, List[ExecutionEvent]] = {}

    def start_session(self, intent: IntentSpecV3) -> ExecutionSession:
        ts = now_utc_iso()
        session = ExecutionSession(
            session_id=str(uuid.uuid4()),
            intent=intent,
            status="running",
            created_at=ts,
            updated_at=ts,
        )
        self._sessions[session.session_id] = session
        self._events[session.session_id] = []
        return session

    def complete_session(self, session_id: str, status: str = "completed") -> ExecutionSession | None:
        session = self._sessions.get(str(session_id or ""))
        if not session:
            return None
        updated = replace(session, status=str(status or "completed"), updated_at=now_utc_iso())
        self._sessions[updated.session_id] = updated
        return updated

    def append_event(self, session_id: str, name: str, payload: dict[str, object] | None = None) -> ExecutionEvent:
        sid = str(session_id or "")
        if sid not in self._sessions:
            raise KeyError(f"unknown session: {sid}")
        event = ExecutionEvent(
            event_id=str(uuid.uuid4()),
            session_id=sid,
            name=str(name or "event"),
            payload=dict(payload or {}),
            created_at=now_utc_iso(),
        )
        self._events[sid].append(event)
        return event

    def get_session(self, session_id: str) -> ExecutionSession | None:
        return self._sessions.get(str(session_id or ""))

    def events_for(self, session_id: str) -> list[ExecutionEvent]:
        return list(self._events.get(str(session_id or ""), []))
