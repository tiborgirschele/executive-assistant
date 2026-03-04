import asyncio
from app.telegram import TelegramClient
from app.settings import settings
from app.queue import ingest_update
from app.offset_store import atomic_write_offset, read_offset
import app.poll_listener as pl

async def run_poller():
    print("==================================================", flush=True)
    print("📡 EA OS POLLER: ONLINE (Listening to Telegram...)", flush=True)
    print("==================================================", flush=True)
    if not settings.telegram_bot_token: return
    tg = TelegramClient(settings.telegram_bot_token)
    
    # Keeps the watchdog thread from killing us
    asyncio.create_task(pl.heartbeat_pinger())
    
    offset = read_offset()
    
    while True:
        try:
            updates = await tg.get_updates(offset, timeout_s=30)
            for u in updates:
                update_id = u['update_id']
                offset = max(offset, update_id + 1)
                await asyncio.to_thread(atomic_write_offset, offset)
                
                tenant = "ea_bot"
                chat_id = None
                if 'message' in u:
                    chat_id = u['message'].get('chat', {}).get('id')
                elif 'callback_query' in u:
                    chat_id = u['callback_query'].get('message', {}).get('chat', {}).get('id')
                elif 'channel_post' in u:
                    chat_id = u['channel_post'].get('chat', {}).get('id')
                elif 'edited_channel_post' in u:
                    chat_id = u['edited_channel_post'].get('chat', {}).get('id')
                if chat_id: tenant = f"chat_{chat_id}"
                
                # Throw it instantly into the immortal Postgres Queue
                await asyncio.to_thread(ingest_update, tenant=tenant, update_id=update_id, payload=u)
                print(f"📥 Poller: Ingested update {update_id} into DB.", flush=True)
        except Exception as e:
            print(f"🚨 POLLER ERROR: {e}", flush=True)
            await asyncio.sleep(5)
