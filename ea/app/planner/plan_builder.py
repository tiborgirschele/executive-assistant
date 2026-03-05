from __future__ import annotations

from typing import Any


def _step(
    step_key: str,
    step_title: str,
    *,
    preconditions: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "step_key": str(step_key or "").strip(),
        "step_title": str(step_title or "").strip(),
        "preconditions_json": dict(preconditions or {}),
        "evidence_json": dict(evidence or {}),
    }


def build_task_plan_steps(*, intent_spec: dict[str, Any]) -> list[dict[str, Any]]:
    spec = dict(intent_spec or {})
    has_url = bool(spec.get("has_url"))
    autonomy = str(spec.get("autonomy_level") or "").strip().lower()
    domain = str(spec.get("domain") or "").strip().lower()
    task_type = str(spec.get("task_type") or "").strip().lower()

    steps: list[dict[str, Any]] = [_step("compile_intent", "Compile Intent")]

    if has_url:
        steps.append(
            _step(
                "gather_evidence",
                "Gather URL Evidence",
                preconditions={"requires_url": True},
            )
        )

    if task_type in {"travel_rescue", "trip_context_pack"} or domain == "travel":
        steps.append(
            _step(
                "analyze_trip_commitment",
                "Analyze Trip Commitment",
                preconditions={"requires_domain": "travel"},
                evidence={"sources": ["calendar", "mail", "travel_dossier"]},
            )
        )
        steps.append(
            _step(
                "compare_travel_options",
                "Compare Travel Options",
                preconditions={"trip_context_ready": True},
            )
        )
    elif domain == "finance":
        steps.append(
            _step(
                "verify_payment_context",
                "Verify Payment Context",
                preconditions={"requires_domain": "finance"},
                evidence={"sources": ["billing", "approvals", "ledger"]},
            )
        )
    elif domain == "project":
        steps.append(
            _step(
                "gather_project_context",
                "Gather Project Context",
                preconditions={"requires_domain": "project"},
                evidence={"sources": ["calendar", "mail", "project_dossier"]},
            )
        )
    elif domain == "health":
        steps.append(
            _step(
                "review_health_context",
                "Review Health Context",
                preconditions={"requires_domain": "health"},
                evidence={"sources": ["appointments", "health_dossier"]},
            )
        )

    if autonomy == "approval_required":
        steps.append(
            _step(
                "safety_gate",
                "Safety Gate",
                preconditions={"approval_required": True},
            )
        )

    steps.extend(
        [
            _step("execute_intent", "Execute Intent"),
            _step("render_reply", "Render Reply"),
        ]
    )
    return steps


__all__ = ["build_task_plan_steps"]
