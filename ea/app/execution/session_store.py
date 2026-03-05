from __future__ import annotations

import json
import re
import time
import uuid
import hashlib
from typing import Any, Sequence

from app.db import get_db
from app.planner.plan_builder import build_task_plan_steps

_STATUS_VALUES = {"queued", "running", "completed", "failed", "skipped"}


def _safe_json(value: Any) -> str:
    if value is None:
        return "{}"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps({"value": value})
    return json.dumps({"value": str(value)})


def _normalize_status(status: str, *, default: str = "queued") -> str:
    raw = str(status or "").strip().lower()
    if raw in _STATUS_VALUES:
        return raw
    return default


def _domain_from_text(text_lower: str) -> str:
    if any(k in text_lower for k in ("pay", "invoice", "iban", "transfer", "refund", "budget", "cost")):
        return "finance"
    if any(k in text_lower for k in ("trip", "flight", "hotel", "airport", "layover", "travel", "route")):
        return "travel"
    if any(k in text_lower for k in ("meeting", "project", "deadline", "proposal", "roadmap", "deliverable")):
        return "project"
    if any(k in text_lower for k in ("health", "doctor", "therapy", "med", "appointment", "symptom")):
        return "health"
    return "general"


def compile_intent_spec(
    *,
    text: str,
    tenant: str = "",
    chat_id: int | None = None,
    has_url: bool | None = None,
) -> dict[str, Any]:
    raw = str(text or "").strip()
    text_lower = raw.lower()
    url_present = bool(has_url) or bool(re.search(r"https?://", raw))
    high_risk = any(
        k in text_lower
        for k in (
            "pay",
            "transfer",
            "book",
            "cancel",
            "delete",
            "terminate",
            "sign",
            "approve",
        )
    )
    question_like = raw.endswith("?") or any(
        w in text_lower for w in ("what", "why", "how", "when", "where", "summarize", "explain")
    )
    domain = _domain_from_text(text_lower)
    deadline_hint = (
        "urgent"
        if any(k in text_lower for k in ("urgent", "asap", "today", "now", "immediately"))
        else "normal"
    )
    approval_class = "explicit_callback_required" if high_risk else "none"
    risk_class = "high_impact_action" if high_risk else "routine_assistive"
    deliverable_type = "answer_now" if question_like else "execute_or_plan"
    budget_class = "high_guardrail" if high_risk else "standard"
    evidence_requirements: list[str] = []
    if url_present:
        evidence_requirements.append("url_evidence")
    if domain == "finance":
        evidence_requirements.append("payment_context")
    if domain == "travel":
        evidence_requirements.append("travel_context")
    if not evidence_requirements:
        evidence_requirements.append("user_request_context")
    source_refs = re.findall(r"https?://[^\s]+", raw) if url_present else []
    objective = raw[:1200]
    commitment_key = ""
    if domain in {"travel", "finance", "project", "health"}:
        digest = hashlib.sha1(objective.encode("utf-8", errors="ignore")).hexdigest()[:12]
        commitment_key = f"{domain}:{str(tenant or '')}:{digest}"
    return {
        "intent_type": "url_analysis" if url_present else "free_text",
        "objective": objective,
        "domain": domain,
        "deliverable": deliverable_type,
        "deliverable_type": deliverable_type,
        "autonomy_level": "approval_required" if high_risk else "assistive",
        "approval_class": approval_class,
        "risk_level": "high" if high_risk else "normal",
        "risk_class": risk_class,
        "budget_class": budget_class,
        "deadline_hint": deadline_hint,
        "has_url": url_present,
        "evidence_requirements": evidence_requirements,
        "source_refs": source_refs,
        "stakeholders": [],
        "output_contract": {"format": "telegram_message", "style": "concise", "max_chars": 3500},
        "commitment_key": commitment_key,
        "tenant": str(tenant or ""),
        "chat_id": int(chat_id) if chat_id is not None else None,
        "compiled_at_epoch_s": int(time.time()),
    }


