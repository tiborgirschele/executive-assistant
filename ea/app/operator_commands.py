from __future__ import annotations

import html

from app.repair.healer import system_health_snapshot


def _safe_err(err: Exception) -> str:
    return html.escape(str(err), quote=False)


async def handle_mumbrain_command(*, tg, chat_id: int, tenant_cfg: dict, admin_chat_id: str | None) -> None:
    is_admin = bool((tenant_cfg or {}).get("is_admin", False)) or str(chat_id) == str(admin_chat_id or "")
    if not is_admin:
        await tg.send_message(
            chat_id,
            "ℹ️ This command is operator-only.",
            parse_mode="HTML",
        )
        return

    try:
        from app.db import get_db

        db = get_db()
        active = db.fetchone("SELECT count(*) AS c FROM delivery_sessions WHERE status = 'active'")
        health = system_health_snapshot(db)
        last = db.fetchone("SELECT recipe_key, status FROM repair_jobs ORDER BY job_id DESC LIMIT 1")
        msg = (
            "🧠 <b>Mum Brain Status</b>\n\n"
            f"• Phase A active deliveries: <b>{int((active or {}).get('c') or 0)}</b>\n"
            f"• Phase B pending/running: <b>{health['pending']}</b>/<b>{health['running']}</b>\n"
            f"• Repairs 24h (ok/failed): <b>{health['completed_24h']}</b>/<b>{health['failed_24h']}</b>\n"
            f"• Replay queue/dead letters: <b>{health['replay_q']}</b>/<b>{health['dead_q']}</b>\n"
            f"• Render breaker open: <b>{'yes' if health['breaker_open'] else 'no'}</b>\n"
            f"• Last repair: <b>{(last or {}).get('recipe_key') or 'none'}</b> → <b>{(last or {}).get('status') or 'none'}</b>"
        )
        await tg.send_message(chat_id, msg, parse_mode="HTML")
    except Exception as err:
        await tg.send_message(chat_id, f"⚠️ Mum Brain status error: {_safe_err(err)}")
