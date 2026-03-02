import asyncio, logging, os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db import get_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] EVENT-WORKER: %(message)s')

async def poll_external_events():
    db = get_db()
    logging.info("🚀 EA Event Worker started. Polling for durable webhooks...")
    from app.approvals.normalizer import process_approvethis_event
    from app.intake.browseract import process_browseract_event
    while True:
        try:
            row = db.fetchone("SELECT event_id, source FROM external_events WHERE status='new' OR (status IN ('processing', 'failed') AND updated_at < NOW() - INTERVAL '15 minutes') ORDER BY created_at ASC LIMIT 1")
            if hasattr(db, 'commit'): db.commit()
            
            if not row:
                await asyncio.sleep(2) # Schnelleres Polling (2s statt 4s)
                continue
                
            r = row if hasattr(row, 'keys') else {"event_id": row[0], "source": row[1]}
            source = r["source"]
            event_id = str(r["event_id"])
            
            if source == 'approvethis': 
                await process_approvethis_event(event_id)
            elif source == 'browseract':
                await process_browseract_event(event_id)
            else: 
                db.execute("UPDATE external_events SET status='discarded', updated_at=NOW() WHERE event_id=%s::uuid", (event_id,))
                if hasattr(db, 'commit'): db.commit()
                
        except Exception as e:
            logging.error(f"Event Worker Loop Error: {e}")
            await asyncio.sleep(4)

if __name__ == "__main__": asyncio.run(poll_external_events())
