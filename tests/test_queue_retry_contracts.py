from __future__ import annotations

import pytest

from app.domain.models import IntentSpecV3, ToolInvocationResult
from app.repositories.ledger import InMemoryExecutionLedgerRepository
from app.repositories.connector_bindings import InMemoryConnectorBindingRepository
from app.repositories.tool_registry import InMemoryToolRegistryRepository
from app.services.orchestrator import RewriteOrchestrator
from app.services.tool_execution import ToolExecutionService
from app.services.tool_runtime import ToolRuntimeService


def _build_retry_orchestrator(handler):
    ledger = InMemoryExecutionLedgerRepository()
    tool_runtime = ToolRuntimeService(
        tool_registry=InMemoryToolRegistryRepository(),
        connector_bindings=InMemoryConnectorBindingRepository(),
    )
    tool_runtime.upsert_tool(
        tool_name="flaky_tool",
        version="v1",
        input_schema_json={"type": "object"},
        output_schema_json={"type": "object"},
        policy_json={"builtin": False},
        approval_default="none",
        enabled=True,
    )
    tool_execution = ToolExecutionService(tool_runtime=tool_runtime)
    tool_execution.register_handler("flaky_tool", handler)
    orchestrator = RewriteOrchestrator(
        ledger=ledger,
        tool_execution=tool_execution,
    )
    return orchestrator, ledger


def _start_retry_step(
    orchestrator: RewriteOrchestrator,
    ledger: InMemoryExecutionLedgerRepository,
    *,
    max_attempts: int,
    retry_backoff_seconds: int,
):
    session = ledger.start_session(
        IntentSpecV3(
            principal_id="exec-1",
            goal="exercise retry runtime",
            task_type="retry_task",
            deliverable_type="retry_note",
            risk_class="low",
            approval_class="none",
            budget_class="low",
            allowed_tools=("flaky_tool",),
        )
    )
    step = ledger.start_step(
        session.session_id,
        "tool_call",
        input_json={
            "plan_id": "plan-retry",
            "plan_step_key": "step_flaky_tool",
            "tool_name": "flaky_tool",
            "action_kind": "flaky.execute",
            "failure_strategy": "retry",
            "max_attempts": max_attempts,
            "retry_backoff_seconds": retry_backoff_seconds,
            "depends_on": [],
            "input_keys": [],
            "output_keys": ["status"],
        },
    )
    queue_item = orchestrator._enqueue_rewrite_step(session.session_id, step.step_id)
    return session, step, queue_item


def test_retry_failure_strategy_requeues_a_failed_step_until_it_succeeds() -> None:
    calls = {"count": 0}

    def handler(request, definition):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary_failure")
        return ToolInvocationResult(
            tool_name=definition.tool_name,
            action_kind=str(request.action_kind or "flaky.execute") or "flaky.execute",
            target_ref="retry-target",
            output_json={"status": "ok"},
            receipt_json={"handler_key": definition.tool_name},
        )

    orchestrator, ledger = _build_retry_orchestrator(handler)
    session, step, queue_item = _start_retry_step(
        orchestrator,
        ledger,
        max_attempts=2,
        retry_backoff_seconds=0,
    )

    assert orchestrator.run_queue_item(queue_item.queue_id, lease_owner="worker") is None

    queued_step = ledger.get_step(step.step_id)
    assert queued_step is not None
    assert queued_step.state == "queued"
    assert queued_step.attempt_count == 1
    assert queued_step.error_json["reason"] == "retry_scheduled"
    assert queued_step.error_json["detail"] == "temporary_failure"
    queued_item = ledger.queue_for_session(session.session_id)[0]
    assert queued_item.state == "queued"
    assert queued_item.attempt_count == 1
    assert queued_item.last_error == "temporary_failure"
    assert queued_item.next_attempt_at is not None
    assert ledger.get_session(session.session_id).status == "queued"
    assert "step_retry_scheduled" in [row.name for row in ledger.events_for(session.session_id)]

    assert orchestrator.run_queue_item(queue_item.queue_id, lease_owner="worker") is None

    completed_step = ledger.get_step(step.step_id)
    assert completed_step is not None
    assert completed_step.state == "completed"
    assert completed_step.attempt_count == 2
    completed_item = ledger.queue_for_session(session.session_id)[0]
    assert completed_item.state == "done"
    assert completed_item.attempt_count == 2
    assert ledger.get_session(session.session_id).status == "completed"
    receipts = ledger.receipts_for(session.session_id)
    assert len(receipts) == 1
    assert receipts[0].tool_name == "flaky_tool"
    assert calls["count"] == 2


def test_retry_failure_strategy_exhausts_into_terminal_session_failure() -> None:
    def handler(request, definition):
        raise RuntimeError("still_broken")

    orchestrator, ledger = _build_retry_orchestrator(handler)
    session, step, queue_item = _start_retry_step(
        orchestrator,
        ledger,
        max_attempts=2,
        retry_backoff_seconds=0,
    )

    assert orchestrator.run_queue_item(queue_item.queue_id, lease_owner="worker") is None

    with pytest.raises(RuntimeError, match="still_broken"):
        orchestrator.run_queue_item(queue_item.queue_id, lease_owner="worker")

    failed_step = ledger.get_step(step.step_id)
    assert failed_step is not None
    assert failed_step.state == "failed"
    assert failed_step.attempt_count == 2
    assert failed_step.error_json["reason"] == "execution_failed"
    failed_item = ledger.queue_for_session(session.session_id)[0]
    assert failed_item.state == "failed"
    assert failed_item.attempt_count == 2
    assert failed_item.last_error == "still_broken"
    assert ledger.get_session(session.session_id).status == "failed"
    event_names = [row.name for row in ledger.events_for(session.session_id)]
    assert event_names.count("step_retry_scheduled") == 1
    assert "session_failed" in event_names
