from __future__ import annotations

from app.services.planner import PlannerService
from app.services.task_contracts import TaskContractService
from app.repositories.task_contracts import InMemoryTaskContractRepository


def test_planner_uses_task_contract_defaults() -> None:
    contracts = TaskContractService(InMemoryTaskContractRepository())
    contracts.upsert_contract(
        task_key="rewrite_text",
        deliverable_type="rewrite_note",
        default_risk_class="low",
        default_approval_class="manager",
        allowed_tools=("rewrite_store",),
        memory_write_policy="reviewed_only",
        budget_policy_json={"class": "low"},
    )
    planner = PlannerService(contracts)
    intent, plan = planner.build_plan(task_key="rewrite_text", principal_id="exec-1", goal="rewrite")
    assert intent.task_type == "rewrite_text"
    assert intent.approval_class == "manager"
    assert len(plan.steps) == 1
    assert plan.steps[0].approval_required is True
