from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import get_db
from app.evidence_vault.service import EvidenceVaultService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrustOperatorService:
    def __init__(self) -> None:
        self.db = get_db()
        self.vault = EvidenceVaultService()

    def _audit(self, *, actor_id: str, action_type: str, target_type: str, target_id: str, correlation_id: str, details: dict[str, Any]) -> None:
        self.db.execute(
            """
            INSERT INTO operator_audit_events (actor_id, action_type, target_type, target_id, correlation_id, details_json, created_at)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (actor_id, action_type, target_type, target_id, correlation_id, __import__("json").dumps(details), _utcnow()),
        )

    def create_review_item(self, *, correlation_id: str, safe_hint: dict[str, Any], raw_document_ref: str) -> int:
        row = self.db.fetchone(
            """
            INSERT INTO review_queue_items (status, sanitised_hint_json, raw_document_ref, created_at, updated_at)
            VALUES ('pending', %s::jsonb, %s, %s, %s)
            RETURNING id
            """,
            (__import__("json").dumps(safe_hint, ensure_ascii=False), raw_document_ref, _utcnow(), _utcnow()),
        )
        return int(row["id"])

    def claim_review_item(self, *, review_item_id: int, actor_id: str, ttl_minutes: int = 20) -> str:
        claim_token = secrets.token_urlsafe(18)
        expires = _utcnow() + timedelta(minutes=max(1, ttl_minutes))
        row = self.db.fetchone(
            """
            INSERT INTO review_claims (review_queue_item_id, claimed_by, claim_token, claim_expires_at, claim_status, created_at)
            VALUES (%s, %s, %s, %s, 'active', %s)
            RETURNING claim_id
            """,
            (review_item_id, actor_id, claim_token, expires, _utcnow()),
        )
        self.db.execute(
            """
            UPDATE review_queue_items
            SET status='claimed', claim_token=%s, claimed_by=%s, claim_expires_at=%s, updated_at=%s
            WHERE id=%s
            """,
            (claim_token, actor_id, expires, _utcnow(), review_item_id),
        )
        self._audit(
            actor_id=actor_id,
            action_type="claim_item",
            target_type="review_queue_item",
            target_id=str(review_item_id),
            correlation_id=f"review-{review_item_id}",
            details={"claim_id": int(row["claim_id"])},
        )
        return claim_token

    def store_raw_evidence(self, *, tenant_key: str, object_ref: str, correlation_id: str, payload: bytes) -> str:
        return self.vault.store(tenant_key=tenant_key, object_ref=object_ref, correlation_id=correlation_id, payload=payload)

    def reveal_evidence(self, *, review_item_id: int, actor_id: str, claim_token: str, vault_object_id: str, reason: str) -> bytes:
        claim = self.db.fetchone(
            """
            SELECT claim_id, claim_expires_at, claim_status
            FROM review_claims
            WHERE review_queue_item_id = %s AND claimed_by = %s AND claim_token = %s
            ORDER BY claim_id DESC LIMIT 1
            """,
            (review_item_id, actor_id, claim_token),
        )
        if not claim:
            raise ValueError("invalid_claim")
        if str(claim["claim_status"]) != "active":
            raise ValueError("claim_inactive")
        if claim["claim_expires_at"] and claim["claim_expires_at"] < _utcnow():
            raise ValueError("claim_expired")
        payload = self.vault.read(vault_object_id=vault_object_id)
        self.db.execute(
            """
            INSERT INTO evidence_reveals (review_queue_item_id, claim_id, revealed_by, reveal_reason, correlation_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (review_item_id, claim["claim_id"], actor_id, reason, f"review-{review_item_id}", _utcnow()),
        )
        self._audit(
            actor_id=actor_id,
            action_type="reveal_evidence",
            target_type="review_queue_item",
            target_id=str(review_item_id),
            correlation_id=f"review-{review_item_id}",
            details={"vault_object_id": vault_object_id},
        )
        return payload

    def emit_replay(self, *, review_item_id: int, document_id: str, pipeline_stage: str, correlation_id: str) -> int:
        row = self.db.fetchone(
            """
            INSERT INTO replay_events (document_id, pipeline_stage, attempt_count, status, correlation_id, created_at, updated_at)
            VALUES (%s, %s, 0, 'queued', %s, %s, %s)
            RETURNING id
            """,
            (document_id, pipeline_stage, correlation_id, _utcnow(), _utcnow()),
        )
        self.db.execute(
            "UPDATE review_queue_items SET status='replay_queued', updated_at=%s WHERE id=%s",
            (_utcnow(), review_item_id),
        )
        return int(row["id"])

    def dead_letter_replay(self, *, replay_event_id: int, tenant_key: str, failure_code: str, source_pointer: str, connector_type: str, correlation_id: str) -> int:
        replay = self.db.fetchone("SELECT attempt_count FROM replay_events WHERE id=%s", (replay_event_id,))
        attempts = int((replay or {}).get("attempt_count") or 0) + 1
        self.db.execute(
            """
            UPDATE replay_events
            SET attempt_count=%s, status='deadletter', dead_letter_reason=%s, updated_at=%s
            WHERE id=%s
            """,
            (attempts, failure_code, _utcnow(), replay_event_id),
        )
        row = self.db.fetchone(
            """
            INSERT INTO dead_letter_items (tenant_key, source_pointer, connector_type, failure_code, attempt_count, correlation_id, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'open', %s, %s)
            RETURNING dead_letter_id
            """,
            (tenant_key, source_pointer, connector_type, failure_code, attempts, correlation_id, _utcnow(), _utcnow()),
        )
        self.db.execute(
            """
            INSERT INTO dead_letter_envelopes (dead_letter_id, redacted_failure_json, created_at)
            VALUES (%s, %s::jsonb, %s)
            """,
            (row["dead_letter_id"], __import__("json").dumps({"failure_code": failure_code, "attempts": attempts, "correlation_id": correlation_id}), _utcnow()),
        )
        return int(row["dead_letter_id"])

