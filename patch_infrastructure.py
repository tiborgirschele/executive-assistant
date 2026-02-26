import re, os

print("1️⃣ Patching vision.py (Delegating to llm_vision)...")
vision_code = """from __future__ import annotations
import traceback
from app.llm_vision import complete_json_with_image

async def extract_calendar_from_image(image_bytes: bytes, mime_type: str) -> dict:
    prompt = '''Extract all appointments from this image. 
    Return ONLY a JSON object with this exact schema:
    {"events": [{"title": "Name of event", "start": "YYYY-MM-DD HH:MM", "end": "YYYY-MM-DD HH:MM", "location": "Optional"}]}
    If end time is missing, assume 1 hour duration.
    '''
    try:
        res = await complete_json_with_image(prompt, image_bytes, mime=mime_type, timeout_s=90.0)
        if "events" not in res:
            res["events"] = []
        return res
    except Exception as e:
        print(f"Vision API Error: {e}\\n{traceback.format_exc()}", flush=True)
        return {"events": [], "error": str(e)}
"""
with open("ea/app/vision.py", "w") as f:
    f.write(vision_code)


print("2️⃣ Patching poll_listener.py (Atomic Saves & Forensic Logging)...")
with open("ea/app/poll_listener.py", "r") as f:
    poll_code = f.read()

new_code = """
def _atomic_write_offset(offset: int):
    import os, json
    offset_file = "/attachments/tg_offset.json"
    tmp_file = offset_file + ".tmp"
    try:
        os.makedirs("/attachments", exist_ok=True)
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({"offset": offset}, f)
            f.flush()
            os.fsync(f.fileno())  # Force OS to write to physical hardware platter
        os.replace(tmp_file, offset_file)  # Atomic OS-level rename
    except Exception as e: 
        print(f"Offset Write Error: {e}", flush=True)

async def safe_task(coro):
    try: await coro
    except Exception as e: 
        import traceback
        print(f"Task Crash: {traceback.format_exc()}", flush=True)

async def poll_loop():
    print("🤖 Telegram Bot Poller: ACTIVE (Atomic Safety)", flush=True)
    from app.settings import settings
    if not settings.telegram_bot_token: return
    
    import os, json, asyncio, traceback
    offset = 0
    offset_file = "/attachments/tg_offset.json"
    os.makedirs("/attachments", exist_ok=True)
    if os.path.exists(offset_file):
        try:
            with open(offset_file, "r") as f: offset = json.load(f).get("offset", 0)
        except: pass

    sem = asyncio.Semaphore(15)

    while True:
        try:
            updates = await tg.get_updates(offset)
            for u in updates:
                offset = u['update_id'] + 1
                
                # 🚨 ATOMIC WRITE: Ensures updates are recorded safely
                _atomic_write_offset(offset)
                
                async def _run(u_data):
                    async with sem:
                        if 'callback_query' in u_data: await handle_callback(u_data['callback_query'])
                        elif 'message' in u_data:
                            msg = u_data['message']
                            chat_id = msg['chat']['id']
                            cmd_text = str(msg.get('text') or msg.get('caption') or "").strip()
                            if cmd_text.startswith('/'): await handle_command(chat_id, cmd_text, msg)
                            elif msg.get('text') or msg.get('photo') or msg.get('document') or msg.get('voice') or msg.get('audio'): 
                                await handle_intent(chat_id, msg)
                
                asyncio.create_task(safe_task(_run(u)))
                
        except Exception as e: 
            # 🚨 FORENSIC LOGGING: No more silent crashes
            import traceback
            print(f"POLL LOOP CRASH: {traceback.format_exc()}", flush=True)
            await asyncio.sleep(5)
"""

# Surgically replace the end of the file
poll_code = re.sub(r'async def safe_task\(coro\):[\s\S]*', new_code.strip(), poll_code)

with open("ea/app/poll_listener.py", "w") as f:
    f.write(poll_code)

print("✅ Scripts patched successfully.")