def build_plan_steps(*, intent_spec: dict[str, Any]) -> list[dict[str, Any]]:
    return build_task_plan_steps(intent_spec=dict(intent_spec or {}))


def append_execution_event(
    session_id: str,
    *,
    event_type: str,
    message: str = "",
    level: str = "info",
    payload: dict[str, Any] | None = None,
) -> None:
    if not session_id:
        return
    try:
        db = get_db()
        db.execute(
            """
            INSERT INTO execution_events (session_id, level, event_type, message, payload_json)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                str(session_id),
                str(level or "info"),
                str(event_type or "event"),
                str(message or ""),
                _safe_json(payload or {}),
            ),
        )
    except Exception:
        return


def create_approval_gate(
    *,
    session_id: str,
    tenant: str,
    chat_id: int | None,
    approval_class: str = "explicit_callback_required",
    action_id: str | None = None,
    decision_payload: dict[str, Any] | None = None,
) -> str | None:
    if not session_id:
        return None
    try:
        db = get_db()
        gate_id = str(uuid.uuid4())
        db.execute(
            """
            INSERT INTO approval_gates (
                approval_gate_id,
                session_id,
                tenant,
                chat_id,
                approval_class,
                decision_status,
                action_id,
                decision_payload_json
            )
            VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s::jsonb)
            """,
            (
                gate_id,
                str(session_id),
                str(tenant or ""),
                int(chat_id) if chat_id is not None else None,
                str(approval_class or "explicit_callback_required"),
                str(action_id or "") if action_id else None,
                _safe_json(decision_payload or {}),
            ),
        )
        return gate_id
    except Exception:
        return None


def attach_approval_gate_action(approval_gate_id: str, action_id: str) -> None:
    if not approval_gate_id or not action_id:
        return
    try:
        db = get_db()
        db.execute(
            """
            UPDATE approval_gates
            SET action_id = %s,
                updated_at = NOW()
            WHERE approval_gate_id = %s
            """,
            (str(action_id), str(approval_gate_id)),
        )
    except Exception:
        return


def mark_approval_gate_decision(
    approval_gate_id: str,
    *,
    decision_status: str,
    decision_payload: dict[str, Any] | None = None,
) -> None:
    if not approval_gate_id:
        return
    status = str(decision_status or "").strip().lower() or "pending"
    try:
        db = get_db()
        db.execute(
            """
            UPDATE approval_gates
            SET decision_status = %s,
                decision_payload_json = CASE
                    WHEN %s::jsonb = '{}'::jsonb THEN decision_payload_json
                    ELSE %s::jsonb
                END,
                decided_at = CASE
                    WHEN %s IN ('approved','rejected','cancelled','expired','staging_failed') THEN COALESCE(decided_at, NOW())
                    ELSE decided_at
                END,
                updated_at = NOW()
            WHERE approval_gate_id = %s
            """,
            (
                status,
                _safe_json(decision_payload or {}),
                _safe_json(decision_payload or {}),
                status,
                str(approval_gate_id),
            ),
        )
    except Exception:
        return


def create_execution_session(
    *,
    tenant: str,
    chat_id: int | None,
    intent_spec: dict[str, Any],
    plan_steps: Sequence[dict[str, Any]],
    source: str = "telegram_free_text",
    correlation_id: str | None = None,
) -> str | None:
    try:
        db = get_db()
        session_id = str(uuid.uuid4())
        objective = str((intent_spec or {}).get("objective") or "")[:1200]
        intent_type = str((intent_spec or {}).get("intent_type") or "free_text")
        db.execute(
            """
            INSERT INTO execution_sessions (
                session_id,
                tenant,
                source,
                chat_id,
                intent_type,
                objective,
                intent_spec_json,
                status,
                correlation_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, 'queued', %s)
            """,
            (
                session_id,
                str(tenant or ""),
                str(source or "telegram_free_text"),
                int(chat_id) if chat_id is not None else None,
                intent_type,
                objective,
                _safe_json(intent_spec or {}),
                str(correlation_id or ""),
            ),
        )
        for idx, step in enumerate(plan_steps or [], start=1):
            step_key = str((step or {}).get("step_key") or f"step_{idx}")
            step_title = str((step or {}).get("step_title") or step_key)
            preconditions = (step or {}).get("preconditions_json") if isinstance(step, dict) else {}
            evidence = (step or {}).get("evidence_json") if isinstance(step, dict) else {}
            db.execute(
                """
                INSERT INTO execution_steps (
                    step_id,
                    session_id,
                    step_order,
                    step_key,
                    step_title,
                    status,
                    preconditions_json,
                    evidence_json
                )
                VALUES (%s, %s, %s, %s, %s, 'queued', %s::jsonb, %s::jsonb)
                """,
                (
                    str(uuid.uuid4()),
                    session_id,
                    int(idx),
                    step_key,
                    step_title,
                    _safe_json(preconditions),
                    _safe_json(evidence),
                ),
            )
        append_execution_event(
            session_id,
            event_type="session_created",
            message="Execution session created.",
            payload={"step_count": len(list(plan_steps or []))},
        )
        return session_id
    except Exception:
        return None


def mark_execution_session_running(session_id: str) -> None:
    if not session_id:
        return
    try:
        db = get_db()
        db.execute(
            """
            UPDATE execution_sessions
            SET status = 'running',
                started_at = COALESCE(started_at, NOW()),
                updated_at = NOW()
            WHERE session_id = %s
            """,
            (str(session_id),),
        )
        append_execution_event(
            session_id,
            event_type="session_running",
            message="Execution session marked running.",
        )
    except Exception:
        return


def mark_execution_step_status(
    session_id: str,
    step_key: str,
    status: str,
    *,
    result: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    error_text: str | None = None,
) -> None:
    if not session_id or not step_key:
        return
    st = _normalize_status(status)
    try:
        db = get_db()
        result_json = _safe_json(result or {})
        evidence_json = _safe_json(evidence or {})
        db.execute(
            """
            UPDATE execution_steps
            SET status = %s,
                result_json = CASE WHEN %s::jsonb = '{}'::jsonb THEN result_json ELSE %s::jsonb END,
                evidence_json = CASE WHEN %s::jsonb = '{}'::jsonb THEN evidence_json ELSE %s::jsonb END,
                error_text = %s,
                started_at = CASE WHEN %s = 'running' AND started_at IS NULL THEN NOW() ELSE started_at END,
                finished_at = CASE WHEN %s IN ('completed','failed','skipped') THEN NOW() ELSE finished_at END,
                updated_at = NOW()
            WHERE session_id = %s AND step_key = %s
            """,
            (
                st,
                result_json,
                result_json,
                evidence_json,
                evidence_json,
                str(error_text or "") if error_text else None,
                st,
                st,
                str(session_id),
                str(step_key),
            ),
        )
    except Exception:
        return


def finalize_execution_session(
    session_id: str,
    *,
    status: str,
    outcome: dict[str, Any] | None = None,
    last_error: str | None = None,
) -> None:
    if not session_id:
        return
    final_status = str(status or "").strip().lower()
    if final_status not in {"completed", "failed", "cancelled", "partial"}:
        final_status = "failed" if last_error else "completed"
    try:
        db = get_db()
        db.execute(
            """
            UPDATE execution_sessions
            SET status = %s,
                outcome_json = %s::jsonb,
                last_error = %s,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE session_id = %s
            """,
            (
                final_status,
                _safe_json(outcome or {}),
                str(last_error or "") if last_error else None,
                str(session_id),
            ),
        )
        append_execution_event(
            session_id,
            level="error" if final_status == "failed" else "info",
            event_type="session_finalized",
            message="Execution session finalized.",
            payload={"status": final_status, "has_error": bool(last_error)},
        )
    except Exception:
        return


__all__ = [
    "append_execution_event",
    "attach_approval_gate_action",
    "build_plan_steps",
    "compile_intent_spec",
    "create_approval_gate",
    "create_execution_session",
    "finalize_execution_session",
    "mark_approval_gate_decision",
    "mark_execution_session_running",
    "mark_execution_step_status",
]
