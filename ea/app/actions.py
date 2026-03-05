import uuid, json
from app.db import get_db


def _requires_session_reference(action_type: str) -> bool:
    kind = str(action_type or "").strip().lower()
    return kind.startswith("skill:") or kind == "intent:approval_execute"


def _requires_approval_gate_reference(action_type: str) -> bool:
    return str(action_type or "").strip().lower() == "intent:approval_execute"


def create_action(
    tenant: str,
    action_type: str,
    payload: dict,
    days: int = 7,
    *,
    session_id: str | None = None,
    step_id: str | None = None,
    approval_gate_id: str | None = None,
) -> str:
    if _requires_session_reference(action_type) and not str(session_id or "").strip():
        return ""
    if _requires_approval_gate_reference(action_type) and not str(approval_gate_id or "").strip():
        return ""
    db = get_db()
    act_id = str(uuid.uuid4())
    safe_days = max(1, int(days))
    db.execute(
        """
        INSERT INTO typed_actions (
            id, tenant, action_type, payload_json, session_id, step_id, approval_gate_id, expires_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW() + (%s * INTERVAL '1 day'))
        """,
        (
            act_id,
            tenant,
            action_type,
            json.dumps(payload),
            str(session_id or "") if session_id else None,
            str(step_id or "") if step_id else None,
            str(approval_gate_id or "") if approval_gate_id else None,
            safe_days,
        ),
    )
    return act_id

def consume_action(tenant: str, act_id: str):
    db = get_db()
    action = db.fetchone("SELECT * FROM typed_actions WHERE id = %s AND tenant = %s AND is_consumed = FALSE AND expires_at > NOW() FOR UPDATE SKIP LOCKED", (act_id, tenant))
    if action:
        db.execute("UPDATE typed_actions SET is_consumed = TRUE WHERE id = %s", (act_id,))
        return action
    return None


def peek_action(tenant: str, act_id: str):
    db = get_db()
    return db.fetchone(
        "SELECT * FROM typed_actions WHERE id = %s AND tenant = %s AND is_consumed = FALSE AND expires_at > NOW()",
        (act_id, tenant),
    )
