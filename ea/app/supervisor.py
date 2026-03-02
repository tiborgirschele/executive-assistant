import functools, logging, uuid, asyncio, json

def trigger_mum_brain(db_conn, e_msg, fallback="telegram_text", failure_class="system_error", intent="unknown"):
    """v1.12.1 L2 Supervisor Programmatic API"""
    cid = uuid.uuid4().hex[:8]
    logging.error(f"🚨 [L2 SUPERVISOR] Escalation triggered for '{intent}'. CorrID: {cid}. Msg: {str(e_msg)[:100]}...")
    
    if db_conn is None:
        try:
            from app.db import get_db
            db_conn = get_db()
        except: pass

    # MANDATORY: Erase dirty transaction state!
    if db_conn:
        try:
            if hasattr(db_conn, 'rollback'): db_conn.rollback()
            elif hasattr(db_conn, 'conn') and hasattr(db_conn.conn, 'rollback'): db_conn.conn.rollback()
            logging.info("🧹 [L1: CHILD] DB transaction cleanly rolled back.")
        except: pass
        
        # Async Ticketing (Stuck Event)
        try:
            sql = "INSERT INTO stuck_events (intent, failure_class, correlation_id, user_safe_context_json) VALUES (%s, %s, %s, %s)"
            ctx = json.dumps({"error_snippet": str(e_msg)[:200]})
            if hasattr(db_conn, 'execute'): db_conn.execute(sql, (intent, failure_class, cid, ctx))
            elif hasattr(db_conn, 'cursor'):
                with db_conn.cursor() as cur: cur.execute(sql, (intent, failure_class, cid, ctx))
            if hasattr(db_conn, 'commit'): db_conn.commit()
            elif hasattr(db_conn, 'conn') and hasattr(db_conn.conn, 'commit'): db_conn.conn.commit()
        except Exception as log_e:
            logging.error(f"⚠️ [L2 SUPERVISOR] Failed to write event logs: {log_e}")
            try:
                if hasattr(db_conn, 'rollback'): db_conn.rollback()
                elif hasattr(db_conn, 'conn') and hasattr(db_conn.conn, 'rollback'): db_conn.conn.rollback()
            except: pass
            
    return cid
