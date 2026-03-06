from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Dict, List, Protocol

from app.domain.models import (
    ExecutionEvent,
    ExecutionSession,
    ExecutionStep,
    IntentSpecV3,
    RunCost,
    ToolReceipt,
    now_utc_iso,
)


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
        ...

    def update_step(
        self,
        step_id: str,
        *,
        state: str,
        output_json: dict[str, object] | None = None,
        error_json: dict[str, object] | None = None,
    ) -> ExecutionStep | None:
        ...

    def steps_for(self, session_id: str) -> list[ExecutionStep]:
        ...

    def append_tool_receipt(
        self,
        session_id: str,
        step_id: str,
        tool_name: str,
        action_kind: str,
        target_ref: str,
        receipt_json: dict[str, object] | None = None,
    ) -> ToolReceipt:
        ...

    def receipts_for(self, session_id: str) -> list[ToolReceipt]:
        ...

    def get_receipt(self, receipt_id: str) -> ToolReceipt | None:
        ...

    def append_run_cost(
        self,
        session_id: str,
        model_name: str,
        *,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
    ) -> RunCost:
        ...

    def run_costs_for(self, session_id: str) -> list[RunCost]:
        ...

    def get_run_cost(self, cost_id: str) -> RunCost | None:
        ...


class InMemoryExecutionLedgerRepository:
    def __init__(self) -> None:
        self._sessions: Dict[str, ExecutionSession] = {}
        self._events: Dict[str, List[ExecutionEvent]] = {}
        self._steps: Dict[str, ExecutionStep] = {}
        self._step_order: Dict[str, List[str]] = {}
        self._receipts: Dict[str, ToolReceipt] = {}
        self._receipt_order: Dict[str, List[str]] = {}
        self._costs: Dict[str, RunCost] = {}
        self._cost_order: Dict[str, List[str]] = {}

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
        self._step_order[session.session_id] = []
        self._receipt_order[session.session_id] = []
        self._cost_order[session.session_id] = []
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
        if sid not in self._sessions:
            raise KeyError(f"unknown session: {sid}")
        ts = now_utc_iso()
        step = ExecutionStep(
            step_id=str(uuid.uuid4()),
            session_id=sid,
            parent_step_id=parent_step_id,
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
        self._steps[step.step_id] = step
        self._step_order.setdefault(sid, []).append(step.step_id)
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
        step = self._steps.get(sid)
        if not step:
            return None
        updated = replace(
            step,
            state=str(state or step.state),
            output_json=dict(output_json or step.output_json),
            error_json=dict(error_json or step.error_json),
            updated_at=now_utc_iso(),
        )
        self._steps[updated.step_id] = updated
        return updated

    def steps_for(self, session_id: str) -> list[ExecutionStep]:
        sid = str(session_id or "")
        return [self._steps[i] for i in self._step_order.get(sid, []) if i in self._steps]

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
        if sid not in self._sessions:
            raise KeyError(f"unknown session: {sid}")
        step = self._steps.get(str(step_id or ""))
        if not step or step.session_id != sid:
            raise KeyError(f"unknown step for session: {step_id}")
        row = ToolReceipt(
            receipt_id=str(uuid.uuid4()),
            session_id=sid,
            step_id=step.step_id,
            tool_name=str(tool_name or "tool"),
            action_kind=str(action_kind or "action"),
            target_ref=str(target_ref or ""),
            receipt_json=dict(receipt_json or {}),
            created_at=now_utc_iso(),
        )
        self._receipts[row.receipt_id] = row
        self._receipt_order.setdefault(sid, []).append(row.receipt_id)
        return row

    def receipts_for(self, session_id: str) -> list[ToolReceipt]:
        sid = str(session_id or "")
        return [self._receipts[i] for i in self._receipt_order.get(sid, []) if i in self._receipts]

    def get_receipt(self, receipt_id: str) -> ToolReceipt | None:
        return self._receipts.get(str(receipt_id or ""))

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
        if sid not in self._sessions:
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
        self._costs[row.cost_id] = row
        self._cost_order.setdefault(sid, []).append(row.cost_id)
        return row

    def run_costs_for(self, session_id: str) -> list[RunCost]:
        sid = str(session_id or "")
        return [self._costs[i] for i in self._cost_order.get(sid, []) if i in self._costs]

    def get_run_cost(self, cost_id: str) -> RunCost | None:
        return self._costs.get(str(cost_id or ""))
