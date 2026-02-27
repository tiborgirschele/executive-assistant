import asyncio
from app.queue import claim_outbox_message, mark_outbox_sent, mark_outbox_error

async def run_outbox():
    print("==================================================", flush=True)
    print("📤 EA OS OUTBOX: ONLINE (Awaiting Traffic...)", flush=True)
    print("==================================================", flush=True)
    while True:
        try:
            msg = await asyncio.to_thread(claim_outbox_message)
            if not msg:
                await asyncio.sleep(0.5)
                continue
            # Future sending logic goes here. For now, we clear the queue.
            await asyncio.to_thread(mark_outbox_sent, message_id=msg["id"])
        except Exception as e:
            if 'msg' in locals() and msg: 
                try: await asyncio.to_thread(mark_outbox_error, message_id=msg["id"], attempt_count=msg.get("attempt_count", 0), error=str(e))
                except: pass
            await asyncio.sleep(5)
