import re, os

print("1️⃣ Deploying briefings.py (Positional Calendar IDs & Deep Diagnostics)...")
b_code = '''from __future__ import annotations
import re, json, httpx, asyncio, traceback, time, html
from datetime import datetime, timezone, timedelta
from app.gog import gog_cli
from app.settings import settings
from app.open_loops import OpenLoops

def _sanitize_telegram_html(text: str) -> str: return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _safe_extract_array(text: str) -> list:
    try:
        m = re.search(r"\\[[\\s\\S]*\\]", text)
        return json.loads(m.group(0)) if m else []
    except: return []

def _safe_extract_obj(text: str) -> dict:
    try:
        m = re.search(r"\\{[\\s\\S]*\\}", text)
        return json.loads(m.group(0)) if m else {}
    except: return {}

def get_val(obj, key, default=""):
    if isinstance(obj, dict): return obj.get(key, default)
    return getattr(obj, key, default)

async def safe_gog(container, cmd, account, timeout=20.0):
    try: return await asyncio.wait_for(gog_cli(container, cmd, account), timeout=timeout)
    except asyncio.TimeoutError: 
        await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", container, "sh", "-c", "pkill -f gog || true")
        raise TimeoutError(f"CLI hung on command: {' '.join(cmd[:3])}")

async def call_llm(prompt: str, temp=0.1) -> str:
    base = getattr(settings, "litellm_base_url", "http://litellm:4000")
    api_key = getattr(settings, "litellm_api_key", "")
    headers = {"Content-Type": "application/json"}
    if api_key: headers["Authorization"] = f"Bearer {api_key}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(base.rstrip("/") + "/v1/chat/completions", headers=headers, json={"model": getattr(settings, "llm_model", "gpt-4o"), "temperature": temp, "messages": [{"role": "user", "content": prompt}]})
        return r.json()['choices'][0]['message']['content']

async def build_briefing_for_tenant(tenant, status_cb=None) -> dict:
    t_openclaw = get_val(tenant, 'openclaw_container', '')
    t_account = get_val(tenant, 'google_account', '')
    t_key = get_val(tenant, 'key', 'tibor')
    
    ui_history = []
    diag_logs = []
    async def _log(msg):
        ui_history.append(f"✅ {msg}")
        if status_cb:
            try: await status_cb("\\n".join(ui_history) + "\\n<i>⚙️ Synthesizing...</i>")
            except: pass

    await _log("Fetching & Python Filtering Emails...")
    clean_mails = []
    try:
        raw_mails = await safe_gog(t_openclaw, ["gmail", "messages", "search", "newer_than:1d", "--limit", "40", "--json"], t_account)
        mails = _safe_extract_array(re.sub(r'\\x1b\\[[0-9;]*m', '', raw_mails))
        junk_kws = ['eff', 'andrew lock', 'ehrenkind', 'stack overflow', 'dodo', 'appsumo', 'dyson', 'facebook', 'linkedin', 'bestsecret', 'mediamarkt', 'voyage', 'babysits', 'stacksocial', 'digital trends', 'the futurist', 'newsletter', 'spiceworks', 'ikea', 'paypal', 'gog.com', 'steam', 'humble bundle', 'indie gala', 'promotions', 'penny', 'chummer', 'samsung', 'mtg', 'omi ai', 'omi', 'akupara', 'cinecenter', 'beta', 'early access', 'n8n']
        for m in mails:
            raw_val = json.dumps(m).lower()
            if any(j in raw_val for j in junk_kws): continue
            clean_mails.append(m)
            if len(clean_mails) >= 15: break
    except Exception as e: diag_logs.append(f"⚠️ Mails Err: {str(e)[:50]}")

    await _log("Fetching Calendars...")
    
    cal_ids = ["primary"]
    try:
        raw_cals = await safe_gog(t_openclaw, ["calendar", "list", "--json"], t_account, timeout=15.0)
        cals = _safe_extract_array(re.sub(r'\\x1b\\[[0-9;]*m', '', raw_cals))
        diag_logs.append(f"🔍 Discovered {len(cals)} total calendars.")
        found_names = []
        for c in cals:
            summary = str(c.get("summary", ""))
            found_names.append(summary)
            if any(kw in summary.lower() for kw in ["executive", "assistant", "ea"]):
                cal_ids.append(c.get("id"))
                diag_logs.append(f"✅ Found Cal: {summary} (ID: {c.get('id')[:8]})")
        if len(cal_ids) == 1:
            diag_logs.append(f"ℹ️ All Names: {', '.join(found_names)}")
    except Exception as e:
        diag_logs.append(f"⚠️ CalList Err: {str(e)[:50]}")

    clean_cal = []
    now = datetime.now(timezone.utc)
    
    for cid in list(set(cal_ids)):
        try:
            # 🚨 Passes cid as a POSITIONAL argument natively!
            raw_cal = await safe_gog(t_openclaw, ["calendar", "events", "list", cid, "--limit", "50", "--json"], t_account, timeout=25.0)
            events = _safe_extract_array(re.sub(r'\\x1b\\[[0-9;]*m', '', raw_cal))
            
            if not events:
                diag_logs.append(f"⚠️ Cal '{cid[:8]}' returned no events.")
                continue
                
            added = 0
            for ev in events:
                dt_str = ''
                end_val = ev.get('end', {})
                if isinstance(end_val, dict): dt_str = end_val.get('dateTime') or end_val.get('date') or ''
                elif isinstance(end_val, str): dt_str = end_val
                
                if dt_str:
                    dt_str = dt_str.replace('Z', '+00:00')
                    if ' ' in dt_str and '+' not in dt_str: dt_str = dt_str.replace(' ', 'T') + '+01:00'
                    try:
                        end_ts = datetime.fromisoformat(dt_str)
                        if end_ts.tzinfo is None: end_ts = end_ts.replace(tzinfo=timezone.utc)
                        if end_ts <= now - timedelta(hours=1): continue
                        clean_cal.append(ev)
                        added += 1
                    except:
                        try:
                            end_date = datetime.strptime(dt_str[:10], '%Y-%m-%d').date()
                            if end_date < now.date(): continue
                            clean_cal.append(ev)
                            added += 1
                        except: clean_cal.append(ev); added += 1
                else: clean_cal.append(ev); added += 1
                    
            diag_logs.append(f"✅ Cal '{cid[:8]}': {len(events)} raw -> kept {added} future.")
        except Exception as e: diag_logs.append(f"⚠️ Cal '{cid[:8]}' Err: {str(e)[:50]}")

    await _log("Synthesizing Executive Action Report...")
    prompt = f"""You are my elite Executive Assistant. I demand ACTIONABLE intelligence.
CRITICAL DIRECTIVES:
1. THE CULLING: YOU MUST COMPLETELY DELETE AND OMIT ANY promotional emails, newsletters, game betas, or trivial alerts. DO NOT include them with a note saying "ignore this". Delete them entirely.
2. CHURCHILL TONE: For the critical emails that remain, state brutally and concisely WHY it requires my attention in 1 sentence.
3. CALENDARS: Format ALL events provided in the JSON timeline into a clean schedule. Group them cleanly by Day/Date. Do not omit any future events. Note that these come from multiple calendars.

DATA:
Mails: {json.dumps(clean_mails)}
Calendars: {json.dumps(clean_cal)}

Return ONLY valid JSON matching this schema:
{{
  "emails": [{{"sender": "Sender", "subject": "Subject", "churchill_action": "1 sentence: What must I do?", "action_button": "Short Command"}}],
  "calendar_summary": "Clean, bulleted timeline of the schedule across all calendars, grouped by date."
}}"""

    out = await call_llm(prompt)
    try:
        obj = _safe_extract_obj(out)
        if not obj: raise ValueError("No valid JSON found in LLM response.")
        
        loops_txt, loop_btns = OpenLoops.get_dashboard(t_key)
        html_out = "🎩 <b>Executive Action Briefing</b>\\n\\n" + loops_txt
        options = []
        
        if obj.get("emails") and len(obj["emails"]) > 0:
            html_out += "<b>Requires Attention:</b>\\n"
            for e in obj["emails"]:
                s_name = _sanitize_telegram_html(e.get('sender', 'Unknown'))
                subj = _sanitize_telegram_html(e.get('subject', ''))
                reason = _sanitize_telegram_html(e.get('churchill_action', ''))
                html_out += f"• <b>{s_name}</b>: <i>{subj}</i>\\n  └ <i>{reason}</i>\\n\\n"
                if e.get('action_button'): options.append(e.get('action_button'))
        else:
            html_out += "<i>No critical items require your immediate attention.</i>\\n\\n"
            
        html_out += f"<b>Calendars:</b>\\n{_sanitize_telegram_html(obj.get('calendar_summary', 'No upcoming events.'))}"
        
        if diag_logs: html_out += "\\n\\n<i>⚙️ Diagnostics:</i>\\n<pre>" + html.escape("\\n".join(diag_logs), quote=False) + "</pre>"

        clean_opts = [str(o) for o in options if "Option" not in str(o)][:3]
        return {"text": html_out, "options": clean_opts, "dynamic_buttons": loop_btns}
    except Exception as e: return {"text": f"⚠️ <b>Fatal Briefing Error:</b>\\n<pre>{html.escape(str(e), quote=False)}</pre>", "options": ["🔁 Retry"]}
'''
with open("ea/app/briefings.py", "w") as f: f.write(b_code)


