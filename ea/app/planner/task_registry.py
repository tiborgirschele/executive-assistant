from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TaskContract:
    key: str
    description: str
    provider_priority: tuple[str, ...]
    output_artifact_type: str
    approval_default: str
    budget_policy: str


TASK_REGISTRY: dict[str, TaskContract] = {
    "travel_rescue": TaskContract(
        key="travel_rescue",
        description="Assess trip risk/cost and prepare reroute or rebook options.",
        provider_priority=("oneair", "avomap", "browseract"),
        output_artifact_type="travel_decision_pack",
        approval_default="advisory",
        budget_policy="travel_sidecar_daily",
    ),
    "trip_context_pack": TaskContract(
        key="trip_context_pack",
        description="Build contextual trip prep artifact with sidecar enrichments.",
        provider_priority=("oneair", "avomap", "one_min_ai", "ai_magicx"),
        output_artifact_type="trip_context_pack",
        approval_default="advisory",
        budget_policy="travel_sidecar_daily",
    ),
    "collect_structured_intake": TaskContract(
        key="collect_structured_intake",
        description="Collect structured intake via lightweight or rich form flows.",
        provider_priority=("involve_me", "metasurvey", "apix_drive"),
        output_artifact_type="intake_packet",
        approval_default="none",
        budget_policy="intake_quota",
    ),
    "guided_intake": TaskContract(
        key="guided_intake",
        description="Run guided intake for external contributors.",
        provider_priority=("involve_me", "metasurvey", "apix_drive"),
        output_artifact_type="intake_packet",
        approval_default="none",
        budget_policy="intake_quota",
    ),
    "compile_prompt_pack": TaskContract(
        key="compile_prompt_pack",
        description="Compile structured prompts for downstream multimodal workflows.",
        provider_priority=("prompting_systems", "paperguide", "vizologi"),
        output_artifact_type="prompt_pack",
        approval_default="none",
        budget_policy="content_sidecar_daily",
    ),
    "polish_human_tone": TaskContract(
        key="polish_human_tone",
        description="Polish approved drafts for readability and human tone.",
        provider_priority=("undetectable",),
        output_artifact_type="polished_draft",
        approval_default="none",
        budget_policy="tone_polish_daily",
    ),
    "generate_multimodal_support_asset": TaskContract(
        key="generate_multimodal_support_asset",
        description="Produce non-blocking support assets for communication/prep.",
        provider_priority=("one_min_ai", "ai_magicx", "peekshot"),
        output_artifact_type="support_asset",
        approval_default="none",
        budget_policy="secondary_ai_daily",
    ),
}


def task_or_none(task_key: str) -> TaskContract | None:
    key = str(task_key or "").strip().lower()
    if not key:
        return None
    return TASK_REGISTRY.get(key)


def task_or_raise(task_key: str) -> TaskContract:
    task = task_or_none(task_key)
    if not task:
        raise ValueError(f"unknown_task_contract:{task_key}")
    return task


def list_task_contracts() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in sorted(TASK_REGISTRY.keys()):
        task = TASK_REGISTRY[key]
        out.append(
            {
                "key": task.key,
                "description": task.description,
                "provider_priority": list(task.provider_priority),
                "output_artifact_type": task.output_artifact_type,
                "approval_default": task.approval_default,
                "budget_policy": task.budget_policy,
            }
        )
    return out


__all__ = ["TaskContract", "TASK_REGISTRY", "task_or_none", "task_or_raise", "list_task_contracts"]
