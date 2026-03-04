from __future__ import annotations

import asyncio
import html
import os
import re
import traceback
import uuid
from typing import Any, Awaitable, Callable

from app.briefing_delivery_sessions import (
    activate_briefing_delivery_session,
    create_briefing_delivery_session,
)
from app.briefings import build_briefing_for_tenant, get_val
from app.contracts.repair import open_repair_incident
from app.intake.survey_planner import plan_briefing_feedback_survey
from app.render_guard import (
    classify_markupgo_error,
    log_render_guard,
    markupgo_breaker_open,
    open_markupgo_breaker,
    promote_known_good_template_if_needed,
)


def _build_inline_markup(
    briefing_payload: dict[str, Any],
    save_ctx: Callable[[str], str],
) -> dict[str, Any] | None:
    inline_kb: list[list[dict[str, str]]] = []
    for row in briefing_payload.get("dynamic_buttons", []) or []:
        inline_kb.append(row)
    for opt in briefing_payload.get("options", []) or []:
        if opt and "Option" not in str(opt):
            inline_kb.append(
                [
                    {
                        "text": str(opt)[:40],
                        "callback_data": f"act:{save_ctx(f'Deep dive: {opt}')}",
                    }
                ]
            )
    return {"inline_keyboard": inline_kb} if inline_kb else None


async def _schedule_followups(
    *,
    safe_task: Callable[[str, Awaitable[Any]], Awaitable[Any]],
    send_newspaper_pdf: Callable[[int, str, dict[str, Any], str], Awaitable[bool]],
    tenant_name: str,
    tenant_cfg: dict[str, Any],
    chat_id: int,
    safe_txt: str,
    full_text: str,
) -> None:
    await safe_task(
        "Briefing PDF",
        send_newspaper_pdf(chat_id, tenant_name, tenant_cfg, full_text),
    )
    asyncio.create_task(
        safe_task(
            "Briefing Survey",
            plan_briefing_feedback_survey(
                tenant=(get_val(tenant_cfg, "google_account", "") or tenant_name),
                principal=str(chat_id),
                briefing_excerpt=safe_txt,
            ),
        )
    )


async def _enqueue_photo_outbox(
    *,
    tenant_name: str,
    chat_id: int,
    artifact_id: str,
    safe_txt: str,
) -> None:
    from app.outbox import enqueue_outbox

    delivery_session_id = await asyncio.to_thread(
        create_briefing_delivery_session,
        chat_id,
        status="pending",
    )
    payload: dict[str, Any] = {
        "type": "photo",
        "artifact_id": artifact_id,
        "caption": safe_txt[:1000] + ("..." if len(safe_txt) > 1000 else ""),
        "parse_mode": "HTML",
    }
    if delivery_session_id:
        payload["delivery_session_id"] = int(delivery_session_id)
    await asyncio.to_thread(enqueue_outbox, tenant_name, chat_id, payload)


