from __future__ import annotations

from app.domain.models import TaskContract, now_utc_iso
from app.repositories.task_contracts import InMemoryTaskContractRepository


def test_inmemory_task_contracts_upsert_get_list() -> None:
    repo = InMemoryTaskContractRepository()
    row = repo.upsert(
        TaskContract(
            task_key="rewrite_text",
            deliverable_type="rewrite_note",
            default_risk_class="low",
            default_approval_class="none",
            allowed_tools=("artifact_repository",),
            evidence_requirements=(),
            memory_write_policy="reviewed_only",
            budget_policy_json={"class": "low"},
            updated_at=now_utc_iso(),
        )
    )
    assert row.task_key == "rewrite_text"
    found = repo.get("rewrite_text")
    assert found is not None
    assert found.deliverable_type == "rewrite_note"
    listed = repo.list_all(limit=10)
    assert len(listed) == 1
