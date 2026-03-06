from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any

from app.domain.models import (
    ExecutionEvent,
    ExecutionSession,
    ExecutionStep,
    IntentSpecV3,
    RunCost,
    ToolReceipt,
    now_utc_iso,
)


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
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_steps (
                        step_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL REFERENCES execution_sessions(session_id) ON DELETE CASCADE,
                        parent_step_id TEXT NULL,
                        step_kind TEXT NOT NULL,
                        state TEXT NOT NULL,
                        attempt_count INT NOT NULL,
                        input_json JSONB NOT NULL,
                        output_json JSONB NOT NULL,
                        error_json JSONB NOT NULL,
                        correlation_id TEXT NOT NULL,
                        causation_id TEXT NOT NULL,
                        actor_type TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_execution_steps_session_created
                    ON execution_steps(session_id, created_at, step_id)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tool_receipts (
                        receipt_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL REFERENCES execution_sessions(session_id) ON DELETE CASCADE,
                        step_id TEXT NOT NULL REFERENCES execution_steps(step_id) ON DELETE CASCADE,
                        tool_name TEXT NOT NULL,
                        action_kind TEXT NOT NULL,
                        target_ref TEXT NOT NULL,
                        receipt_json JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_tool_receipts_session_created
                    ON tool_receipts(session_id, created_at, receipt_id)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_costs (
                        cost_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL REFERENCES execution_sessions(session_id) ON DELETE CASCADE,
                        model_name TEXT NOT NULL,
                        tokens_in BIGINT NOT NULL,
                        tokens_out BIGINT NOT NULL,
                        cost_usd DOUBLE PRECISION NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_run_costs_session_created
                    ON run_costs(session_id, created_at, cost_id)
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

    def _step_from_db_row(self, row: tuple[Any, ...]) -> ExecutionStep:
        (
            step_id,
            session_id,
            parent_step_id,
            step_kind,
            state,
            attempt_count,
            input_json,
            output_json,
            error_json,
            correlation_id,
            causation_id,
            actor_type,
            actor_id,
            created_at,
            updated_at,
        ) = row
        return ExecutionStep(
            step_id=str(step_id),
            session_id=str(session_id),
            parent_step_id=str(parent_step_id) if parent_step_id else None,
            step_kind=str(step_kind),
            state=str(state),
            attempt_count=int(attempt_count),
            input_json=dict(input_json or {}),
            output_json=dict(output_json or {}),
            error_json=dict(error_json or {}),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id),
            actor_type=str(actor_type),
            actor_id=str(actor_id),
            created_at=_to_iso(created_at),
            updated_at=_to_iso(updated_at),
        )

    def _receipt_from_db_row(self, row: tuple[Any, ...]) -> ToolReceipt:
        receipt_id, session_id, step_id, tool_name, action_kind, target_ref, receipt_json, created_at = row
        return ToolReceipt(
            receipt_id=str(receipt_id),
            session_id=str(session_id),
            step_id=str(step_id),
            tool_name=str(tool_name),
            action_kind=str(action_kind),
            target_ref=str(target_ref),
            receipt_json=dict(receipt_json or {}),
            created_at=_to_iso(created_at),
        )

    def _cost_from_db_row(self, row: tuple[Any, ...]) -> RunCost:
        cost_id, session_id, model_name, tokens_in, tokens_out, cost_usd, created_at = row
        return RunCost(
            cost_id=str(cost_id),
            session_id=str(session_id),
            model_name=str(model_name),
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            cost_usd=float(cost_usd),
            created_at=_to_iso(created_at),
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
        return [
            ExecutionEvent(
                event_id=str(event_id),
                session_id=str(found_sid),
                name=str(name),
                payload=dict(payload_json or {}),
                created_at=_to_iso(created_at),
            )
            for event_id, found_sid, name, payload_json, created_at in rows
        ]

    def start_step(
        self,
        session_id: str,
        step_kind: str,
        *,
        parent_step_id: str | None = None,
        input_json: dict[str, object] | None = None,
        correlation_id: str = "",
        causation_id: str = "",
        actor_type: str = "system",
        actor_id: str = "orchestrator",
    ) -> ExecutionStep:
        sid = str(session_id or "")
        if not sid or not self.get_session(sid):
            raise KeyError(f"unknown session: {sid}")
        ts = now_utc_iso()
        step = ExecutionStep(
            step_id=str(uuid.uuid4()),
            session_id=sid,
            parent_step_id=str(parent_step_id) if parent_step_id else None,
            step_kind=str(step_kind or "step"),
            state="running",
            attempt_count=1,
            input_json=dict(input_json or {}),
            output_json={},
            error_json={},
            correlation_id=str(correlation_id or ""),
            causation_id=str(causation_id or ""),
            actor_type=str(actor_type or "system"),
            actor_id=str(actor_id or "orchestrator"),
            created_at=ts,
            updated_at=ts,
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO execution_steps
                    (step_id, session_id, parent_step_id, step_kind, state, attempt_count, input_json, output_json, error_json,
                     correlation_id, causation_id, actor_type, actor_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        step.step_id,
                        step.session_id,
                        step.parent_step_id,
                        step.step_kind,
                        step.state,
                        step.attempt_count,
                        self._json_value(step.input_json),
                        self._json_value(step.output_json),
                        self._json_value(step.error_json),
                        step.correlation_id,
                        step.causation_id,
                        step.actor_type,
                        step.actor_id,
                        step.created_at,
                        step.updated_at,
                    ),
                )
        return step

    def update_step(
        self,
        step_id: str,
        *,
        state: str,
        output_json: dict[str, object] | None = None,
        error_json: dict[str, object] | None = None,
    ) -> ExecutionStep | None:
        sid = str(step_id or "")
        if not sid:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE execution_steps
                    SET state = %s,
                        output_json = %s,
                        error_json = %s,
                        updated_at = %s
                    WHERE step_id = %s
                    RETURNING step_id, session_id, parent_step_id, step_kind, state, attempt_count, input_json, output_json, error_json,
                              correlation_id, causation_id, actor_type, actor_id, created_at, updated_at
                    """,
                    (
                        str(state or "completed"),
                        self._json_value(dict(output_json or {})),
                        self._json_value(dict(error_json or {})),
                        now_utc_iso(),
                        sid,
                    ),
                )
                row = cur.fetchone()
        if not row:
            return None
        return self._step_from_db_row(row)

    def steps_for(self, session_id: str) -> list[ExecutionStep]:
        sid = str(session_id or "")
        if not sid:
            return []
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT step_id, session_id, parent_step_id, step_kind, state, attempt_count, input_json, output_json, error_json,
                           correlation_id, causation_id, actor_type, actor_id, created_at, updated_at
                    FROM execution_steps
                    WHERE session_id = %s
                    ORDER BY created_at ASC, step_id ASC
                    """,
                    (sid,),
                )
                rows = cur.fetchall()
        return [self._step_from_db_row(row) for row in rows]

    def append_tool_receipt(
        self,
        session_id: str,
        step_id: str,
        tool_name: str,
        action_kind: str,
        target_ref: str,
        receipt_json: dict[str, object] | None = None,
    ) -> ToolReceipt:
        sid = str(session_id or "")
        stid = str(step_id or "")
        if not sid or not self.get_session(sid):
            raise KeyError(f"unknown session: {sid}")
        row = ToolReceipt(
            receipt_id=str(uuid.uuid4()),
            session_id=sid,
            step_id=stid,
            tool_name=str(tool_name or "tool"),
            action_kind=str(action_kind or "action"),
            target_ref=str(target_ref or ""),
            receipt_json=dict(receipt_json or {}),
            created_at=now_utc_iso(),
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tool_receipts
                    (receipt_id, session_id, step_id, tool_name, action_kind, target_ref, receipt_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row.receipt_id,
                        row.session_id,
                        row.step_id,
                        row.tool_name,
                        row.action_kind,
                        row.target_ref,
                        self._json_value(row.receipt_json),
                        row.created_at,
                    ),
                )
        return row

    def receipts_for(self, session_id: str) -> list[ToolReceipt]:
        sid = str(session_id or "")
        if not sid:
            return []
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT receipt_id, session_id, step_id, tool_name, action_kind, target_ref, receipt_json, created_at
                    FROM tool_receipts
                    WHERE session_id = %s
                    ORDER BY created_at ASC, receipt_id ASC
                    """,
                    (sid,),
                )
                rows = cur.fetchall()
        return [self._receipt_from_db_row(row) for row in rows]

    def get_receipt(self, receipt_id: str) -> ToolReceipt | None:
        rid = str(receipt_id or "")
        if not rid:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT receipt_id, session_id, step_id, tool_name, action_kind, target_ref, receipt_json, created_at
                    FROM tool_receipts
                    WHERE receipt_id = %s
                    """,
                    (rid,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return self._receipt_from_db_row(row)

    def append_run_cost(
        self,
        session_id: str,
        model_name: str,
        *,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
    ) -> RunCost:
        sid = str(session_id or "")
        if not sid or not self.get_session(sid):
            raise KeyError(f"unknown session: {sid}")
        row = RunCost(
            cost_id=str(uuid.uuid4()),
            session_id=sid,
            model_name=str(model_name or "unknown"),
            tokens_in=max(0, int(tokens_in)),
            tokens_out=max(0, int(tokens_out)),
            cost_usd=float(cost_usd),
            created_at=now_utc_iso(),
        )
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO run_costs
                    (cost_id, session_id, model_name, tokens_in, tokens_out, cost_usd, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row.cost_id,
                        row.session_id,
                        row.model_name,
                        row.tokens_in,
                        row.tokens_out,
                        row.cost_usd,
                        row.created_at,
                    ),
                )
        return row

    def run_costs_for(self, session_id: str) -> list[RunCost]:
        sid = str(session_id or "")
        if not sid:
            return []
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT cost_id, session_id, model_name, tokens_in, tokens_out, cost_usd, created_at
                    FROM run_costs
                    WHERE session_id = %s
                    ORDER BY created_at ASC, cost_id ASC
                    """,
                    (sid,),
                )
                rows = cur.fetchall()
        return [self._cost_from_db_row(row) for row in rows]

    def get_run_cost(self, cost_id: str) -> RunCost | None:
        cid = str(cost_id or "")
        if not cid:
            return None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT cost_id, session_id, model_name, tokens_in, tokens_out, cost_usd, created_at
                    FROM run_costs
                    WHERE cost_id = %s
                    """,
                    (cid,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return self._cost_from_db_row(row)
