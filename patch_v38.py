import re

print("1️⃣ Fixing briefings.py (TypeError Crash Fix)...")
with open("ea/app/briefings.py", "r", encoding="utf-8") as f: code = f.read()

# Fix the TypeError in HTML sanitizer
code = code.replace('.replace("<ol>", "").replace("</ol>")', '.replace("<ol>", "").replace("</ol>", "")')
with open("ea/app/briefings.py", "w", encoding="utf-8") as f: f.write(code)


print("2️⃣ Deploying poll_listener.py (Robust HTML Auth Flow)...")
with open("ea/app/poll_listener.py", "r", encoding="utf-8") as f: poll = f.read()

# Fix the TypeError in HTML sanitizer here too
poll = poll.replace('.replace("<ol>", "").replace("</ol>")', '.replace("<ol>", "").replace("</ol>", "")')

# 🚨 THE BULLETPROOF WGET AUTH ENGINE 🚨
new_auth = """async def trigger_auth_flow(chat_id: int, email: str, t: dict, scopes: str = ""):
    if chat_id in AUTH_SESSIONS:
        try: AUTH_SESSIONS[chat_id]["proc"].kill()
        except: pass

    res = await tg.send_message(chat_id, f"🔄 Starting auth for <b>{email}</b>...\\n<i>⚙️ Requesting OAuth URL...</i>", parse_mode="HTML")
    port = "unknown"
    proc = None
    t_openclaw = get_val(t, 'openclaw_container', 'openclaw-gateway-tibor')
    
    await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "sh", "-c", "pkill -f gog 2>/dev/null || true")
    await asyncio.sleep(0.5)

    try:
        cmd = ["docker", "exec", "-i", "-e", f"GOG_ACCOUNT={email}", t_openclaw, "gog", "auth", "login"]
        if "cal" in scopes: cmd.extend(["--scopes", "calendar"])
        elif "mail" in scopes: cmd.extend(["--scopes", "gmail"])
        proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        
        google_url = None
        auth_logs = []
        for _ in range(40):
            try:
                line_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=1.0)
                if not line_bytes: break
                line = re.sub(r'\\x1b\\[[0-9;]*m', '', line_bytes.decode('utf-8', errors='ignore').strip())
                auth_logs.append("CLI: " + line)
                
                m_loc = re.search(r'(http://(?:127\\.0\\.0\\.1|localhost):(\\d+))', line)
                if m_loc:
                    port = m_loc.group(2)
                    local_url = f"http://127.0.0.1:{port}"
                    
                    # 🚨 Fetch HTML body instead of headers!
                    cmd_sh = f"wget -qO- {local_url} 2>&1 || curl -sL {local_url} 2>&1"
                    await asyncio.sleep(1.5)
                    try:
                        c_proc = await asyncio.create_subprocess_exec("docker", "exec", t_openclaw, "sh", "-c", cmd_sh, stdout=asyncio.subprocess.PIPE)
                        c_out, _ = await asyncio.wait_for(c_proc.communicate(), timeout=5.0)
                        extracted = c_out.decode('utf-8', errors='ignore').strip()
                        
                        m_url = re.search(r'(https://accounts\\.google\\.com/[^\\s"\\'><]+)', extracted)
                        if m_url: 
                            google_url = m_url.group(1).replace('&amp;', '&').strip()
                            break
                    except Exception as e: auth_logs.append(f"Sniper Err: {e}")
                    break
            except asyncio.TimeoutError: pass
                    
        if google_url:
            AUTH_SESSIONS[chat_id] = {"state": "waiting_for_token", "proc": proc, "email": email, "openclaw": t_openclaw, "port": port}
            auth_msg = (
                f"🔗 <b>Authorization Required</b>\\n\\n"
                f"1. 👉 <b><a href='{google_url}'>Click here to open Google Login</a></b> 👈\\n"
                f"2. ⚠️ <b>CRITICAL: Ensure you select <code>{email}</code></b> in the Google screen!\\n"
                f"3. Google will redirect you to a broken localhost page.\\n"
                f"4. <b>COPY the full broken URL from your browser's address bar and PASTE IT HERE.</b>"
            )
            await tg.edit_message_text(chat_id, res['message_id'], auth_msg, parse_mode="HTML", disable_web_page_preview=True)
        else:
            try: proc.kill()
            except: pass
            await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "sh", "-c", "pkill -f gog 2>/dev/null || true")
            logs = "\\n".join(auth_logs[-8:]) if auth_logs else "No output received."
            await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Failed to extract auth URL natively.</b>\\nLogs:\\n<pre>{_safe_err(logs)}</pre>\\nPort: {port}", parse_mode="HTML")
            
    except Exception as e: 
        if proc: 
            try: proc.kill()
            except: pass
        await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "sh", "-c", "pkill -f gog 2>/dev/null || true")
        await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Auth Error:</b> {_safe_err(e)}\\nPort: {port}", parse_mode="HTML")"""

