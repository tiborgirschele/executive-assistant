from __future__ import annotations

import asyncio
import os
import re
from typing import Any, Callable

from app.briefings import get_val
from app.chat_assist import humanize_agent_report
from app.gog import gog_scout
from app.memory import save_button_context
from app.poll_ui import build_dynamic_ui, clean_html_for_telegram


async def handle_free_text_intent(
    *,
    tg,
    chat_id: int,
    text: str,
    tenant_cfg: dict[str, Any],
    safe_err: Callable[[Any], str],
) -> None:
    text_lower = str(text or "").lower()
    t_openclaw = get_val(
        tenant_cfg,
        "openclaw_container",
        os.environ.get("EA_DEFAULT_OPENCLAW_CONTAINER", "openclaw-gateway"),
    )
    active_res = await tg.send_message(chat_id, "▶️ <b>Analyzing request...</b>", parse_mode="HTML")
    urls = re.findall(r"(https?://[^\s]+)", text)
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
        scraped_data = await scrape_url(urls[0])
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
        kb_dict = build_dynamic_ui(report, prompt, save_ctx=save_button_context)
        clean_rep = clean_html_for_telegram(
            re.sub(r"\[OPTIONS:.*?\]", "", humanize_agent_report(report)).replace("[YES/NO]", "")
        )
        if not clean_rep.strip() or clean_rep.strip() == "[]":
            clean_rep = "✅ Task executed successfully!"
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
    except Exception as task_err:
        await tg.edit_message_text(
            chat_id,
            active_res["message_id"],
            f"❌ Agent Failed: {safe_err(task_err)}",
            parse_mode="HTML",
        )
