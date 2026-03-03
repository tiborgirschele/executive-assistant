import asyncio, logging, os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.db import get_db
from app.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] EVENT-WORKER: %(message)s')


def _expire_stale_avomap_jobs(db) -> None:
    timeout_sec = int(getattr(settings, "avomap_browseract_timeout_sec", 180) or 180)
    db.execute(
        """
        UPDATE avomap_jobs j
        SET status='failed', last_error='browseract_timeout', updated_at=NOW()
        WHERE j.status IN ('queued', 'processing')
          AND j.updated_at < NOW() - (%s * INTERVAL '1 second')
          AND NOT EXISTS (
              SELECT 1 FROM avomap_assets a
              WHERE a.spec_id = j.spec_id AND a.status='ready'
          )
        """,
        (timeout_sec,),
    )
    db.execute(
        """
        UPDATE travel_video_specs s
        SET status='failed', last_error='browseract_timeout', updated_at=NOW()
        WHERE s.status IN ('pending', 'dispatched')
          AND EXISTS (
              SELECT 1 FROM avomap_jobs j
              WHERE j.spec_id = s.spec_id
                AND j.status='failed'
                AND j.last_error='browseract_timeout'
          )
        """,
    )

async def poll_external_events():
    db = get_db()
    logging.info("🚀 EA Event Worker started. Polling for durable webhooks...")
    from app.approvals.normalizer import process_approvethis_event
    from app.intake.browseract import process_browseract_event
    from app.intake.metasurvey_feedback import process_metasurvey_submission
    while True:
        try:
            _expire_stale_avomap_jobs(db)
            row = db.fetchone(
                """
                SELECT COALESCE(to_jsonb(external_events)->>'id', to_jsonb(external_events)->>'event_id') AS id, source
                FROM external_events
                WHERE status IN ('new', 'queued')
                   OR (status IN ('retry', 'failed') AND next_attempt_at <= NOW())
                   OR (status='processing' AND updated_at < NOW() - INTERVAL '15 minutes')
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
            if hasattr(db, 'commit'): db.commit()
            
            if not row:
                await asyncio.sleep(2) # Schnelleres Polling (2s statt 4s)
                continue
                
            r = row if hasattr(row, 'keys') else {"id": row[0], "source": row[1]}
            source = r["source"]
            event_id = str(r["id"])
            
            if source == 'approvethis': 
                await process_approvethis_event(event_id)
            elif source == 'browseract':
                await process_browseract_event(event_id)
            elif source == 'metasurvey':
                await process_metasurvey_submission(event_id)
            else: 
                try:
                    db.execute("UPDATE external_events SET status='discarded', updated_at=NOW() WHERE id=%s::uuid", (event_id,))
                except Exception:
                    db.execute("UPDATE external_events SET status='discarded', updated_at=NOW() WHERE event_id=%s::uuid", (event_id,))
                if hasattr(db, 'commit'): db.commit()
                
        except Exception as e:
            logging.error(f"Event Worker Loop Error: {e}")
            await asyncio.sleep(4)

if __name__ == "__main__": asyncio.run(poll_external_events())
