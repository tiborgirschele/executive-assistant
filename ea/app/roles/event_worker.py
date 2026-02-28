import asyncio
import json
import traceback
from app.db import get_db

async def run_event_worker():
    print("==================================================", flush=True)
    print("📥 EA OS EVENT WORKER: External Events Ingress Online", flush=True)
    print("==================================================", flush=True)
    db = get_db()
    
    while True:
        try:
            row = await asyncio.to_thread(db.fetchone, """
                UPDATE external_events 
                SET status = 'processing', updated_at = NOW() 
                WHERE id = (
                    SELECT id FROM external_events 
                    WHERE status IN ('queued', 'retry') AND next_attempt_at <= NOW() 
                    ORDER BY created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1
                ) RETURNING *;
            """)
            
            if not row:
                await asyncio.sleep(2)
                continue
                
            event_id, source, tenant, payload = row['id'], row['source'], row['tenant'], row['payload_json']
            print(f"⚙️ Processing {source} for {tenant} (ID: {event_id})", flush=True)
            
            # Y3. Inbound adapters rule: 
            # "Gmail/Drive ingest creates an artifact-ingest job, not a direct payment execution."
            if source in ["apixdrive.gmail_invoice_ingest", "apixdrive.drive_invoice_ingest"]:
                print(f"📄 Delegating {source} to artifact-ingest action...", flush=True)
                
                # Insert a typed action for the core worker to pick up
                action_payload = {"source": source, "event_id": str(event_id), "payload": payload}
                await asyncio.to_thread(db.execute, """
                    INSERT INTO typed_actions (id, tenant, action_type, payload_json, expires_at)
                    VALUES (gen_random_uuid(), %s, 'artifact.ingest', %s, NOW() + interval '7 days')
                """, (tenant, json.dumps(action_payload)))
                
                # Notify operator
                await asyncio.to_thread(db.execute, """
                    INSERT INTO tg_outbox (chat_id, payload_json)
                    VALUES ((SELECT chat_id FROM tenants WHERE id = %s LIMIT 1), %s)
                """, (tenant, json.dumps({"text": f"🔔 <b>New Document Ingested ({source})</b>\nArtifact ingest job successfully queued.", "parse_mode": "HTML"})))
                
            else:
                print(f"🌐 Processing generic webhook...", flush=True)
                await asyncio.to_thread(db.execute, """
                    INSERT INTO tg_outbox (chat_id, payload_json)
                    VALUES ((SELECT chat_id FROM tenants WHERE id = %s LIMIT 1), %s)
                """, (tenant, json.dumps({"text": f"🔔 <b>Generic Webhook Received</b>\nSource: {source}", "parse_mode": "HTML"})))
                
            await asyncio.to_thread(db.execute, "UPDATE external_events SET status = 'processed', updated_at = NOW() WHERE id = %s", (event_id,))
            print(f"✅ Event {event_id} successfully processed.", flush=True)
            
        except Exception as e:
            print(f"🚨 Event Worker Error: {e}", flush=True)
            traceback.print_exc()
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_event_worker())
