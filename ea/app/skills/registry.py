from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.skills import payments
from app.skills.capability_registry import capability_or_raise


SkillHandler = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class SkillContract:
    key: str
    display_name: str
    operations: tuple[str, ...]
    handler: SkillHandler
    capabilities: tuple[str, ...]


SKILL_REGISTRY: dict[str, SkillContract] = {
    "payments": SkillContract(
        key="payments",
        display_name="Payments",
        operations=("generate_demo_draft", "handle_action"),
        handler=payments.run_operation,
        capabilities=("approvethis",),
    ),
}


def skill_or_raise(skill_key: str) -> SkillContract:
    key = str(skill_key or "").strip().lower()
    if key not in SKILL_REGISTRY:
        raise ValueError(f"unknown_skill:{skill_key}")
    return SKILL_REGISTRY[key]


def list_skills() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in sorted(SKILL_REGISTRY.keys()):
        contract = SKILL_REGISTRY[key]
        capability_rows = []
        for cap_key in contract.capabilities:
            cap = capability_or_raise(cap_key)
            capability_rows.append(
                {
                    "key": cap.key,
                    "display_name": cap.display_name,
                    "invocation_method": cap.invocation_method,
                    "task_types": list(cap.task_types),
                }
            )
        out.append(
            {
                "key": contract.key,
                "display_name": contract.display_name,
                "operations": list(contract.operations),
                "capabilities": capability_rows,
            }
        )
    return out
