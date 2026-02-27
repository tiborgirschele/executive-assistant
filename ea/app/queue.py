import json
import uuid
from typing import Any, Optional
from app.db import get_db

def ingest_update(*, tenant: str, update_id: int, payload: dict[str, Any]) -> None:
    get_db().execute(
        """
        INSERT INTO tg_updates(tenant, update_id, payload_json, status, next_attempt_at)
        VALUES (%s, %s, %s::jsonb, 'queued', NOW())
        ON CONFLICT (tenant, update_id) DO NOTHING
        """,
        [tenant, update_id, json.dumps(payload, ensure_ascii=False)]
    )

def claim_update() -> Optional[dict[str, Any]]:
    db = get_db()
    row = db.fetchone(
        """
        SELECT tenant, update_id, payload_json, attempt_count
          FROM tg_updates
         WHERE status IN ('queued', 'retry')
           AND next_attempt_at <= NOW()
         ORDER BY next_attempt_at ASC
         FOR UPDATE SKIP LOCKED
         LIMIT 1
        """
    )
    if not row: return None
    db.execute("UPDATE tg_updates SET status='processing' WHERE tenant=%s AND update_id=%s", [row["tenant"], row["update_id"]])
    return dict(row)

def mark_update_done(*, tenant: str, update_id: int) -> None:
    get_db().execute("UPDATE tg_updates SET status='done' WHERE tenant=%s AND update_id=%s", [tenant, update_id])

def mark_update_error(*, tenant: str, update_id: int, attempt_count: int, error: str) -> None:
    delay = 2 ** int(attempt_count)
    status = 'retry' if attempt_count < 10 else 'deadletter'
    get_db().execute(
        f"UPDATE tg_updates SET status=%s, attempt_count=attempt_count+1, last_error=%s, next_attempt_at=NOW() + interval '{delay} seconds' WHERE tenant=%s AND update_id=%s",
        [status, str(error)[:2000], tenant, update_id]
    )

def enqueue_outbox(*, tenant: str, chat_id: int, payload: dict[str, Any], idempotency_key: str) -> None:
    get_db().execute(
        """
        INSERT INTO tg_outbox(id, tenant, chat_id, payload_json, status, idempotency_key)
        VALUES (%s::uuid, %s, %s, %s::jsonb, 'queued', %s)
        ON CONFLICT (tenant, idempotency_key) DO NOTHING
        """,
        [str(uuid.uuid4()), tenant, chat_id, json.dumps(payload, ensure_ascii=False), idempotency_key]
    )

def claim_outbox_message() -> Optional[dict[str, Any]]:
    db = get_db()
    row = db.fetchone(
        """
        SELECT id::text as id, tenant, chat_id, payload_json, attempt_count
          FROM tg_outbox
         WHERE status IN ('queued', 'retry')
           AND next_attempt_at <= NOW()
         ORDER BY next_attempt_at ASC
         FOR UPDATE SKIP LOCKED
         LIMIT 1
        """
    )
    if not row: return None
    db.execute("UPDATE tg_outbox SET status='processing' WHERE id=%s::uuid", [row["id"]])
    return dict(row)

def mark_outbox_sent(*, message_id: str) -> None:
    get_db().execute("UPDATE tg_outbox SET status='sent' WHERE id=%s::uuid", [message_id])

def mark_outbox_error(*, message_id: str, attempt_count: int, error: str) -> None:
    delay = 2 ** int(attempt_count)
    status = 'retry' if attempt_count < 10 else 'deadletter'
    get_db().execute(
        f"UPDATE tg_outbox SET status=%s, attempt_count=attempt_count+1, last_error=%s, next_attempt_at=NOW() + interval '{delay} seconds' WHERE id=%s::uuid",
        [status, str(error)[:2000], message_id]
    )