print("2️⃣ Deploying poll_listener.py (The Native '--manual' Auth Flow)...")
with open("ea/app/poll_listener.py", "r") as f: poll = f.read()

# Make sure html is imported
if "import html" not in poll:
    poll = poll.replace("import urllib.request", "import urllib.request, html")

new_auth = """# 🚨 THE HTML ESCAPER: Prevents "!doctype" crashes in Telegram
def _safe_err(e) -> str: 
    return html.escape(str(e), quote=False)

async def trigger_auth_flow(chat_id: int, email: str, t: dict, scopes: str = ""):
    if chat_id in AUTH_SESSIONS:
        try: AUTH_SESSIONS[chat_id]["proc"].kill()
        except: pass

    res = await tg.send_message(chat_id, f"🔄 Starting manual auth for <b>{email}</b>...\\n<i>⚙️ Requesting OAuth URL...</i>", parse_mode="HTML")
    proc = None
    t_openclaw = get_val(t, 'openclaw_container', 'openclaw-gateway-tibor')
    
    await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "sh", "-c", "pkill -f gog || true")
    await asyncio.sleep(0.5)

    try:
        # Step 1: Remove existing profile to guarantee clean slate
        await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "gog", "auth", "remove", email)
        await asyncio.sleep(0.5)

        # 🚨 Step 2: Use the magical --manual flag you discovered!
        cmd = ["docker", "exec", "-i", "-u", "root", "-e", f"GOG_KEYRING_PASSWORD={getattr(settings, 'gog_keyring_password', 'rangersofB5')}", t_openclaw, "gog", "auth", "add", email, "--manual"]
        if "calendar" in scopes: cmd.extend(["--services", "calendar"])
        elif "mail" in scopes: cmd.extend(["--services", "gmail"])
        else: cmd.extend(["--services", "all"])

        proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        
        google_url = None
        auth_logs = []
        for _ in range(40):
            try:
                line_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=1.0)
                if not line_bytes: break
                line = re.sub(r'\\x1b\\[[0-9;]*m', '', line_bytes.decode('utf-8', errors='ignore').strip())
                auth_logs.append(line)
                
                m_g = re.search(r'(https://accounts\\.google\\.com/[^\\s"\\'><]+)', line)
                if m_g:
                    google_url = m_g.group(1).replace('&amp;', '&')
                    break
            except asyncio.TimeoutError: pass
                    
        if google_url:
            AUTH_SESSIONS[chat_id] = {"state": "waiting_for_token", "proc": proc, "email": email}
            auth_msg = (
                f"🔗 <b>Authorization Required</b>\\n\\n"
                f"1. 👉 <b><a href='{google_url}'>Click here to open Google Login</a></b> 👈\\n"
                f"2. Log in and approve the permissions.\\n"
                f"3. Google will give you a verification code on the screen.\\n"
                f"4. <b>COPY that code and PASTE IT HERE in this chat.</b>"
            )
            await tg.edit_message_text(chat_id, res['message_id'], auth_msg, parse_mode="HTML", disable_web_page_preview=True)
        else:
            try: proc.kill()
            except: pass
            await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "sh", "-c", "pkill -f gog || true")
            logs = "\\n".join(auth_logs[-8:]) if auth_logs else "No output received."
            await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Failed to extract auth URL from manual prompt.</b>\\nLogs:\\n<pre>{_safe_err(logs)}</pre>", parse_mode="HTML")
            
    except Exception as e: 
        if proc: 
            try: proc.kill()
            except: pass
        await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "sh", "-c", "pkill -f gog || true")
        await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Auth Error:</b> {_safe_err(e)}", parse_mode="HTML")"""

