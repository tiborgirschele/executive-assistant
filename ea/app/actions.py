import uuid, json
from app.db import get_db

def create_action(tenant: str, action_type: str, payload: dict, days: int = 7) -> str:
    db = get_db()
    act_id = str(uuid.uuid4())
    db.execute("INSERT INTO typed_actions (id, tenant, action_type, payload_json, expires_at) VALUES (%s, %s, %s, %s, NOW() + interval '%s days')",
               (act_id, tenant, action_type, json.dumps(payload), days))
    return act_id

def consume_action(tenant: str, act_id: str):
    db = get_db()
    # Atomic consume using FOR UPDATE SKIP LOCKED prevents TOCTOU replay attacks
    action = db.fetchone("SELECT * FROM typed_actions WHERE id = %s AND tenant = %s AND is_consumed = FALSE AND expires_at > NOW() FOR UPDATE SKIP LOCKED", (act_id, tenant))
    if action:
        db.execute("UPDATE typed_actions SET is_consumed = TRUE WHERE id = %s", (act_id,))
        return action
    return None
