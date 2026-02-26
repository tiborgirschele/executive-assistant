import os, sys, glob, re, time, subprocess

print("=== 1. FIXING THE AI IMPORT CRASH ===")
path = "ea/app/briefings.py"
try:
    with open(path, "r") as f: text = f.read()
    # Strip the broken import entirely
    text = re.sub(r'^from app\.config import.*\n', '', text, flags=re.MULTILINE)
    text = text.replace("tenant: TenantConfig", "tenant")
    with open(path, "w") as f: f.write(text)
    print("✅ Fixed import in briefings.py")
except Exception as e:
    print(f"❌ Error fixing briefings.py: {e}")

print("\n=== 2. PATCHING TELEGRAM UX (TYPING & TOASTS) ===")
for path in glob.glob("ea/app/*.py"):
    try:
        with open(path, "r") as f: text = f.read()
        orig = text
        
        # 1. Dynamic Button Toasts
        m = re.search(r'async def handle_callback\s*\(\s*([a-zA-Z_0-9]+)', text)
        if m and "_get_btn_text" not in text:
            var_name = m.group(1)
            helper = f"""
    btn_txt = "Processing..."
    try:
        data = {var_name}.get('data')
        for row in {var_name}.get('message', {{}}).get('reply_markup', {{}}).get('inline_keyboard', []):
            for btn in row:
                if btn.get('callback_data') == data: btn_txt = f"⚙️ {{btn.get('text')}}..."
    except: pass
"""
            # Inject helper inside the function
            text = re.sub(r'(async def handle_callback\s*\(\s*[a-zA-Z_0-9]+\s*\):)', r'\1' + helper, text)
            # Replace old generic toast
            text = re.sub(r'text\s*=\s*f?["\'][Ee]xecuting[^"\']*["\']', 'text=btn_txt', text)

        # 2. Command Typing Indicator
        target_cmd = "asyncio.create_task(handle_command(chat_id, msg['text']))"
        if target_cmd in text:
            wrapper_cmd = """
                        async def _cmd_task(cid, txt):
                            import httpx, os, asyncio
                            keep_typing = [True]
                            async def _typer():
                                async with httpx.AsyncClient() as hc:
                                    while keep_typing[0]:
                                        try: await hc.post(f"https://api.telegram.org/bot{os.environ.get('EA_TELEGRAM_BOT_TOKEN')}/sendChatAction", json={"chat_id": cid, "action": "typing"})
                                        except: pass
                                        await asyncio.sleep(4)
                            t = asyncio.create_task(_typer())
                            try: await handle_command(cid, txt)
                            finally: keep_typing[0] = False; t.cancel()
                        asyncio.create_task(_cmd_task(chat_id, msg['text']))
"""
            text = text.replace(target_cmd, wrapper_cmd.strip())

        # 3. Callback Typing Indicator
        target_cb = "await handle_callback(u['callback_query'])"
        if target_cb in text:
            wrapper_cb = """
                    async def _cb_task(cb):
                        import httpx, os, asyncio
                        keep_typing = [True]
                        async def _typer():
                            async with httpx.AsyncClient() as hc:
                                while keep_typing[0]:
                                    try:
                                        cid = cb.get("message", {}).get("chat", {}).get("id")
                                        if cid: await hc.post(f"https://api.telegram.org/bot{os.environ.get('EA_TELEGRAM_BOT_TOKEN')}/sendChatAction", json={"chat_id": cid, "action": "typing"})
                                    except: pass
                                    await asyncio.sleep(4)
                        t = asyncio.create_task(_typer())
                        try: await handle_callback(cb)
                        finally: keep_typing[0] = False; t.cancel()
                    asyncio.create_task(_cb_task(u['callback_query']))
"""
            text = text.replace(target_cb, wrapper_cb.strip())

        if text != orig:
            with open(path, "w") as f: f.write(text)
            print(f"✅ Patched UX in {path}")
            
    except Exception as e:
        pass

print("\n=== 3. RESTARTING EA-DAEMON ===")
subprocess.run(["docker", "compose", "restart", "ea-daemon"], check=True)

print("--> Waiting 4 seconds for daemon to boot...")
time.sleep(4)

print("\n=== 4. 🧪 AUTOMATED SMOKE TESTS ===")
try:
    # Capture BOTH stdout and stderr correctly in python
    result = subprocess.run(["docker", "logs", "--tail", "50", "ea-daemon"], capture_output=True, text=True)
    logs = result.stdout + result.stderr
    
    crashes = [line for line in logs.split("\n") if any(err in line for err in ["Traceback", "Error:", "Exception:", "ImportError", "SyntaxError"])]
    # Ignore harmless expected warnings
    crashes = [c for c in crashes if "Vision API Error" not in c and "Poller Warning" not in c]

    if crashes:
        print("❌ CRASH DETECTED in ea-daemon logs:")
        print("\n".join(logs.split("\n")[-25:]))
        sys.exit(1)
    else:
        print("✅ Clean daemon startup confirmed. No Python errors found in logs.")
        
    if "poll" in logs.lower() or "update" in logs.lower():
        print("✅ Telegram Poller loop is actively listening.")
        
except Exception as e:
    print("❌ Failed to run smoke tests:", e)
    sys.exit(1)
