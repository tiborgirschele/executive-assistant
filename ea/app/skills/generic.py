from __future__ import annotations

from typing import Any, Callable

from app.planner.provider_outcomes import record_provider_outcome
from app.skills.capability_router import build_capability_plan


def build_generic_skill_handler(
    skill_key: str,
    capabilities: tuple[str, ...],
    *,
    planning_task_type: str | None = None,
    runtime_execution_ops: tuple[str, ...] = (),
) -> Callable[..., dict[str, Any]]:
    key = str(skill_key or "").strip().lower()
    caps = tuple(str(x or "").strip().lower() for x in capabilities if str(x or "").strip())
    task_type = str(planning_task_type or key).strip().lower()
    runtime_ops = {str(x or "").strip().lower() for x in runtime_execution_ops if str(x or "").strip()}
    planning_ops = {"plan", "build", "compile"}
    staging_ops = {"stage", "dispatch", "polish", "generate"}

    def _run_operation(
        *,
        operation: str,
        tenant: str,
        chat_id: int,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        preferred = str((payload or {}).get("preferred_capability") or "").strip().lower() or None
        plan = build_capability_plan(task_type, preferred=preferred)
        op = str(operation or "").strip().lower()
        if op in runtime_ops:
            status = "executed"
        elif op in planning_ops:
            status = "planned"
        elif op in staging_ops:
            status = "staged"
        else:
            status = "not_implemented"
        ok = bool(plan.get("ok")) and status in {"planned", "staged", "executed"}
        artifacts: list[dict[str, Any]] = []
        if ok and status == "executed":
            notes = str(((payload or {}).get("notes") if isinstance(payload, dict) else "") or "").strip()
            artifacts.append(
                {
                    "artifact_type": str(plan.get("task_contract_output_artifact_type") or "execution_artifact"),
                    "summary": "Deterministic generic-skill execution artifact",
                    "preview": notes[:220] if notes else f"{key}:{op} executed",
                }
            )
        execution_mode = str(((payload or {}).get("execution_mode") if isinstance(payload, dict) else "") or "").strip().lower()
        provider_executed = bool(
            ((payload or {}).get("provider_executed") if isinstance(payload, dict) else False)
            or execution_mode in {"provider", "runtime", "live"}
        )
        primary = str((plan or {}).get("primary") or "").strip().lower()
        if primary:
            if status == "executed" and ok:
                source = "skill_runtime" if provider_executed else "synthetic_preview"
                outcome_status = "success" if provider_executed else "synthetic_preview"
                score_delta = 1 if provider_executed else 0
                record_provider_outcome(
                    tenant_key=str(tenant or ""),
                    provider_key=primary,
                    task_type=task_type,
                    outcome_status=outcome_status,
                    score_delta=score_delta,
                    source=source,
                )
            elif status in {"not_implemented"} or not ok:
                record_provider_outcome(
                    tenant_key=str(tenant or ""),
                    provider_key=primary,
                    task_type=task_type,
                    outcome_status="failed",
                    score_delta=-1,
                    source="skill_runtime",
                )
        message = (
            "Skill orchestration plan generated."
            if status == "planned"
            else "Skill operation executed."
            if status == "executed"
            else "Skill orchestration request staged."
            if status == "staged"
            else "Skill contract exists but implementation is pending."
        )
        return {
            "ok": ok,
            "status": status,
            "skill": key,
            "task_type": task_type,
            "operation": op,
            "tenant": str(tenant or ""),
            "chat_id": int(chat_id),
            "payload": dict(payload or {}),
            "capabilities": list(caps),
            "plan": plan,
            "artifacts": artifacts,
            "message": message,
        }

    return _run_operation


__all__ = ["build_generic_skill_handler"]
