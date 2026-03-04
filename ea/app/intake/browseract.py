import json, logging, os
from app.db import get_db
from app.execution import (
    append_execution_event,
    compile_intent_spec,
    create_execution_session,
    finalize_execution_session,
    mark_execution_session_running,
    mark_execution_step_status,
)
from app.integrations.avomap.finalize import finalize_avomap_render_event
from app.settings import settings


def _parse_chat_id_from_tenant(tenant: str) -> int | None:
    raw = str(tenant or "")
    if not raw.startswith("chat_"):
        return None
    try:
        return int(raw.split("_", 1)[1])
    except Exception:
        return None


def _claim_active_briefing_session(db, *, chat_id: int) -> int | None:
    try:
        row = db.fetchone(
            """
            SELECT session_id
            FROM delivery_sessions
            WHERE chat_id=%s
              AND mode='briefing'
              AND status='active'
              AND enhancement_deadline_ts >= NOW()
            ORDER BY enhancement_deadline_ts DESC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
            """,
            (str(chat_id),),
        ) or {}
    except Exception:
        return None
    sid = row.get("session_id")
    return int(sid) if sid is not None else None


def _maybe_enqueue_late_attach_followup(db, *, tenant: str, spec_id: str) -> None:
    chat_id = _parse_chat_id_from_tenant(tenant)
    if not chat_id:
        return
    session_id = _claim_active_briefing_session(db, chat_id=chat_id)
    if not session_id:
        return

    asset = db.fetchone(
        """
        SELECT object_ref
        FROM avomap_assets
        WHERE spec_id=%s
          AND status='ready'
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (spec_id,),
    ) or {}
    object_ref = str((asset or {}).get("object_ref") or "").strip()
    if not object_ref:
        return

    claimed = db.fetchone(
        """
        UPDATE avomap_jobs
        SET status='delivered', updated_at=NOW()
        WHERE job_id = (
            SELECT job_id
            FROM avomap_jobs
            WHERE spec_id=%s
              AND status='completed'
              AND updated_at >= NOW() - (%s * INTERVAL '1 second')
            ORDER BY updated_at DESC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING job_id::text AS job_id
        """,
        (spec_id, int(settings.avomap_late_attach_window_sec)),
    )
    if not claimed:
        return

    delivery_mode = str(os.getenv("EA_AVOMAP_LATE_ATTACH_MODE", "link")).strip().lower()
    if delivery_mode in {"video", "sendvideo", "native"}:
        payload = {
            "type": "video",
            "video_url": object_ref,
            "caption": "🎬 <b>Travel video ready</b>",
            "parse_mode": "HTML",
        }
    else:
        payload = {
            "text": f"🎬 <b>Travel video ready</b>\n<a href=\"{object_ref}\">▶ Open video</a>",
            "parse_mode": "HTML",
        }
    idem = f"avomap_late_attach:{spec_id}:{str((claimed or {}).get('job_id') or '')}"
    db.execute(
        """
        INSERT INTO tg_outbox (tenant, chat_id, payload_json, status, idempotency_key)
        VALUES (%s, %s, %s::jsonb, 'queued', %s)
        ON CONFLICT (tenant, idempotency_key) DO NOTHING
        """,
        (tenant, int(chat_id), json.dumps(payload), idem),
    )
    db.execute(
        """
        UPDATE delivery_sessions
        SET status='enhanced'
        WHERE session_id=%s
          AND status='active'
        """,
        (int(session_id),),
    )


async def process_browseract_event(event_id: str):
    db = get_db()
    session_id = None
    current_step = "compile_intent"
    try:
        row = db.fetchone(
            """
            UPDATE external_events
            SET status='processing', updated_at=NOW()
            WHERE COALESCE(to_jsonb(external_events)->>'id', to_jsonb(external_events)->>'event_id')=%s
              AND (
                  status IN ('new', 'queued', 'retry', 'failed')
                  OR (status='processing' AND updated_at < NOW() - INTERVAL '15 minutes')
              )
            RETURNING tenant, event_type, payload_json
            """,
            (str(event_id),),
        )
        if not row: 
            if hasattr(db, 'commit'): db.commit()
            return
            
        tenant = row['tenant'] if hasattr(row, 'keys') else row[0]
        workflow = row['event_type'] if hasattr(row, 'keys') else row[1]
        p_raw = row['payload_json'] if hasattr(row, 'keys') else row[2]
        payload = json.loads(p_raw) if isinstance(p_raw, str) else p_raw
        if not isinstance(payload, dict): payload = {}
        intent_spec = compile_intent_spec(
            text=f"Process BrowserAct event workflow {str(workflow or '').strip()}",
            tenant=str(tenant),
            chat_id=_parse_chat_id_from_tenant(str(tenant)),
            has_url=False,
        )
        intent_spec["source"] = "browseract"
        intent_spec["event_id"] = str(event_id)
        plan_steps = [
            {"step_key": "compile_intent", "step_title": "Compile Event Intent"},
            {"step_key": "execute_intent", "step_title": "Execute Event Handler"},
            {"step_key": "persist_result", "step_title": "Persist Event Result"},
        ]
        session_id = create_execution_session(
            tenant=str(tenant),
            chat_id=_parse_chat_id_from_tenant(str(tenant)),
            intent_spec=intent_spec,
            plan_steps=plan_steps,
            source="external_event_browseract",
            correlation_id=f"browseract:{tenant}:{event_id}",
        )
        if session_id:
            mark_execution_session_running(session_id)
            mark_execution_step_status(session_id, "compile_intent", "completed", result=intent_spec)
            append_execution_event(
                session_id,
                event_type="external_event_claimed",
                message="BrowserAct external event claimed for processing.",
                payload={"event_id": str(event_id), "workflow": str(workflow)},
            )

        if str(workflow or "").startswith("avomap.") or str(workflow or "") == settings.avomap_browseract_workflow:
            current_step = "execute_intent"
            if session_id:
                mark_execution_step_status(
                    session_id,
                    "execute_intent",
                    "running",
                    evidence={"workflow": str(workflow), "event_id": str(event_id)},
                )
            result = finalize_avomap_render_event(
                event_id=str(event_id),
                tenant=str(tenant),
                workflow=str(workflow),
                payload=payload,
                db=db,
            )
            ext_status = "processed" if bool(result.get("ok")) else "failed"
            if session_id:
                mark_execution_step_status(
                    session_id,
                    "execute_intent",
                    "completed" if ext_status == "processed" else "failed",
                    result={"status": str(result.get("status") or ""), "ok": bool(result.get("ok"))},
                )
                append_execution_event(
                    session_id,
                    event_type="avomap_finalize_result",
                    level="info" if ext_status == "processed" else "error",
                    message="AvoMap finalize returned.",
                    payload={"ext_status": ext_status, "result_status": str(result.get("status") or "")},
                )
            current_step = "persist_result"
            if session_id:
                mark_execution_step_status(session_id, "persist_result", "running")
            db.execute(
                """
                UPDATE external_events
                SET status=%s, updated_at=NOW(), last_error=CASE WHEN %s='processed' THEN NULL ELSE %s END
                WHERE COALESCE(to_jsonb(external_events)->>'id', to_jsonb(external_events)->>'event_id')=%s
                """,
                (ext_status, ext_status, str(result)[:500], str(event_id)),
            )
            if ext_status == "processed" and str(result.get("status") or "") == "completed":
                _maybe_enqueue_late_attach_followup(
                    db,
                    tenant=str(tenant),
                    spec_id=str(result.get("spec_id") or ""),
                )
            if session_id:
                mark_execution_step_status(
                    session_id,
                    "persist_result",
                    "completed",
                    result={"external_event_status": ext_status},
                )
                finalize_execution_session(
                    session_id,
                    status="completed" if ext_status == "processed" else "failed",
                    outcome={"external_event_status": ext_status, "result_status": str(result.get("status") or "")},
                    last_error=None if ext_status == "processed" else str(result)[:500],
                )
            if hasattr(db, 'commit'): db.commit()
            return

        # Autonome Extraktion der ID
        current_step = "execute_intent"
        if session_id:
            mark_execution_step_status(
                session_id,
                "execute_intent",
                "running",
                evidence={"workflow": str(workflow), "event_id": str(event_id)},
            )
        template_id = payload.get("template_id") or payload.get("data", {}).get("template_id") or payload.get("output", {}).get("template_id") or payload.get("id")
        if session_id:
            mark_execution_step_status(
                session_id,
                "execute_intent",
                "completed",
                result={"template_found": bool(template_id)},
            )
        
        current_step = "persist_result"
        if session_id:
            mark_execution_step_status(session_id, "persist_result", "running")
        if template_id:
            logging.info(f"🤖 AUTO-HEALING: Speichere Template-ID '{template_id}' für {tenant} in Registry...")
            db.execute("INSERT INTO template_registry (tenant, key, provider, template_id) VALUES (%s, 'briefing.image', 'markupgo', %s) ON CONFLICT (tenant, key, provider) DO UPDATE SET template_id = EXCLUDED.template_id", (tenant, str(template_id)))
            
            # Für Generic EA Bot ebenfalls heilen
            db.execute("INSERT INTO template_registry (tenant, key, provider, template_id) VALUES ('ea_bot', 'briefing.image', 'markupgo', %s) ON CONFLICT (tenant, key, provider) DO UPDATE SET template_id = EXCLUDED.template_id", (str(template_id),))

            db.execute(
                """
                UPDATE external_events
                SET status='processed', updated_at=NOW()
                WHERE COALESCE(to_jsonb(external_events)->>'id', to_jsonb(external_events)->>'event_id')=%s
                """,
                (str(event_id),),
            )
        else:
            db.execute(
                """
                UPDATE external_events
                SET status='discarded', updated_at=NOW()
                WHERE COALESCE(to_jsonb(external_events)->>'id', to_jsonb(external_events)->>'event_id')=%s
                """,
                (str(event_id),),
            )
            logging.info(
                "BrowserAct event discarded: no template_id (workflow=%s, tenant=%s)",
                str(workflow),
                str(tenant),
            )
        if session_id:
            event_status = "processed" if template_id else "discarded"
            mark_execution_step_status(
                session_id,
                "persist_result",
                "completed",
                result={"external_event_status": event_status},
            )
            finalize_execution_session(
                session_id,
                status="completed",
                outcome={"external_event_status": event_status, "template_found": bool(template_id)},
            )

        if hasattr(db, 'commit'): db.commit()
        
    except Exception as e:
        logging.error(f"BrowserAct Normalizer Error: {e}")
        db.execute(
            """
            UPDATE external_events
            SET status='failed', updated_at=NOW()
            WHERE COALESCE(to_jsonb(external_events)->>'id', to_jsonb(external_events)->>'event_id')=%s
            """,
            (str(event_id),),
        )
        if session_id:
            mark_execution_step_status(
                session_id,
                current_step,
                "failed",
                error_text=str(e)[:400],
            )
            append_execution_event(
                session_id,
                level="error",
                event_type="external_event_failed",
                message="BrowserAct event processing failed.",
                payload={"event_id": str(event_id), "step": current_step},
            )
            finalize_execution_session(
                session_id,
                status="failed",
                last_error=str(e)[:400],
                outcome={"event_id": str(event_id), "failed_step": current_step},
            )
        if hasattr(db, 'commit'): db.commit()
