from __future__ import annotations
import json, re
from typing import List
from app.audit import log_event
from app.config import load_tenants
from app.db import connect
from app.gog import gog_scout
from app import llm

_JSON_RE = re.compile(r"\{[\s\S]*\}", re.M)

def _extract_json(text: str) -> dict:
    m = _JSON_RE.search(text or "")
    if not m:
        raise ValueError("No JSON in text")
    return json.loads(m.group(0))

async def sync_keep_shopping_list(tenant: str) -> dict:
    tenants, _, _ = load_tenants()
    t = tenants.get(tenant)
    if not t:
        raise ValueError("unknown tenant")

    prompt = """
Lies die Google Keep Einkaufsliste (Shopping List) und gib NUR JSON zurück:
{"items":["item1","item2",...]}
Regeln:
- Nur offene Items.
- Keine Erklärungen, keine Markdown.
""".strip()

    raw = gog_scout(t.openclaw_container, prompt, to=t.whatsapp_to)
    items: List[str] = []
    try:
        obj = _extract_json(raw)
        items = [str(x).strip() for x in (obj.get("items") or []) if str(x).strip()]
    except Exception:
        # fallback: ask LLM to extract
        obj = await llm.complete_json(f"Extract shopping list items from this text. Output JSON {{\"items\":[...]}} only.\n\nTEXT:\n{raw[:12000]}")
        items = [str(x).strip() for x in (obj.get("items") or []) if str(x).strip()]

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shopping_list WHERE tenant=%s", (tenant,))
            for it in items:
                cur.execute("INSERT INTO shopping_list (tenant, item, checked, raw) VALUES (%s,%s,false,%s)",
                            (tenant, it, json.dumps({"source":"keep_sync"})))
        conn.commit()

    log_event(tenant, "sync", "keep", "synced keep shopping list", {"count": len(items)})
    return {"ok": True, "tenant": tenant, "count": len(items)}