async def _try_template_render_outbox(
    *,
    update_status: Callable[[str], Awaitable[None]],
    tenant_name: str,
    chat_id: int,
    txt: str,
    safe_txt: str,
) -> bool:
    if markupgo_breaker_open():
        raise RuntimeError("EA render guard: markupgo breaker open")

    from app.db import get_db
    from app.tools.markupgo_client import MarkupGoClient, render_request_hash

    await update_status("🎨 <i>Rendering visual briefing via MarkupGo...</i>")
    db = get_db()
    row = await asyncio.to_thread(
        db.fetchone,
        "SELECT template_id FROM template_registry WHERE key = 'briefing.image' AND is_active = TRUE ORDER BY version DESC LIMIT 1",
    )
    template_id = row["template_id"] if row else ""
    if not template_id:
        raise ValueError(
            "OODA: No active template found for 'briefing.image'. Act: Run SQL: INSERT INTO template_registry (tenant, key, provider, template_id) VALUES ('ea_bot', 'briefing.image', 'markupgo', 'YOUR_ID');"
        )
    template_id = promote_known_good_template_if_needed(str(template_id), tenant="ea_bot")
    if str(template_id).strip().lower().startswith("ooda_auto_tpl_") or str(template_id).strip().upper() == "YOUR_ID":
        raise RuntimeError("EA render guard: markupgo template not configured")

    context = {"briefing_text": txt}
    options = {"format": "png"}
    req_hash = render_request_hash(template_id, context, options, "png")
    cached = await asyncio.to_thread(
        db.fetchone,
        "SELECT artifact_id FROM render_cache WHERE tenant = 'ea_bot' AND render_request_hash = %s",
        (req_hash,),
    )

    artifacts_dir = os.path.join(os.environ.get("EA_ATTACHMENTS_DIR", "/attachments"), "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)

    img_bytes: bytes | None = None
    art_id: str | None = None
    if cached and os.path.exists(f"{artifacts_dir}/{cached['artifact_id']}.png"):
        art_id = cached["artifact_id"]
        with open(f"{artifacts_dir}/{cached['artifact_id']}.png", "rb") as f:
            img_bytes = f.read()
    else:
        mg = MarkupGoClient()
        payload = {
            "source": {
                "type": "template",
                "data": {"id": template_id, "context": context},
            },
            "options": options,
        }
        img_bytes = await mg.render_image_buffer(payload)
        art_id = str(uuid.uuid4())
        with open(f"{artifacts_dir}/{art_id}.png", "wb") as f:
            f.write(img_bytes)
        await asyncio.to_thread(
            db.execute,
            "INSERT INTO render_cache (tenant, render_request_hash, provider, format, artifact_id) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            ("ea_bot", req_hash, "markupgo", "png", art_id),
        )

    if not img_bytes or not art_id:
        return False
    await _enqueue_photo_outbox(
        tenant_name=tenant_name,
        chat_id=chat_id,
        artifact_id=art_id,
        safe_txt=safe_txt,
    )
    return True


async def _try_html_fallback_outbox(
    *,
    tenant_name: str,
    chat_id: int,
    txt: str,
    safe_txt: str,
    fallback_fault: str,
) -> bool:
    from app.tools.markupgo_client import MarkupGoClient

    plain = re.sub("<[^>]+>", "", txt)
    plain = plain[:3500]
    html_doc = (
        "<html><body style='margin:24px;font-family:Arial,sans-serif;'>"
        f"<div style='white-space:pre-wrap;font-size:22px;line-height:1.35;'>{html.escape(plain)}</div>"
        "</body></html>"
    )
    mg = MarkupGoClient()
    payload = {"source": {"type": "html", "data": html_doc}, "options": {"format": "png"}}
    img_bytes = await mg.render_image_buffer(payload)
    if not (img_bytes and img_bytes.startswith(b"\x89PNG")):
        return False

    art_id = str(uuid.uuid4())
    artifacts_dir = f"{os.environ.get('EA_ATTACHMENTS_DIR', '/attachments')}/artifacts"
    os.makedirs(artifacts_dir, exist_ok=True)
    with open(f"{artifacts_dir}/{art_id}.png", "wb") as f:
        f.write(img_bytes)

    await _enqueue_photo_outbox(
        tenant_name=tenant_name,
        chat_id=chat_id,
        artifact_id=art_id,
        safe_txt=safe_txt,
    )
    log_render_guard("renderer_html_fallback", fallback_fault, skill="markupgo", location="poll_listener")
    return True


async def run_brief_command(
    *,
    tg,
    chat_id: int,
    tenant_name: str,
    tenant_cfg: dict[str, Any],
    init_message_id: int,
    save_ctx: Callable[[str], str],
    clean_html: Callable[[str], str],
    send_newspaper_pdf: Callable[[int, str, dict[str, Any], str], Awaitable[bool]],
    safe_task: Callable[[str, Awaitable[Any]], Awaitable[Any]],
    incident_ref: Callable[[str], str],
) -> None:
    async def _update_status(msg_text: str) -> None:
        try:
            await tg.edit_message_text(
                chat_id,
                init_message_id,
                msg_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:
            pass

    try:
        briefing_payload = await asyncio.wait_for(
            build_briefing_for_tenant(tenant_cfg, status_cb=_update_status),
            timeout=240.0,
        )
        txt = briefing_payload.get("text", "⚠️ Error")
        markup = _build_inline_markup(briefing_payload, save_ctx)
        safe_txt = clean_html(txt)

        try:
            rendered = await _try_template_render_outbox(
                update_status=_update_status,
                tenant_name=tenant_name,
                chat_id=chat_id,
                txt=txt,
                safe_txt=safe_txt,
            )
            if rendered:
                await _schedule_followups(
                    safe_task=safe_task,
                    send_newspaper_pdf=send_newspaper_pdf,
                    tenant_name=tenant_name,
                    tenant_cfg=tenant_cfg,
                    chat_id=chat_id,
                    safe_txt=safe_txt,
                    full_text=txt,
                )
                try:
                    await tg.delete_message(chat_id, init_message_id)
                except Exception:
                    pass
                return
        except Exception as mg_err:
            fault = classify_markupgo_error(mg_err)
            if fault in ("invalid_template_id", "renderer_unavailable"):
                open_markupgo_breaker(fault, skill="markupgo", location="poll_listener")
            try:
                rendered = await _try_html_fallback_outbox(
                    tenant_name=tenant_name,
                    chat_id=chat_id,
                    txt=txt,
                    safe_txt=safe_txt,
                    fallback_fault=fault,
                )
                if rendered:
                    await _schedule_followups(
                        safe_task=safe_task,
                        send_newspaper_pdf=send_newspaper_pdf,
                        tenant_name=tenant_name,
                        tenant_cfg=tenant_cfg,
                        chat_id=chat_id,
                        safe_txt=safe_txt,
                        full_text=txt,
                    )
                    try:
                        await tg.delete_message(chat_id, init_message_id)
                    except Exception:
                        pass
                    return
            except Exception as html_fb_err:
                log_render_guard(
                    "renderer_html_fallback_failed",
                    str(html_fb_err)[:120],
                    skill="markupgo",
                    location="poll_listener",
                )

            try:
                open_repair_incident(
                    db_conn=None,
                    error_message=str(mg_err),
                    fallback_mode="simplified-first",
                    failure_class="renderer_fault",
                    intent="brief_render",
                    chat_id=str(chat_id),
                )
            except Exception:
                pass
            log_render_guard("renderer_text_only", fault, skill="markupgo", location="poll_listener")
            safe_txt += "\n\n📝 <i>Visual template unavailable, switched to safe text mode.</i>"

        try:
            delivery_session_id = await asyncio.to_thread(
                create_briefing_delivery_session,
                chat_id,
                status="active",
            )
            await tg.edit_message_text(
                chat_id,
                init_message_id,
                safe_txt,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=True,
            )
            if delivery_session_id:
                await asyncio.to_thread(activate_briefing_delivery_session, int(delivery_session_id))
            await _schedule_followups(
                safe_task=safe_task,
                send_newspaper_pdf=send_newspaper_pdf,
                tenant_name=tenant_name,
                tenant_cfg=tenant_cfg,
                chat_id=chat_id,
                safe_txt=safe_txt,
                full_text=txt,
            )
        except Exception as tg_err:
            print(f"Telegram HTML Parse Error: {tg_err}", flush=True)
            plain_txt = re.sub("<[^>]+>", "", txt).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            if len(plain_txt) > 4000:
                plain_txt = plain_txt[:4000] + "...[truncated]"
            try:
                delivery_session_id = await asyncio.to_thread(
                    create_briefing_delivery_session,
                    chat_id,
                    status="active",
                )
                await tg.edit_message_text(
                    chat_id,
                    init_message_id,
                    plain_txt,
                    parse_mode=None,
                    reply_markup=markup,
                    disable_web_page_preview=True,
                )
                if delivery_session_id:
                    await asyncio.to_thread(activate_briefing_delivery_session, int(delivery_session_id))
            except Exception:
                await tg.edit_message_text(
                    chat_id,
                    init_message_id,
                    "⚠️ Fatal error rendering briefing.",
                    parse_mode=None,
                )
    except Exception:
        ref = incident_ref("BRIEF")
        print(f"BRIEFING FAILED [{ref}] {traceback.format_exc()}", flush=True)
        await tg.edit_message_text(
            chat_id,
            init_message_id,
            f"⚠️ <b>Briefing Failed.</b>\nReference: <code>{ref}</code>",
            parse_mode="HTML",
        )
