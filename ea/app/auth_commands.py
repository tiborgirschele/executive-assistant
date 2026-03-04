from __future__ import annotations

from typing import Callable


async def handle_auth_command(
    *,
    tg,
    chat_id: int,
    command_text: str,
    primary_account: str,
    save_ctx: Callable[[str], str],
) -> None:
    parts = str(command_text or "").strip().split(" ", 1)
    target_email = parts[1].strip() if len(parts) > 1 else ""
    account = str(primary_account or "").strip()

    if not target_email:
        keyboard: list[list[dict[str, str]]] = []
        if account:
            keyboard.extend(
                [
                    [{"text": f"🔑 All Features ({account})", "callback_data": f"auth_cb:{save_ctx(f'all|{account}')}"}],
                    [{"text": f"📅 Cal Only ({account})", "callback_data": f"auth_cb:{save_ctx(f'cal|{account}')}"}],
                ]
            )
        keyboard.append([{"text": "✏️ Type a different email...", "callback_data": "cmd_auth_custom"}])
        await tg.send_message(
            chat_id,
            "ℹ️ <b>Authentication</b>\nWhich Google Account do you want to authorize?",
            parse_mode="HTML",
            reply_markup={"inline_keyboard": keyboard},
        )
        return

    keyboard = [
        [{"text": "🔑 All Features", "callback_data": f"auth_cb:{save_ctx(f'all|{target_email}')}"}],
        [{"text": "📅 Calendar Only", "callback_data": f"auth_cb:{save_ctx(f'cal|{target_email}')}"}],
        [{"text": "✉️ Gmail Only", "callback_data": f"auth_cb:{save_ctx(f'mail|{target_email}')}"}],
        [{"text": "✏️ Type a different email...", "callback_data": "cmd_auth_custom"}],
        [{"text": "❌ Cancel", "callback_data": f"auth_cb:{save_ctx('cancel|none')}"}],
    ]
    await tg.send_message(
        chat_id,
        f"ℹ️ <b>Features for {target_email}</b>\nWhich features do you want to enable?",
        parse_mode="HTML",
        reply_markup={"inline_keyboard": keyboard},
    )
