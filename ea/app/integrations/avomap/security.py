from __future__ import annotations

import hashlib
import hmac


def _hex_hmac(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def sign_webhook_body(secret: str, body: bytes) -> str:
    return f"sha256={_hex_hmac(secret, body)}"


def verify_webhook_signature(secret: str | None, body: bytes, signature: str | None) -> bool:
    if not secret or not signature:
        return False
    provided = str(signature).strip()
    if provided.startswith("sha256="):
        provided = provided.split("=", 1)[1].strip()
    expected = _hex_hmac(secret, body)
    return hmac.compare_digest(expected, provided)


def issue_job_token(secret: str | None, *, tenant: str, job_id: str, spec_id: str) -> str:
    if not secret:
        return ""
    seed = f"{tenant}:{job_id}:{spec_id}".encode("utf-8")
    return f"{job_id}:{_hex_hmac(secret, seed)}"


def verify_job_token(
    secret: str | None,
    *,
    tenant: str,
    job_id: str,
    spec_id: str,
    token: str | None,
) -> bool:
    if not secret or not token:
        return False
    parts = str(token).split(":", 1)
    if len(parts) != 2:
        return False
    token_job_id, token_sig = parts
    if token_job_id != str(job_id):
        return False
    expected = _hex_hmac(secret, f"{tenant}:{job_id}:{spec_id}".encode("utf-8"))
    return hmac.compare_digest(expected, token_sig)

