import re, os

print("1️⃣ Deploying the Sentinel Watchdog (Hardware Level Protection)...")
with open("ea/app/poll_listener.py", "r") as f:
    code = f.read()

sentinel_code = """
# 🚨 THE SENTINEL WATCHDOG 🚨
import threading, time, os, urllib.request, json

LAST_HEARTBEAT = time.time()

def _watchdog_loop():
    while True:
        time.sleep(15)
        # If the main event loop hasn't updated the heartbeat in 120 seconds = FATAL DEADLOCK
        if time.time() - LAST_HEARTBEAT > 120:
            print("🚨 SENTINEL: System Deadlock Detected! Attempting escalation and restart...", flush=True)
            try:
                from app.settings import settings
                from app.config import get_admin_chat_id
                tok = getattr(settings, 'telegram_bot_token', None)
                admin = get_admin_chat_id()
                if tok and admin:
                    msg = "🚨 <b>Sentinel Alert:</b> Assistant AI suffered a fatal event loop deadlock. Executing emergency container restart to self-heal..."
                    url = f"https://api.telegram.org/bot{tok}/sendMessage"
                    data = json.dumps({"chat_id": admin, "text": msg, "parse_mode": "HTML"}).encode('utf-8')
                    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=5)
            except: pass
            
            # Kamikaze the Python process. Docker's 'restart: always' will instantly reboot it.
            os._exit(1)

threading.Thread(target=_watchdog_loop, daemon=True).start()
"""

if "LAST_HEARTBEAT = time.time()" not in code:
    code = code.replace("tg = TelegramClient(settings.telegram_bot_token)", "tg = TelegramClient(settings.telegram_bot_token)\n" + sentinel_code)


print("2️⃣ Injecting Workflow Timeout Guards into poll_listener.py...")
new_poll_loop = """
async def poll_loop():
    global LAST_HEARTBEAT
    print("🤖 Telegram Bot Poller: ACTIVE (Sentinel Guarded)", flush=True)
    from app.settings import settings
    if not settings.telegram_bot_token: return
    
    import os, json, asyncio, traceback
    
    # 🚨 NOTIFY BOOT
    try:
        from app.config import get_admin_chat_id
        admin_id = get_admin_chat_id()
        if admin_id:
            await tg.send_message(admin_id, "🔄 <b>System Online:</b> The EA Sentinel has successfully verified application startup and is standing guard.", parse_mode="HTML")
    except: pass

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
            LAST_HEARTBEAT = time.time()  # 💓 PET THE WATCHDOG
            
            updates = await tg.get_updates(offset)
            for u in updates:
                offset = u['update_id'] + 1
                
                # 🚨 Non-blocking write! Protects Event Loop from Disk I/O freezes.
                await asyncio.to_thread(_atomic_write_offset, offset)
                
                async def _route_update(u_data):
                    if 'callback_query' in u_data: await handle_callback(u_data['callback_query'])
                    elif 'message' in u_data:
                        msg = u_data['message']
                        chat_id = msg.get('chat', {}).get('id')
                        if not chat_id: return
                        cmd_text = str(msg.get('text') or msg.get('caption') or "").strip()
                        if cmd_text.startswith('/'): await handle_command(chat_id, cmd_text, msg)
                        elif msg.get('text') or msg.get('photo') or msg.get('document') or msg.get('voice') or msg.get('audio'): 
                            await handle_intent(chat_id, msg)

                async def _run_with_guard(u_data):
                    async with sem:
                        try:
                            # 🚨 THE ANTI-DEADLOCK GUARD (4 MINUTE TIMEOUT)
                            await asyncio.wait_for(_route_update(u_data), timeout=240.0)
                        except asyncio.TimeoutError:
                            print("🚨 SENTINEL: Task timed out after 4 minutes and was killed to free the semaphore.", flush=True)
                            try:
                                chat_id = u_data.get('message', {}).get('chat', {}).get('id') or u_data.get('callback_query', {}).get('message', {}).get('chat', {}).get('id')
                                if chat_id:
                                    await tg.send_message(chat_id, "⚠️ <b>Sentinel Guard Alert:</b>\nYour previous task hung for over 4 minutes and was forcefully terminated to prevent a system freeze.", parse_mode="HTML")
                            except: pass
                        except Exception as inner_e:
                            print(f"Update Route Crash: {traceback.format_exc()}", flush=True)
                
                asyncio.create_task(safe_task(_run_with_guard(u)))
                
        except Exception as e: 
            import traceback
            print(f"POLL LOOP CRASH: {traceback.format_exc()}", flush=True)
            await asyncio.sleep(5)
"""

code = re.sub(r'async def poll_loop\(\):[\s\S]*', new_poll_loop.strip(), code)

with open("ea/app/poll_listener.py", "w") as f:
    f.write(code)

print("✅ Sentinel Guard and Anti-Deadlock fixes applied.")