poll = re.sub(r'def _safe_err\(e\).*?await tg\.edit_message_text\(chat_id, res\[\'message_id\'\], f"⚠️ <b>Auth Error:</b> \{_safe_err\(e\)\}.*?", parse_mode="HTML"\)', new_auth.strip(), poll, flags=re.DOTALL)

# Refine Handle Intent for Auth interception
auth_intent = """        if chat_id in AUTH_SESSIONS:
            if text_lower.startswith("/"):
                del AUTH_SESSIONS[chat_id]
                return await tg.send_message(chat_id, "🛑 Auth session aborted by command.")

            session = AUTH_SESSIONS.pop(chat_id)
            email = session["email"]
            
            # Extract code from URL if they pasted the full localhost link by mistake
            paste_text = text
            if "code=" in text:
                m = re.search(r'code=([^&\\s]+)', text)
                if m: paste_text = m.group(1)

            res = await tg.send_message(chat_id, "🔄 <i>⚙️ Processing authorization token...</i>", parse_mode="HTML")
            try:
                session["proc"].stdin.write(f"{paste_text}\\n".encode('utf-8'))
                await session["proc"].stdin.drain()
                await asyncio.wait_for(session["proc"].communicate(), timeout=30.0)
                try:
                    with open("/attachments/dynamic_users.json", "r") as f: dt = json.load(f)
                except: dt = {}
                if str(chat_id) not in dt: dt[str(chat_id)] = {}
                dt[str(chat_id)]["email"] = email
                
                tmp_file = "/attachments/dynamic_users.json.tmp"
                with open(tmp_file, "w") as f: json.dump(dt, f)
                os.replace(tmp_file, "/attachments/dynamic_users.json")
                
                await tg.edit_message_text(chat_id, res['message_id'], f"✅ <b>Authentication Successful for {email}!</b>", parse_mode="HTML")
            except Exception as e: await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ Error finalizing auth: {_safe_err(e)}", parse_mode="HTML")
            return"""

poll = re.sub(r'if chat_id in AUTH_SESSIONS.*?return', auth_intent.strip(), poll, flags=re.DOTALL)

with open("ea/app/poll_listener.py", "w") as f: f.write(poll)

print("✅ Golden Master V30 Files Prepared.")
