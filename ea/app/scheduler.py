import asyncio
import httpx
import os
import traceback
from app.poll_listener import tg, handle_callback, handle_photo, handle_command

async def scheduler_loop():
    """Background loop for scheduled tasks."""
    while True:
        await asyncio.sleep(60)

async def send_briefing_and_poll():
    """Main Telegram poller loop with crash recovery and typing UX."""
    offset = 0
    while True:
        try:
            updates = await tg.get_updates(offset)
            for u in updates:
                offset = u['update_id'] + 1
                
                if 'callback_query' in u:
                    cb = u['callback_query']
                    async def _cb_task(callback):
                        chat_id = callback.get("message", {}).get("chat", {}).get("id")
                        keep = True
                        async def _typer():
                            async with httpx.AsyncClient() as hc:
                                while keep and chat_id:
                                    try: await hc.post(f"https://api.telegram.org/bot{os.environ.get('EA_TELEGRAM_BOT_TOKEN')}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                                    except: pass
                                    await asyncio.sleep(4)
                        t = asyncio.create_task(_typer())
                        try:
                            await handle_callback(callback)
                        except Exception as e:
                            print(f"\n🔥 CRASH IN CALLBACK: {e}\n", flush=True)
                            traceback.print_exc()
                        finally:
                            keep = False
                            t.cancel()
                    asyncio.create_task(_cb_task(cb))
                    
                elif 'message' in u:
                    msg = u['message']
                    chat_id = msg['chat']['id']
                    if msg.get('photo'):
                        asyncio.create_task(handle_photo(chat_id, msg))
                    elif msg.get('text') and msg['text'].startswith('/'):
                        async def _cmd_task(cid, txt):
                            keep = True
                            async def _typer():
                                async with httpx.AsyncClient() as hc:
                                    while keep and cid:
                                        try: await hc.post(f"https://api.telegram.org/bot{os.environ.get('EA_TELEGRAM_BOT_TOKEN')}/sendChatAction", json={"chat_id": cid, "action": "typing"})
                                        except: pass
                                        await asyncio.sleep(4)
                        t = asyncio.create_task(_typer())
                        try:
                            await handle_command(cid, txt)
                        except Exception as e:
                            print(f"\n🔥 CRASH IN COMMAND: {e}\n", flush=True)
                            traceback.print_exc()
                        finally:
                            keep = False
                            t.cancel()
                        asyncio.create_task(_cmd_task(chat_id, msg['text']))

        except Exception as e:
            print(f"Poller Warning: {e}", flush=True)
            await asyncio.sleep(5)