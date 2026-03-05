from __future__ import annotations

import json
from typing import Any


def _safe_json(value: Any) -> str:
    if value is None:
        return "{}"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps({"value": value})
    return json.dumps({"value": str(value)})


def _get_db():
    from app.db import get_db

    return get_db()


def emit_memory_candidate(
    *,
    tenant_key: str,
    source_session_id: str | None = None,
    concept: str,
    candidate_fact: str,
    confidence: float = 0.5,
    sensitivity: str = "internal",
    sharing_policy: str = "private",
    payload: dict[str, Any] | None = None,
) -> str:
    tenant = str(tenant_key or "").strip()
    concept_key = str(concept or "").strip().lower()
    fact = str(candidate_fact or "").strip()
    if not tenant or not concept_key or not fact:
        return ""
    conf = max(0.0, min(1.0, float(confidence)))
    try:
        db = _get_db()
        row = db.fetchone(
            """
            INSERT INTO memory_candidates (
                tenant_key,
                source_session_id,
                concept,
                candidate_fact,
                confidence,
                sensitivity,
                sharing_policy,
                review_status,
                payload_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s::jsonb)
            RETURNING memory_candidate_id
            """,
            (
                tenant,
                str(source_session_id or "") if source_session_id else None,
                concept_key[:120],
                fact[:2000],
                conf,
                str(sensitivity or "internal")[:60],
                str(sharing_policy or "private")[:60],
                _safe_json(payload or {}),
            ),
        )
        return str((row or {}).get("memory_candidate_id") or "")
    except Exception:
        return ""


def mark_memory_candidate_review(
    *,
    memory_candidate_id: str,
    review_status: str,
    reviewer: str = "",
    review_note: str = "",
) -> bool:
    candidate_id = str(memory_candidate_id or "").strip()
    if not candidate_id:
        return False
    status = str(review_status or "").strip().lower()
    if status not in {"approved", "rejected", "pending"}:
        status = "pending"
    try:
        db = _get_db()
        db.execute(
            """
            UPDATE memory_candidates
            SET review_status = %s,
                reviewer = %s,
                review_note = %s,
                reviewed_at = CASE WHEN %s IN ('approved', 'rejected') THEN NOW() ELSE reviewed_at END
            WHERE memory_candidate_id = %s
            """,
            (
                status,
                str(reviewer or "")[:120] if reviewer else None,
                str(review_note or "")[:2000] if review_note else None,
                status,
                candidate_id,
            ),
        )
        return True
    except Exception:
        return False


def list_memory_candidates(
    *,
    tenant_key: str,
    review_status: str = "approved",
    limit: int = 100,
) -> list[dict[str, Any]]:
    tenant = str(tenant_key or "").strip()
    if not tenant:
        return []
    status = str(review_status or "approved").strip().lower()
    cap = max(1, min(1000, int(limit)))
    try:
        db = _get_db()
        rows = db.fetchall(
            """
            SELECT memory_candidate_id, concept, candidate_fact, confidence, sensitivity,
                   sharing_policy, review_status, payload_json, created_at, reviewed_at
            FROM memory_candidates
            WHERE tenant_key = %s AND review_status = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (tenant, status, cap),
        )
        return list(rows or [])
    except Exception:
        return []


__all__ = ["emit_memory_candidate", "mark_memory_candidate_review", "list_memory_candidates"]
