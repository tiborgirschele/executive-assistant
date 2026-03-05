from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any

from app.domain.models import ExecutionEvent, ExecutionSession, IntentSpecV3, now_utc_iso


def _to_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


def _intent_from_row(raw: dict[str, Any]) -> IntentSpecV3:
    return IntentSpecV3(
        principal_id=str(raw.get("principal_id") or ""),
        goal=str(raw.get("goal") or ""),
        task_type=str(raw.get("task_type") or ""),
        deliverable_type=str(raw.get("deliverable_type") or ""),
        risk_class=str(raw.get("risk_class") or ""),
        approval_class=str(raw.get("approval_class") or ""),
        budget_class=str(raw.get("budget_class") or ""),
        stakeholders=tuple(raw.get("stakeholders") or ()),
        evidence_requirements=tuple(raw.get("evidence_requirements") or ()),
        allowed_tools=tuple(raw.get("allowed_tools") or ()),
        desired_artifact=str(raw.get("desired_artifact") or ""),
        time_horizon=str(raw.get("time_horizon") or "immediate"),
        interruption_budget=str(raw.get("interruption_budget") or "low"),
        memory_write_policy=str(raw.get("memory_write_policy") or "reviewed_only"),
    )


class PostgresExecutionLedgerRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = str(database_url or "").strip()
        if not self._database_url:
            raise ValueError("database_url is required for PostgresExecutionLedgerRepository")
        self._ensure_schema()

    def _connect(self):  # type: ignore[no-untyped-def]
        try:
            import psycopg
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError("psycopg is required for postgres ledger backend") from exc
        return psycopg.connect(self._database_url, autocommit=True)

    def _json_value(self, value: dict[str, Any]):  # type: ignore[no-untyped-def]
        from psycopg.types.json import Json

        return Json(value)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_sessions (
                        session_id TEXT PRIMARY KEY,
                        intent_json JSONB NOT NULL,
                        status TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_events (
                        event_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL REFERENCES execution_sessions(session_id) ON DELETE CASCADE,
                        name TEXT NOT NULL,
                        payload_json JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_execution_events_session_created
                    ON execution_events(session_id, created_at)
                    """
                )

    def _session_from_db_row(self, row: tuple[Any, Any, Any, Any, Any]) -> ExecutionSession:
        session_id, intent_json, status, created_at, updated_at = row
        return ExecutionSession(
            session_id=str(session_id),
            intent=_intent_from_row(dict(intent_json or {})),
            status=str(status),
            created_at=_to_iso(created_at),
            updated_at=_to_iso(updated_at),
        )

    def start_session(self, intent: IntentSpecV3) -> ExecutionSession:
        session_id = str(uuid.uuid4())
        ts = now_utc_iso()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO execution_sessions (session_id, intent_json, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (session_id, self._json_value(asdict(intent)), "running", ts, ts),
                )
        return ExecutionSession(
            session_id=session_id,
            intent=intent,
            status="running",
            created_at=ts,
            updated_at=ts,
        )

    def complete_session(self, session_id: str, status: str = "completed") -> ExecutionSession | None:
        sid = str(session_id or "")
        if not sid:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE execution_sessions
                    SET status = %s, updated_at = %s
                    WHERE session_id = %s
                    RETURNING session_id, intent_json, status, created_at, updated_at
                    """,
                    (str(status or "completed"), now_utc_iso(), sid),
                )
                row = cur.fetchone()
        if not row:
            return None
        return self._session_from_db_row(row)

    def append_event(self, session_id: str, name: str, payload: dict[str, object] | None = None) -> ExecutionEvent:
        sid = str(session_id or "")
        if not sid or not self.get_session(sid):
            raise KeyError(f"unknown session: {sid}")
        event = ExecutionEvent(
            event_id=str(uuid.uuid4()),
            session_id=sid,
            name=str(name or "event"),
            payload=dict(payload or {}),
            created_at=now_utc_iso(),
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO execution_events (event_id, session_id, name, payload_json, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        event.event_id,
                        event.session_id,
                        event.name,
                        self._json_value(event.payload),
                        event.created_at,
                    ),
                )
        return event

    def get_session(self, session_id: str) -> ExecutionSession | None:
        sid = str(session_id or "")
        if not sid:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT session_id, intent_json, status, created_at, updated_at
                    FROM execution_sessions
                    WHERE session_id = %s
                    """,
                    (sid,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return self._session_from_db_row(row)

    def events_for(self, session_id: str) -> list[ExecutionEvent]:
        sid = str(session_id or "")
        if not sid:
            return []
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id, session_id, name, payload_json, created_at
                    FROM execution_events
                    WHERE session_id = %s
                    ORDER BY created_at ASC, event_id ASC
                    """,
                    (sid,),
                )
                rows = cur.fetchall()
        events: list[ExecutionEvent] = []
        for event_id, found_sid, name, payload_json, created_at in rows:
            events.append(
                ExecutionEvent(
                    event_id=str(event_id),
                    session_id=str(found_sid),
                    name=str(name),
                    payload=dict(payload_json or {}),
                    created_at=_to_iso(created_at),
                )
            )
        return events