poll = re.sub(r'async def trigger_auth_flow[\s\S]*?(?=async def handle_callback)', new_auth + '\n\n', poll)


auth_intent = """        if chat_id in AUTH_SESSIONS and ("localhost" in text_lower or "127.0.0.1" in text_lower or "code=" in text_lower):
            if text_lower.startswith("/"):
                try: AUTH_SESSIONS[chat_id]["proc"].kill()
                except: pass
                del AUTH_SESSIONS[chat_id]
                return await tg.send_message(chat_id, "🛑 Auth session aborted by command.")

            session = AUTH_SESSIONS.pop(chat_id)
            email = session["email"]
            proc = session["proc"]
            t_openclaw = session["openclaw"]
            port = session.get("port", "8080")
            
            res = await tg.send_message(chat_id, "🔄 <i>⚙️ Routing callback to container...</i>", parse_mode="HTML")
            try:
                # Reconstruct the exact URL the container is listening on
                m_query = re.search(r'(/oauth2/callback\\?[^\\s]+)', text)
                if m_query: clean_url = f"http://127.0.0.1:{port}{m_query.group(1)}"
                else: clean_url = text.strip()
                    
                # wget inside Docker to trigger the callback!
                await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "sh", "-c", f"wget -qO- '{clean_url}'")
                await asyncio.wait_for(proc.wait(), timeout=10.0)
                
                # 🚨 THE VALIDATOR: Ensure the user selected the right account!
                auth_list_proc = await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", "-e", f"GOG_KEYRING_PASSWORD={getattr(settings, 'gog_keyring_password', 'rangersofB5')}", t_openclaw, "gog", "auth", "list", stdout=asyncio.subprocess.PIPE)
                stdout, _ = await asyncio.wait_for(auth_list_proc.communicate(), timeout=5.0)
                auth_list = stdout.decode('utf-8', errors='ignore')
                clean_auth_list = re.sub(r'\\x1b\\[[0-9;]*m', '', auth_list).strip()
                
                if email.lower() not in auth_list.lower():
                    await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Account Mismatch Detected!</b>\\nWe expected <b>{email}</b>, but it was not successfully linked. Did you select the wrong account in the browser?\\n\\nActive accounts:\\n<pre>{_safe_err(clean_auth_list)}</pre>", parse_mode="HTML")
                else:
                    try:
                        with open("/attachments/dynamic_users.json", "r") as f: dt = json.load(f)
                    except: dt = {}
                    if str(chat_id) not in dt: dt[str(chat_id)] = {}
                    dt[str(chat_id)]["email"] = email
                    _atomic_write_json("/attachments/dynamic_users.json", dt)
                    await tg.edit_message_text(chat_id, res['message_id'], f"✅ <b>Authentication Successful for {email}!</b>\\n\\nRun /brief to generate your action report.", parse_mode="HTML")
            except Exception as e: 
                try: proc.kill()
                except: pass
                await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ Error routing callback: {_safe_err(e)}", parse_mode="HTML")
            return"""

poll = re.sub(r'if chat_id in AUTH_SESSIONS.*?return', auth_intent.strip(), poll, flags=re.DOTALL)

with open("ea/app/poll_listener.py", "w", encoding="utf-8") as f: f.write(poll)

print("✅ Golden Master V38 Files Prepared.")
