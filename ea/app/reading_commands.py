from __future__ import annotations


async def handle_articles_pdf_command(*, tg, chat_id: int, tenant_name: str, tenant_cfg: dict, send_pdf_func) -> None:
    wait_msg = await tg.send_message(
        chat_id,
        "🗞️ <i>Building reading PDF from BrowserAct...</i>",
        parse_mode="HTML",
    )
    sent = await send_pdf_func(chat_id, tenant_name, tenant_cfg, force=True)
    if sent:
        try:
            await tg.delete_message(chat_id, wait_msg.get("message_id"))
        except Exception:
            pass
        return
    await tg.edit_message_text(
        chat_id,
        wait_msg["message_id"],
        "🗞️ No qualifying Economist/Atlantic/NYT BrowserAct articles in the last 7 days.",
        parse_mode="HTML",
    )
