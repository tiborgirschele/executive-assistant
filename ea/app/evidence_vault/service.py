from __future__ import annotations

import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone

from cryptography.fernet import Fernet

from app.db import get_db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _vault_secret() -> bytes:
    raw = (os.environ.get("EA_EVIDENCE_VAULT_MASTER_KEY", "") or "").strip()
    if raw:
        if len(raw) == 44:
            return raw.encode("utf-8")
        digest = hashlib.sha256(raw.encode("utf-8")).digest()
    else:
        digest = hashlib.sha256(b"ea-dev-vault-default-do-not-use-in-prod").digest()
    return base64.urlsafe_b64encode(digest)


def _token_key(tenant_key: str, object_ref: str) -> str:
    secret = _vault_secret()
    token = hmac.new(secret, f"{tenant_key}:{object_ref}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"keyref:{token[:24]}"


class EvidenceVaultService:
    def __init__(self) -> None:
        self.db = get_db()
        self._fernet = Fernet(_vault_secret())

    def store(self, *, tenant_key: str, object_ref: str, correlation_id: str, payload: bytes) -> str:
        vault_object_id = str(uuid.uuid4())
        encrypted = self._fernet.encrypt(payload)
        key_ref = _token_key(tenant_key, object_ref)
        self.db.execute(
            """
            INSERT INTO evidence_vault_objects
                (vault_object_id, tenant_key, correlation_id, object_ref, encrypted_payload, key_ref, key_version, is_readable, created_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, 1, TRUE, %s)
            """,
            (vault_object_id, tenant_key, correlation_id, object_ref, encrypted, key_ref, _utcnow()),
        )
        return vault_object_id

    def read(self, *, vault_object_id: str) -> bytes:
        row = self.db.fetchone(
            "SELECT encrypted_payload, is_readable FROM evidence_vault_objects WHERE vault_object_id = %s",
            (vault_object_id,),
        )
        if not row:
            raise ValueError("vault_object_not_found")
        if not bool(row.get("is_readable")):
            raise ValueError("vault_object_shredded")
        return self._fernet.decrypt(bytes(row["encrypted_payload"]))

    def crypto_shred(self, *, tenant_key: str, object_ref: str, reason: str) -> int:
        self.db.execute(
            """
            INSERT INTO deletion_tombstones (tenant_key, object_ref, reason, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            (tenant_key, object_ref, reason, _utcnow()),
        )
        self.db.execute(
            """
            UPDATE evidence_vault_objects
            SET encrypted_payload = '\\x'::bytea, is_readable = FALSE, shredded_at = %s
            WHERE tenant_key = %s AND object_ref = %s
            """,
            (_utcnow(), tenant_key, object_ref),
        )
        row = self.db.fetchone(
            "SELECT count(*) AS cnt FROM evidence_vault_objects WHERE tenant_key = %s AND object_ref = %s AND is_readable = FALSE",
            (tenant_key, object_ref),
        )
        return int(row["cnt"]) if row else 0

