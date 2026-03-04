from __future__ import annotations

import asyncio
import os
import re
import time
from typing import Any, Callable

from app.briefings import get_val
from app.chat_assist import humanize_agent_report
from app.execution import (
    append_execution_event,
    build_plan_steps,
    compile_intent_spec,
    create_execution_session,
    finalize_execution_session,
    mark_execution_session_running,
    mark_execution_step_status,
)
from app.gog import gog_scout
from app.memory import save_button_context
from app.poll_ui import build_dynamic_ui, clean_html_for_telegram


async def handle_free_text_intent(
    *,
    tg,
    chat_id: int,
    tenant_name: str,
    text: str,
    tenant_cfg: dict[str, Any],
    safe_err: Callable[[Any], str],
) -> None:
    text_lower = str(text or "").lower()
    tenant_key = str(tenant_name or "")
    t_openclaw = get_val(
        tenant_cfg,
        "openclaw_container",
        os.environ.get("EA_DEFAULT_OPENCLAW_CONTAINER", "openclaw-gateway"),
    )
    active_res = await tg.send_message(chat_id, "▶️ <b>Analyzing request...</b>", parse_mode="HTML")
    urls = re.findall(r"(https?://[^\s]+)", text)
    intent_spec = compile_intent_spec(text=text, tenant=tenant_key, chat_id=chat_id, has_url=bool(urls))
    plan_steps = build_plan_steps(intent_spec=intent_spec)
    session_id = create_execution_session(
        tenant=tenant_key,
        chat_id=chat_id,
        intent_spec=intent_spec,
        plan_steps=plan_steps,
        source="telegram_free_text",
        correlation_id=f"{tenant_key}:{chat_id}:{int(time.time() * 1000)}",
    )
    current_step = "compile_intent"
    if session_id:
        mark_execution_session_running(session_id)
        mark_execution_step_status(session_id, "compile_intent", "completed", result=intent_spec)
        append_execution_event(
            session_id,
            event_type="intent_compiled",
            message="Intent compiled from free-text request.",
            payload={"domain": intent_spec.get("domain"), "intent_type": intent_spec.get("intent_type")},
        )
    if urls and any((w in text_lower for w in ["read", "scrape", "summarize", "check", "extract", "what"])):
        from app.tools.browseract import scrape_url

        try:
            await tg.edit_message_text(
                chat_id,
                active_res["message_id"],
                "🌐 <b>Scraping website with BrowserAct...</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        current_step = "gather_evidence"
        if session_id:
            mark_execution_step_status(
                session_id,
                "gather_evidence",
                "running",
                evidence={"url": urls[0]},
            )
        try:
            scraped_data = await scrape_url(urls[0])
        except Exception as scrape_err:
            if session_id:
                mark_execution_step_status(
                    session_id,
                    "gather_evidence",
                    "failed",
                    error_text=safe_err(scrape_err),
                    evidence={"url": urls[0]},
                )
                append_execution_event(
                    session_id,
                    level="error",
                    event_type="evidence_failed",
                    message="URL evidence scrape failed.",
                    payload={"url": urls[0]},
                )
            raise
        if session_id:
            mark_execution_step_status(
                session_id,
                "gather_evidence",
                "completed",
                evidence={"url": urls[0], "snippet_chars": len(str(scraped_data)[:3000])},
            )
            append_execution_event(
                session_id,
                event_type="evidence_collected",
                message="URL evidence collected for intent execution.",
                payload={"url": urls[0]},
            )
        prompt = (
            "EXECUTE: The user sent a link. I scraped it for you using BrowserAct. "
            f"Here is the website content:\n\n{str(scraped_data)[:3000]}\n\n"
            f"User request: '{text}'. Be concise."
        )
    else:
        prompt = f"EXECUTE: Answer or execute the user request: '{text}'. Be concise."

    async def _ui_updater(msg: str) -> None:
        try:
            await tg.edit_message_text(
                chat_id,
                active_res["message_id"],
                f"▶️ <b>{msg[:80]}...</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    try:
        if session_id and any(str((row or {}).get("step_key") or "") == "safety_gate" for row in plan_steps):
            mark_execution_step_status(
                session_id,
                "safety_gate",
                "running",
                result={"gate_mode": "passive", "reason": "assistive free-text execution"},
            )
            mark_execution_step_status(
                session_id,
                "safety_gate",
                "completed",
                result={"gate_mode": "passive", "decision": "continue"},
            )
        current_step = "execute_intent"
        if session_id:
            mark_execution_step_status(session_id, "execute_intent", "running")
        report = await asyncio.wait_for(
            gog_scout(
                t_openclaw,
                prompt,
                get_val(tenant_cfg, "google_account", ""),
                _ui_updater,
                task_name="Intent: Free Text",
            ),
            timeout=240.0,
        )
        if session_id:
            mark_execution_step_status(
                session_id,
                "execute_intent",
                "completed",
                result={"report_chars": len(str(report or ""))},
            )
        kb_dict = build_dynamic_ui(report, prompt, save_ctx=save_button_context)
        clean_rep = clean_html_for_telegram(
            re.sub(r"\[OPTIONS:.*?\]", "", humanize_agent_report(report)).replace("[YES/NO]", "")
        )
        if not clean_rep.strip() or clean_rep.strip() == "[]":
            clean_rep = "✅ Task executed successfully!"
        current_step = "render_reply"
        if session_id:
            mark_execution_step_status(session_id, "render_reply", "running")
        try:
            await tg.edit_message_text(
                chat_id,
                active_res["message_id"],
                f"🎯 <b>Result:</b>\n\n{clean_rep[:3500]}",
                parse_mode="HTML",
                reply_markup=kb_dict,
            )
        except Exception:
            plain_txt = (
                re.sub("<[^>]+>", "", clean_rep)
                .replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
            )
            if len(plain_txt) > 4000:
                plain_txt = plain_txt[:4000] + "\n...[truncated]"
            try:
                await tg.edit_message_text(
                    chat_id,
                    active_res["message_id"],
                    f"🎯 <b>Result:</b>\n\n{plain_txt}",
                    parse_mode=None,
                    reply_markup=kb_dict,
                )
            except Exception:
                pass
        if session_id:
            mark_execution_step_status(
                session_id,
                "render_reply",
                "completed",
                result={"payload_chars": len(str(clean_rep or ""))},
            )
            finalize_execution_session(
                session_id,
                status="completed",
                outcome={
                    "result": "delivered",
                    "payload_chars": len(str(clean_rep or "")),
                    "report_chars": len(str(report or "")),
                },
            )
    except Exception as task_err:
        if session_id:
            mark_execution_step_status(
                session_id,
                current_step,
                "failed",
                error_text=safe_err(task_err),
            )
            append_execution_event(
                session_id,
                level="error",
                event_type="session_failed",
                message="Free-text execution failed.",
                payload={"step": current_step},
            )
            finalize_execution_session(
                session_id,
                status="failed",
                last_error=safe_err(task_err),
                outcome={"result": "failed", "failed_step": current_step},
            )
        await tg.edit_message_text(
            chat_id,
            active_res["message_id"],
            f"❌ Agent Failed: {safe_err(task_err)}",
            parse_mode="HTML",
        )
