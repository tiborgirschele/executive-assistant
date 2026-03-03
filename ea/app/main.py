from __future__ import annotations

# Hardened boot logging
print("\n" + "!"*40, flush=True)
print("🚀 CHIEF OF STAFF SYSTEM BOOTING", flush=True)
print("!"*40 + "\n", flush=True)

from app.server import app

from fastapi import Request, Header, HTTPException
import hashlib
import json
from app.audit import log_event

def _require_ingest_auth(authorization: str | None) -> None:
    from app.settings import settings
    expected = settings.ea_ingest_token or settings.apixdrive_shared_secret
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/webhooks/apixdrive/{tenant}")
async def apixdrive_ingress(tenant: str, request: Request, authorization: str = Header(None)):
    from app.db import get_db
    _require_ingest_auth(authorization)
        
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    source = payload.get("source", "apixdrive.generic")
    event_type = payload.get("event_type", "webhook_ingest")
    
    # 2. Derive dedupe_key (Idempotency)
    raw_dedupe = payload.get("id") or payload.get("message_id") or payload.get("file_id")
    if raw_dedupe:
        dedupe_key = str(raw_dedupe)
    else:
        dedupe_key = hashlib.md5(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()

    # 3. Fire & Forget Insertion
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO external_events (tenant, source, event_type, dedupe_key, payload_json)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (tenant, source, dedupe_key) DO NOTHING
            """, (tenant, source, event_type, dedupe_key, json.dumps(payload))
        )
        return {"status": "accepted", "tenant": tenant, "source": source, "dedupe_key": dedupe_key}
    except Exception as e:
        log_event(
            tenant,
            "ingress",
            "error",
            "apixdrive ingest persistence failed",
            {"source": source, "error": str(e)[:300]},
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/webhooks/metasurvey/{tenant}")
async def metasurvey_webhook(tenant: str, request: Request, authorization: str = Header(None)):
    _require_ingest_auth(authorization)
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    from app.db import get_db
    db = get_db()
    dedupe = payload.get("response_id", "unknown")
    db.execute(
        """
        INSERT INTO external_events (tenant, source, event_type, dedupe_key, payload_json)
        VALUES (%s, 'metasurvey', 'submission', %s, %s::jsonb)
        ON CONFLICT (tenant, source, dedupe_key) DO NOTHING
        """,
        (tenant, dedupe, json.dumps(payload)),
    )
    return {"status": "ok"}

@app.post("/webhooks/browseract/{tenant}/{workflow}")
async def browseract_webhook(tenant: str, workflow: str, request: Request, authorization: str = Header(None)):
    _require_ingest_auth(authorization)
    import json, hashlib
    from app.db import get_db
    from app.integrations.avomap.security import verify_webhook_signature
    from app.settings import settings
    try:
        raw_body = await request.body()
        if str(workflow).startswith("avomap."):
            sig = request.headers.get("x-webhook-signature")
            if not verify_webhook_signature(settings.avomap_webhook_secret, raw_body, sig):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
        payload = json.loads(raw_body.decode("utf-8"))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    payload_str = json.dumps(payload, sort_keys=True)
    dedupe = request.headers.get("x-webhook-id") or hashlib.sha256(payload_str.encode('utf-8')).hexdigest()
    
    db = get_db()
    db.execute('''
        INSERT INTO external_events (tenant, source, event_type, dedupe_key, payload_json)
        VALUES (%s, 'browseract', %s, %s, %s::jsonb)
        ON CONFLICT (tenant, source, dedupe_key) DO NOTHING
    ''', (tenant, workflow, dedupe, payload_str))
    return {"status": "ok", "durability": "persisted"}
