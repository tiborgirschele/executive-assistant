from __future__ import annotations

import json
import uuid
from typing import Any, Sequence

from app.db import get_db
from app.planner.intent_compiler import compile_intent_spec_v2
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


def _coerce_json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except Exception:
            return {}
        if isinstance(loaded, dict):
            return dict(loaded)
    return {}


def _normalize_memory_text(text: str, *, limit: int = 1400) -> str:
    cleaned = " ".join(str(text or "").replace("\n", " ").split())
    return cleaned[:limit].strip()


def _looks_runtime_like(text: str) -> bool:
    sample = str(text or "").lower()
    if not sample:
        return True
    markers = (
        "traceback",
        "fatal event loop deadlock",
        "tool_call",
        '"role":',
        "[options:",
        "llm gateway",
    )
    return sum(1 for marker in markers if marker in sample) >= 2


def _build_memory_candidate_fact(
    *,
    objective: str,
    final_status: str,
    outcome: dict[str, Any],
) -> str:
    objective_text = _normalize_memory_text(objective, limit=700)
    if not objective_text:
        return ""
    result = _normalize_memory_text(str(outcome.get("result") or ""), limit=120)
    if final_status == "completed":
        tail = f" Outcome: {result}." if result else " Outcome: completed."
        return f"{objective_text}.{tail}"
    if final_status == "partial":
        blocked = _normalize_memory_text(str(outcome.get("blocked_reason") or ""), limit=120)
        if blocked:
            return f"{objective_text}. Pending gate: {blocked}."
        return f"{objective_text}. Pending approval or follow-up."
    return ""


def _load_session_context(session_id: str) -> dict[str, Any]:
    try:
        db = get_db()
        if not hasattr(db, "fetchone"):
            return {}
        row = db.fetchone(
            """
            SELECT tenant, intent_type, objective, intent_spec_json
            FROM execution_sessions
            WHERE session_id = %s
            LIMIT 1
            """,
            (str(session_id),),
        )
        return dict(row or {})
    except Exception:
        return {}


def _emit_finalize_memory_candidate(
    *,
    session_id: str,
    final_status: str,
    outcome: dict[str, Any] | None = None,
    last_error: str | None = None,
) -> None:
    if final_status not in {"completed", "partial"}:
        return
    if last_error:
        return
    session_row = _load_session_context(session_id)
    tenant = str((session_row or {}).get("tenant") or "").strip()
    if not tenant:
        return
    intent_type = str((session_row or {}).get("intent_type") or "").strip().lower() or "free_text"
    objective = str((session_row or {}).get("objective") or "")
    intent_spec = _coerce_json_dict((session_row or {}).get("intent_spec_json"))
    task_type = str(intent_spec.get("task_type") or "").strip().lower()
    domain = str(intent_spec.get("domain") or "").strip().lower()
    concept = task_type or domain or intent_type or "general"
    outcome_dict = dict(outcome or {})
    fact = _build_memory_candidate_fact(objective=objective, final_status=final_status, outcome=outcome_dict)
    fact = _normalize_memory_text(fact, limit=1600)
    if not fact or _looks_runtime_like(fact):
        return
    payload = {
        "source": "session_finalize",
        "status": final_status,
        "intent_type": intent_type,
        "task_type": task_type,
        "domain": domain,
        "result": str(outcome_dict.get("result") or "")[:120],
    }
    try:
        from app.planner.memory_candidates import emit_memory_candidate

        candidate_id = str(
            emit_memory_candidate(
                tenant_key=tenant,
                source_session_id=session_id,
                concept=concept[:120],
                candidate_fact=fact,
                confidence=0.72 if final_status == "completed" else 0.62,
                sensitivity="internal",
                sharing_policy="private",
                payload=payload,
            )
            or ""
        )
    except Exception:
        candidate_id = ""
    if candidate_id:
        append_execution_event(
            session_id,
            event_type="memory_candidate_emitted",
            message="Memory candidate emitted from finalized session.",
            payload={"memory_candidate_id": candidate_id, "concept": concept[:120]},
        )


def compile_intent_spec(
    *,
    text: str,
    tenant: str = "",
    chat_id: int | None = None,
    has_url: bool | None = None,
) -> dict[str, Any]:
    return compile_intent_spec_v2(
        text=str(text or ""),
        tenant=str(tenant or ""),
        chat_id=int(chat_id) if chat_id is not None else None,
        has_url=bool(has_url),
    )


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
            if isinstance(step, dict):
                meta_preconditions = dict(preconditions or {})
                meta_evidence = dict(evidence or {})
                if (step or {}).get("budget_policy"):
                    meta_preconditions["budget_policy"] = str((step or {}).get("budget_policy"))
                if (step or {}).get("approval_default"):
                    meta_preconditions["approval_default"] = str((step or {}).get("approval_default"))
                if (step or {}).get("task_type"):
                    meta_evidence["task_type"] = str((step or {}).get("task_type"))
                provider_candidates = list((step or {}).get("provider_candidates") or [])
                if provider_candidates:
                    meta_evidence["provider_candidates"] = [str(x) for x in provider_candidates if str(x or "").strip()]
                if (step or {}).get("output_artifact_type"):
                    meta_evidence["output_artifact_type"] = str((step or {}).get("output_artifact_type"))
                preconditions = meta_preconditions
                evidence = meta_evidence
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
        _emit_finalize_memory_candidate(
            session_id=session_id,
            final_status=final_status,
            outcome=dict(outcome or {}),
            last_error=last_error,
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
