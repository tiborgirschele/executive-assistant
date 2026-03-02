from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import get_db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_callback_token(
    *,
    tenant_key: str,
    principal_id: str,
    chat_id: str,
    message_id: str,
    action_family: str,
    draft_id: str,
    ttl_minutes: int = 15,
) -> str:
    raw = secrets.token_urlsafe(24)
    expires_at = _utcnow() + timedelta(minutes=max(1, ttl_minutes))
    get_db().execute(
        """
        INSERT INTO action_callbacks
            (token_hash, tenant_key, principal_id, chat_id, message_id, action_family, draft_id, expires_at, created_at)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s::uuid, %s, %s)
        """,
        (_hash(raw), tenant_key, principal_id, chat_id, message_id, action_family, draft_id, expires_at, _utcnow()),
    )
    return raw


def consume_callback_token(
    *,
    raw_token: str,
    tenant_key: str,
    principal_id: str,
    chat_id: str,
    message_id: str,
    action_family: str,
) -> dict[str, Any]:
    row = get_db().fetchone(
        """
        SELECT callback_id, draft_id::text AS draft_id, expires_at, used_at
        FROM action_callbacks
        WHERE token_hash = %s
          AND tenant_key = %s
          AND principal_id = %s
          AND chat_id = %s
          AND message_id = %s
          AND action_family = %s
        """,
        (_hash(raw_token), tenant_key, principal_id, chat_id, message_id, action_family),
    )
    if not row:
        raise ValueError("invalid_callback_token")
    if row.get("used_at"):
        raise ValueError("callback_token_already_used")
    if row["expires_at"] and row["expires_at"] < _utcnow():
        raise ValueError("callback_token_expired")
    get_db().execute("UPDATE action_callbacks SET used_at = %s WHERE callback_id = %s", (_utcnow(), row["callback_id"]))
    return {"draft_id": row["draft_id"]}

