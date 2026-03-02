import os, json, logging, urllib.request, ssl, asyncio
from app.credentials import get_secret_ref
from app.db import get_db

async def create_approval_request(tenant: str, internal_ref_id: str, title: str, document_url: str | None = None) -> dict:
    try: ref = get_secret_ref(tenant, 'approvethis', environment='prod')
    except Exception: pass
    
    api_key = os.environ.get("APPROVETHIS_API_KEY")
    base_url = os.environ.get("APPROVETHIS_API_URL")
    db = get_db()
    
    db.execute("INSERT INTO external_approvals (tenant, internal_ref_id, provider, status) VALUES (%s, %s, 'approvethis', 'parked') ON CONFLICT DO NOTHING", (tenant, internal_ref_id))

    row = db.fetchone("SELECT provider_request_id, status, remote_url FROM external_approvals WHERE tenant = %s AND internal_ref_id = %s AND provider = 'approvethis' FOR UPDATE", (tenant, internal_ref_id))
    if row:
        r = row if hasattr(row, 'keys') else {"provider_request_id": row[0], "status": row[1], "remote_url": row[2]}
        if r.get("provider_request_id") and r.get("status") in ("pending", "approved", "rejected"):
            if hasattr(db, 'commit'): db.commit()
            return {"status": "exists", "provider_request_id": r["provider_request_id"], "remote_url": r.get("remote_url")}

    if not api_key or not base_url:
        db.execute("UPDATE external_approvals SET status='parked', updated_at=NOW() WHERE tenant=%s AND internal_ref_id=%s AND provider='approvethis'", (tenant, internal_ref_id))
        if hasattr(db, 'commit'): db.commit()
        return {"status": "parked", "reason": "Awaiting config"}

    db.execute("UPDATE external_approvals SET status='pending', updated_at=NOW() WHERE tenant=%s AND internal_ref_id=%s AND provider='approvethis'", (tenant, internal_ref_id))
    if hasattr(db, 'commit'): db.commit()

    def _fire():
        req = urllib.request.Request(f"{base_url.rstrip('/')}/v1/requests", data=json.dumps({"title": title, "metadata": {"tenant": tenant, "internal_ref_id": internal_ref_id}}).encode('utf-8'), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Idempotency-Key": internal_ref_id})
        try: return json.loads(urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=10).read().decode())
        except Exception as e: return {"error": str(e)}

    res = await asyncio.to_thread(_fire)
    if "error" not in res:
        pid = res.get("id") or res.get("request_id")
        if pid: db.execute("UPDATE external_approvals SET provider_request_id=%s, updated_at=NOW() WHERE tenant=%s AND internal_ref_id=%s AND provider='approvethis'", (str(pid), tenant, internal_ref_id))
    else:
        db.execute("UPDATE external_approvals SET status='error', updated_at=NOW() WHERE tenant=%s AND internal_ref_id=%s AND provider='approvethis'", (tenant, internal_ref_id))
    
    if hasattr(db, 'commit'): db.commit()
    return res
