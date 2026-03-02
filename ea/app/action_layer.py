from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.db import get_db
from app.telegram.callback_tokens import consume_callback_token, issue_callback_token


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _idem_key(tenant_key: str, principal_id: str, action_type: str, payload: dict[str, Any]) -> str:
    packed = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(f"{tenant_key}:{principal_id}:{action_type}:{packed}".encode("utf-8")).hexdigest()[:40]


class ActionOrchestrator:
    def __init__(self) -> None:
        self.db = get_db()

    def create_action_draft(
        self,
        *,
        tenant_key: str,
        principal_id: str,
        action_type: str,
        payload: dict[str, Any],
        preconditions: dict[str, Any],
    ) -> str:
        draft_id = str(uuid.uuid4())
        idem = _idem_key(tenant_key, principal_id, action_type, payload)
        self.db.execute(
            """
            INSERT INTO action_drafts
                (draft_id, tenant_key, principal_id, action_type, status, action_payload_json, preconditions_json, idempotency_key, created_at, updated_at)
            VALUES
                (%s::uuid, %s, %s, %s, 'draft', %s::jsonb, %s::jsonb, %s, %s, %s)
            """,
            (draft_id, tenant_key, principal_id, action_type, json.dumps(payload), json.dumps(preconditions), idem, _utcnow(), _utcnow()),
        )
        self.db.execute(
            """
            INSERT INTO approval_requests (draft_id, tenant_key, principal_id, request_status, created_at)
            VALUES (%s::uuid, %s, %s, 'pending', %s)
            """,
            (draft_id, tenant_key, principal_id, _utcnow()),
        )
        self.db.execute(
            """
            INSERT INTO action_state_history (draft_id, from_state, to_state, reason, created_at)
            VALUES (%s::uuid, NULL, 'draft', 'created', %s)
            """,
            (draft_id, _utcnow()),
        )
        return draft_id

    def issue_approval(
        self,
        *,
        draft_id: str,
        tenant_key: str,
        principal_id: str,
        chat_id: str,
        message_id: str,
        action_family: str = "action",
    ) -> str:
        self.db.execute(
            "UPDATE action_drafts SET status='awaiting_approval', updated_at=%s WHERE draft_id=%s::uuid",
            (_utcnow(), draft_id),
        )
        self.db.execute(
            """
            INSERT INTO action_state_history (draft_id, from_state, to_state, reason, created_at)
            VALUES (%s::uuid, 'draft', 'awaiting_approval', 'approval_issued', %s)
            """,
            (draft_id, _utcnow()),
        )
        return issue_callback_token(
            tenant_key=tenant_key,
            principal_id=principal_id,
            chat_id=chat_id,
            message_id=message_id,
            action_family=action_family,
            draft_id=draft_id,
        )

    def approve_and_execute(
        self,
        *,
        raw_callback_token: str,
        tenant_key: str,
        principal_id: str,
        chat_id: str,
        message_id: str,
        action_family: str,
        pre_exec_validator: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        tok = consume_callback_token(
            raw_token=raw_callback_token,
            tenant_key=tenant_key,
            principal_id=principal_id,
            chat_id=chat_id,
            message_id=message_id,
            action_family=action_family,
        )
        draft_id = tok["draft_id"]
        draft = self.db.fetchone(
            """
            SELECT draft_id::text AS draft_id, action_payload_json, preconditions_json, idempotency_key
            FROM action_drafts
            WHERE draft_id=%s::uuid
            """,
            (draft_id,),
        )
        if not draft:
            raise ValueError("draft_not_found")
        payload = draft["action_payload_json"] or {}
        preconditions = draft["preconditions_json"] or {}

        check = pre_exec_validator(payload, preconditions)
        if not check.get("ok"):
            self.db.execute(
                "UPDATE action_drafts SET status='stale', updated_at=%s WHERE draft_id=%s::uuid",
                (_utcnow(), draft_id),
            )
            self.db.execute(
                """
                INSERT INTO action_state_history (draft_id, from_state, to_state, reason, created_at)
                VALUES (%s::uuid, 'awaiting_approval', 'stale', %s, %s)
                """,
                (draft_id, str(check.get("reason") or "stale_precondition"), _utcnow()),
            )
            return {"status": "refresh_required", "reason": check.get("reason") or "stale_precondition"}

        existing = self.db.fetchone(
            "SELECT execution_id FROM action_executions WHERE tenant_key=%s AND idempotency_key=%s ORDER BY execution_id DESC LIMIT 1",
            (tenant_key, draft["idempotency_key"]),
        )
        if existing:
            return {"status": "deduped", "execution_id": int(existing["execution_id"])}

        saga_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO saga_instances (saga_id, draft_id, saga_status, created_at, updated_at) VALUES (%s::uuid, %s::uuid, 'running', %s, %s)",
            (saga_id, draft_id, _utcnow(), _utcnow()),
        )
        self.db.execute(
            "INSERT INTO saga_steps (saga_id, step_name, step_status, step_payload_json, created_at) VALUES (%s::uuid, 'pre_exec_validation', 'completed', %s::jsonb, %s)",
            (saga_id, json.dumps(check), _utcnow()),
        )
        exe = self.db.fetchone(
            """
            INSERT INTO action_executions (draft_id, tenant_key, principal_id, execution_status, idempotency_key, created_at, completed_at)
            VALUES (%s::uuid, %s, %s, 'executed', %s, %s, %s)
            RETURNING execution_id
            """,
            (draft_id, tenant_key, principal_id, draft["idempotency_key"], _utcnow(), _utcnow()),
        )
        self.db.execute(
            """
            INSERT INTO execution_receipts (execution_id, validated_preconditions_json, changed_fields_json, receipt_status, created_at)
            VALUES (%s, %s::jsonb, %s::jsonb, 'executed', %s)
            """,
            (
                exe["execution_id"],
                json.dumps(preconditions),
                json.dumps(check.get("changed_fields") or []),
                _utcnow(),
            ),
        )
        self.db.execute(
            "UPDATE action_drafts SET status='executed', updated_at=%s WHERE draft_id=%s::uuid",
            (_utcnow(), draft_id),
        )
        self.db.execute(
            "UPDATE saga_instances SET saga_status='completed', updated_at=%s WHERE saga_id=%s::uuid",
            (_utcnow(), saga_id),
        )
        self.db.execute(
            """
            INSERT INTO action_state_history (draft_id, from_state, to_state, reason, created_at)
            VALUES (%s::uuid, 'awaiting_approval', 'executed', 'approved_and_validated', %s)
            """,
            (draft_id, _utcnow()),
        )
        return {"status": "executed", "execution_id": int(exe["execution_id"])}

