import json, logging
from app.db import get_db

async def process_browseract_event(event_id: str):
    db = get_db()
    try:
        row = db.fetchone("UPDATE external_events SET status='processing', updated_at=NOW() WHERE event_id=%s::uuid AND (status IN ('new', 'failed') OR (status='processing' AND updated_at < NOW() - INTERVAL '15 minutes')) RETURNING tenant, payload_json", (str(event_id),))
        if not row: 
            if hasattr(db, 'commit'): db.commit()
            return
            
        tenant = row['tenant'] if hasattr(row, 'keys') else row[0]
        p_raw = row['payload_json'] if hasattr(row, 'keys') else row[1]
        payload = json.loads(p_raw) if isinstance(p_raw, str) else p_raw
        if not isinstance(payload, dict): payload = {}

        # Autonome Extraktion der ID
        template_id = payload.get("template_id") or payload.get("data", {}).get("template_id") or payload.get("output", {}).get("template_id") or payload.get("id")
        
        if template_id:
            logging.info(f"🤖 AUTO-HEALING: Speichere Template-ID '{template_id}' für {tenant} in Registry...")
            db.execute("INSERT INTO template_registry (tenant, key, provider, template_id) VALUES (%s, 'briefing.image', 'markupgo', %s) ON CONFLICT (tenant, key, provider) DO UPDATE SET template_id = EXCLUDED.template_id", (tenant, str(template_id)))
            
            # Für Generic EA Bot ebenfalls heilen
            db.execute("INSERT INTO template_registry (tenant, key, provider, template_id) VALUES ('ea_bot', 'briefing.image', 'markupgo', %s) ON CONFLICT (tenant, key, provider) DO UPDATE SET template_id = EXCLUDED.template_id", (str(template_id),))

            db.execute("UPDATE external_events SET status='processed', updated_at=NOW() WHERE event_id=%s::uuid", (str(event_id),))
        else:
            db.execute("UPDATE external_events SET status='discarded', updated_at=NOW() WHERE event_id=%s::uuid", (str(event_id),))
            logging.warning("🤖 AUTO-HEALING ABORTED: Kein template_id gefunden.")

        if hasattr(db, 'commit'): db.commit()
        
    except Exception as e:
        logging.error(f"BrowserAct Normalizer Error: {e}")
        db.execute("UPDATE external_events SET status='failed', updated_at=NOW() WHERE event_id=%s::uuid", (str(event_id),))
        if hasattr(db, 'commit'): db.commit()
