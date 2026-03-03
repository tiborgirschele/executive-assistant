import asyncio
import contextlib
import httpx
import os
import traceback
from typing import Awaitable

from app.poll_listener import tg, handle_callback, handle_photo, handle_command

async def scheduler_loop():
    """Background loop for scheduled tasks."""
    while True:
        await asyncio.sleep(60)


async def _run_with_typing(chat_id: int | None, crash_label: str, handler: Awaitable[None]) -> None:
    keep_typing = True

    async def _typer() -> None:
        if not chat_id:
            return
        token = os.environ.get("EA_TELEGRAM_BOT_TOKEN")
        if not token:
            return
        async with httpx.AsyncClient() as hc:
            while keep_typing:
                try:
                    await hc.post(
                        f"https://api.telegram.org/bot{token}/sendChatAction",
                        json={"chat_id": chat_id, "action": "typing"},
                    )
                except Exception:
                    pass
                await asyncio.sleep(4)

    typing_task = asyncio.create_task(_typer())
    try:
        await handler
    except Exception as e:
        print(f"\n🔥 CRASH IN {crash_label}: {e}\n", flush=True)
        traceback.print_exc()
    finally:
        keep_typing = False
        typing_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await typing_task


async def send_briefing_and_poll():
    """Main Telegram poller loop with crash recovery and typing UX."""
    offset = 0
    while True:
        try:
            updates = await tg.get_updates(offset)
            for u in updates:
                offset = u["update_id"] + 1

                if "callback_query" in u:
                    callback = u["callback_query"]
                    callback_chat = callback.get("message", {}).get("chat", {}).get("id")
                    asyncio.create_task(
                        _run_with_typing(callback_chat, "CALLBACK", handle_callback(callback))
                    )
                elif "message" in u:
                    msg = u["message"]
                    chat_id = msg["chat"]["id"]
                    if msg.get("photo"):
                        asyncio.create_task(handle_photo(chat_id, msg))
                    elif msg.get("text") and msg["text"].startswith("/"):
                        asyncio.create_task(
                            _run_with_typing(chat_id, "COMMAND", handle_command(chat_id, msg["text"]))
                        )

        except Exception as e:
            print(f"Poller Warning: {e}", flush=True)
            await asyncio.sleep(5)
