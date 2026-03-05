from __future__ import annotations

from app.planner.task_registry import task_or_none
from app.skills.capability_registry import capability_or_raise, capabilities_for_task


def build_capability_plan(task_type: str, preferred: str | None = None) -> dict[str, object]:
    task = str(task_type or "").strip().lower()
    if not task:
        return {"ok": False, "status": "missing_task_type"}

    task_contract = task_or_none(task)
    candidates = list(capabilities_for_task(task))
    if not candidates:
        return {
            "ok": False,
            "status": "no_capability_for_task",
            "task_type": task,
            "primary": None,
            "fallbacks": [],
            "candidates": [],
        }

    pref = str(preferred or "").strip().lower()
    ranked = list(tuple((task_contract.provider_priority if task_contract else tuple(candidates))))
    for cap in candidates:
        if cap not in ranked:
            ranked.append(cap)
    if pref and pref in candidates:
        ranked = [pref] + [x for x in ranked if x != pref]

    primary = ranked[0]
    fallbacks = [x for x in ranked[1:] if x in candidates]
    cap = capability_or_raise(primary)
    return {
        "ok": True,
        "status": "planned",
        "task_type": task,
        "primary": cap.key,
        "primary_invocation_method": cap.invocation_method,
        "fallbacks": fallbacks,
        "candidates": candidates,
        "task_contract_key": task_contract.key if task_contract else None,
        "task_contract_approval_default": task_contract.approval_default if task_contract else None,
        "task_contract_output_artifact_type": task_contract.output_artifact_type if task_contract else None,
        "task_contract_budget_policy": task_contract.budget_policy if task_contract else None,
    }


__all__ = ["build_capability_plan"]
