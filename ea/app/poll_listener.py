from __future__ import annotations
import httpx, asyncio, os, sys, traceback, re, json, io, base64, urllib.parse, time, threading, html
from datetime import datetime, timezone
import urllib.request
from app.config import get_tenant, get_admin_chat_id, load_tenants, tenant_by_chat_id
from app.gog import gog_scout, gog_cli
from app.settings import settings
from app.telegram import TelegramClient
from app.vision import extract_calendar_from_image
from app.sepa_qr import generate_epc_qr
from app.sepa_xml import generate_pain001_xml
from app.open_loops import OpenLoops
from app.briefings import build_briefing_for_tenant, get_val, call_llm

# 🚨 CHATGPT ENTERPRISE ARCHITECTURE: Postgres State Integration
from app.pg_state import set_auth, get_and_clear_auth, clear_auth, save_action, get_action

def save_button_context(prompt: str) -> str: return save_action(prompt)
def get_button_context(action_id: str) -> str | None: return get_action(action_id)

LAST_HEARTBEAT = time.time()
def _watchdog_loop():
    while True:
        time.sleep(15)
        if time.time() - LAST_HEARTBEAT > 300:
            print("🚨 SENTINEL: System Deadlock Detected! Restarting...", flush=True)
            try:
                tok = getattr(settings, 'telegram_bot_token', None)
                admin = get_admin_chat_id()
                if tok and admin:
                    msg = "🚨 <b>Sentinel Alert:</b> Assistant AI suffered a fatal event loop deadlock. Executing emergency container restart to self-heal..."
                    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data=json.dumps({"chat_id": admin, "text": msg, "parse_mode": "HTML"}).encode('utf-8'), headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=5)
            except: pass
            os._exit(1)
threading.Thread(target=_watchdog_loop, daemon=True).start()

async def heartbeat_pinger():
    global LAST_HEARTBEAT
    while True:
        LAST_HEARTBEAT = time.time()
        await asyncio.sleep(10)

tg = TelegramClient(settings.telegram_bot_token)

def _atomic_write_json(path: str, data: dict):
    tmp = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception as e: print(f"Atomic Write Error: {e}", flush=True)

def _atomic_write_offset(offset: int):
    _atomic_write_json("/attachments/tg_offset.json", {"offset": offset})

def clean_html_for_telegram(text: str) -> str:
    if not text: return ""
    t = text.replace("<br>", "\n").replace("<br/>", "\n").replace("</p>", "\n\n").replace("<p>", "")
    t = t.replace("<ul>", "").replace("</ul>", "").replace("<ol>", "").replace("</ol>", "")
    t = t.replace("<li>", "• ").replace("</li>", "\n").replace("<h1>", "\n\n<b>").replace("</h1>", "</b>\n").replace("<h2>", "\n\n<b>").replace("</h2>", "</b>\n")
    t = t.replace("<strong>", "<b>").replace("</strong>", "</b>").replace("<em>", "<i>").replace("</em>", "</i>")
    t = t.replace("<html>", "").replace("</html>", "").replace("<body>", "").replace("</body>", "").replace("<div>", "").replace("</div>", "")
    t = re.sub(r'&(?![A-Za-z0-9#]+;)', '&amp;', t)
    def repl(m):
        tag = m.group(1).lower()
        if tag in ['b', 'i', 'a', 'code', 'pre', 's', 'u']: return m.group(0)
        return ""
    t = re.sub(r'</?([a-zA-Z0-9]+)[^>]*>', repl, t)
    return re.sub(r'\n{3,}', '\n\n', t).strip()

def _safe_err(e) -> str: 
    return html.escape(str(e), quote=False)

async def check_security(chat_id: int) -> tuple[str, dict]:
    t = get_tenant(chat_id)
    if t: return get_val(t, 'key', 'tibor'), t
    try:
        if os.path.exists("/attachments/dynamic_users.json"):
            with open("/attachments/dynamic_users.json", "r") as f: dt = json.load(f)
            if str(chat_id) in dt:
                u_info = dt[str(chat_id)]
                return f"guest_{chat_id}", {"key": f"guest_{chat_id}", "label": u_info.get("name", "Guest"), "google_account": u_info.get("email", ""), "openclaw_container": "openclaw-gateway-tibor", "is_admin": u_info.get("is_admin", False)}
    except: pass
    return None, None

def build_dynamic_ui(report_text: str, context_prompt: str, fwd_name: str = None) -> dict:
    kb = []
    if fwd_name:
        if "liz" in fwd_name.lower() or "elisabeth" in fwd_name.lower(): kb.append([{"text": f"🤖 Ask to reply to {fwd_name}", "callback_data": f"fwd_liz:{save_button_context(report_text)}"}])
        else: kb.append([{"text": f"📤 Forward to {fwd_name}", "url": f"https://t.me/share/url?url={urllib.parse.quote('Antwort:\n'+report_text)}"}])
    opt_match = re.search(r'\[OPTIONS:\s*(.+?)\]', report_text)
    if opt_match:
        for opt in [o.strip() for o in opt_match.group(1).split('|') if o.strip()][:5]:
            is_rej = any(w in opt.lower() for w in ["do not", "no", "cancel", "stop", "abort", "skip"])
            if is_rej: kb.append([{"text": f"🎯 {opt}", "callback_data": f"act:{save_button_context(f'CONTINUING TASK:\n{context_prompt[:1500]}\n\nUser selected: {opt}. REJECTED. Propose alternatives.')}"}])
            else: kb.append([{"text": f"🎯 {opt}", "callback_data": f"act:{save_button_context(f'CONTINUING TASK:\n{context_prompt[:1500]}\n\nUser selected: {opt}. Proceed.')}"}])
    return {"inline_keyboard": kb} if kb else None

async def handle_photo(chat_id: int, msg: dict): await handle_intent(chat_id, msg)

async def native_calendar_import(chat_id: int, t: dict, events: list):
    res = await tg.send_message(chat_id, "🔄 <i>Starting native calendar import...</i>", parse_mode="HTML")
    try:
        t_openclaw = get_val(t, 'openclaw_container', '')
        t_account = get_val(t, 'google_account', '')
        cal_id = "Executive Assistant"
        
        await tg.edit_message_text(chat_id, res['message_id'], "🔄 <i>Checking for duplicates...</i>", parse_mode="HTML")
        raw_events = await asyncio.wait_for(gog_cli(t_openclaw, ["calendar", "events", "list", "--calendar", cal_id, "--limit", "50", "--json"], t_account), timeout=15)
        existing = json.loads(re.search(r"\[.*\]", re.sub(r'\x1b\[[0-9;]*m', '', raw_events), re.DOTALL).group(0))
        
        log = "🎯 <b>Native Import Result:</b>\n\n"
        for ev in events:
            title = str(ev.get("title", ""))
            start = str(ev.get("start", ""))
            end = str(ev.get("end", ""))
            loc = str(ev.get("location", ""))
            ev_date = start[:10] if start else ""
            clean_title = title.lower()[:8]
            
            is_dup = False
            for ex in existing:
                ex_title = str(ex.get("summary", "")).lower()
                ex_start = ex.get("start", {}).get("dateTime") or ex.get("start", {}).get("date") or ""
                if ev_date and ev_date in ex_start and clean_title in ex_title:
                    is_dup = True
                    break
            
            if is_dup: log += f"⚠️ <b>{title}</b>: Skipped (Duplicate)\n"
            else:
                try:
                    args = ["calendar", "events", "add", title, "--calendar", cal_id]
                    if start: args.extend(["--start", start])
                    if end: args.extend(["--end", end])
                    if loc: args.extend(["--location", loc])
                    await asyncio.wait_for(gog_cli(t_openclaw, args, t_account), timeout=10)
                    log += f"✅ <b>{title}</b>: Added!\n"
                except Exception as ex: log += f"❌ <b>{title}</b>: Failed ({ex})\n"
                    
        await tg.edit_message_text(chat_id, res['message_id'], log, parse_mode="HTML")
    except asyncio.TimeoutError: await tg.edit_message_text(chat_id, res['message_id'], "⚠️ <b>Timeout:</b> GOG CLI hung. Check auth.", parse_mode="HTML")
    except Exception as e: await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Crash:</b> {_safe_err(e)}", parse_mode="HTML")

# 🚨 ADMIN-AWARE REMOTE FLOW
async def trigger_auth_flow(chat_id: int, email: str, t: dict, scopes: str = ""):
    res = await tg.send_message(chat_id, f"🔄 Generating secure OAuth link for <b>{email}</b>...", parse_mode="HTML")
    t_openclaw = get_val(t, 'openclaw_container', 'openclaw-gateway-tibor')
    is_admin = get_val(t, 'is_admin', False) or get_val(t, 'key', '') == 'tibor'
    
    await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "sh", "-c", "pkill -f gog 2>/dev/null || true")
    await asyncio.sleep(0.5)

    try:
        await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "sh", "-c", f"gog auth remove {email} 2>/dev/null || true")
        await asyncio.sleep(0.5)

        scopes_arg = "gmail,calendar,tasks"
        if "cal" in scopes: scopes_arg = "calendar"
        elif "mail" in scopes: scopes_arg = "gmail"
        
        cmd = ["docker", "exec", "-u", "root", "-e", f"GOG_KEYRING_PASSWORD={getattr(settings, 'gog_keyring_password', 'rangersofB5')}", t_openclaw, "gog", "auth", "add", email, "--services", scopes_arg, "--remote", "--step", "1"]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
        out_str = stdout.decode('utf-8', errors='ignore')
        
        m_url = re.search(r'(https://accounts\.google\.com/[^\s"\'><]+)', out_str)
        if m_url:
            google_url = m_url.group(1).replace('&amp;', '&').strip()
            
            # 🚨 POSTGRES AUTH SAVE
            set_auth(chat_id, email, t_openclaw, scopes_arg)
            
            if is_admin:
                admin_note = (
                    f"\n\n💡 <b>Admin Troubleshooting:</b>\n"
                    f"• <b>'Ineligible Account':</b> Google blocks <code>{email}</code> from being a Test User. <b>Fix:</b> Open Google Calendar on the web for {email} and share the target calendar directly with your primary account!\n"
                    f"• <b>403 Access Denied:</b> Add <code>{email}</code> to the <a href='https://console.cloud.google.com/apis/credentials/consent'>OAuth Test Users list in Google Cloud Console</a>."
                )
            else:
                admin_note = "\n\n<i>⏳ If Google shows an 'Ineligible Account' or '403' error, do not panic. The administrator has been notified to grant you access or share the calendar manually. Please wait for their confirmation.</i>"
                admin_id = get_admin_chat_id()
                if admin_id and str(admin_id) != str(chat_id):
                    try: await tg.send_message(admin_id, f"🚨 <b>Auth Intervention Required</b>\nUser <code>{email}</code> is trying to log in but may hit a 403 or Ineligible Account error.\nAs Admin, please ensure they are added to the <a href='https://console.cloud.google.com/apis/credentials/consent'>Google Cloud OAuth Test Users list</a>!", parse_mode="HTML", disable_web_page_preview=True)
                    except: pass
            
            auth_msg = (
                f"🔗 <b>Authorization Required</b>\n\n"
                f"1. 👉 <b><a href='{google_url}'>Click here to open Google Login</a></b> 👈\n"
                f"2. ⚠️ <b>CRITICAL: Ensure you select <code>{email}</code></b> in the Google screen!\n"
                f"3. Google will eventually redirect you to a broken page that says 'This site can't be reached'.\n"
                f"4. 🛑 <b>THIS IS NORMAL!</b> Copy the full broken URL from your browser's address bar and <b>PASTE IT HERE</b> in this chat."
                f"{admin_note}"
            )
            await tg.edit_message_text(chat_id, res['message_id'], auth_msg, parse_mode="HTML", disable_web_page_preview=True)
        else:
            await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Failed to extract auth URL from Remote Flow.</b>\nLogs:\n<pre>{_safe_err(out_str[-1000:])}</pre>", parse_mode="HTML")
            
    except Exception as e: 
        await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Auth Error:</b> {_safe_err(e)}", parse_mode="HTML")

async def handle_callback(cb):
    chat_id = cb.get('message', {}).get('chat', {}).get('id')
    tenant_name, t = await check_security(chat_id)
    if not t: return await tg.answer_callback_query(cb['id'], text="Unauthorized.", show_alert=True)

    if cb['data'] == "cmd_auth_custom":
        await tg.answer_callback_query(cb['id'])
        return await tg.send_message(chat_id, "Please type the command manually:\n<code>/auth your.email@gmail.com</code>", parse_mode="HTML")

    if cb['data'].startswith("auth_cb:"):
        ctx_id = cb['data'].split(":")[1]
        payload = get_button_context(ctx_id)
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass

        if not payload: return await tg.send_message(chat_id, "⚠️ Auth session expired. Please type /auth again.")
        try: scope_type, email = payload.split("|", 1)
        except ValueError: return await tg.send_message(chat_id, "⚠️ Invalid auth payload.")

        if scope_type == "cancel":
            clear_auth(chat_id)
            return await tg.send_message(chat_id, "🛑 Auth cancelled.")
        
        await trigger_auth_flow(chat_id, email, t, scopes=scope_type)
        return

    if cb['data'] == "clear_shopping":
        OpenLoops.clear_shopping(tenant_name)
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass
        return await tg.send_message(chat_id, "✅ <b>Shopping List marked as Done.</b>", parse_mode="HTML")

    if cb['data'].startswith("mark_paid:"):
        OpenLoops.remove_payment(tenant_name, cb['data'].split(":")[1])
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass
        return await tg.send_message(chat_id, "✅ <b>Rechnung als bezahlt markiert.</b>", parse_mode="HTML")

    if cb['data'].startswith("drop_pay:"):
        OpenLoops.remove_payment(tenant_name, cb['data'].split(":")[1])
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass
        return await tg.send_message(chat_id, "🗑️ <b>Zahlungs-Loop gelöscht.</b>", parse_mode="HTML")

    if cb['data'].startswith("exec_cal:"):
        cid = cb['data'].split(":")[1]
        cal_data = OpenLoops.get_calendar(tenant_name, cid)
        if cal_data:
            OpenLoops.remove_calendar(tenant_name, cid)
            try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
            except: pass
            from app.briefings import safe_gog
            t_openclaw = get_val(t, 'openclaw_container', '')
            t_account = get_val(t, 'google_account', '')
            for ev in cal_data["events"]:
                try: await safe_gog(t_openclaw, ["calendar", "events", "add", str(ev.get("title", "")), "--calendar", "Executive Assistant"], t_account, timeout=10.0)
                except: pass
            await tg.send_message(chat_id, "✅ <b>Calendar Events Imported.</b>", parse_mode="HTML")
        return

    if cb['data'].startswith("drop_cal:"):
        cid = cb['data'].split(":")[1]
        OpenLoops.remove_calendar(tenant_name, cid)
        await tg.answer_callback_query(cb['id'], text="Import Dropped!")
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass
        return await tg.send_message(chat_id, "🛑 <b>Calendar Import Discarded.</b>", parse_mode="HTML")

    is_trusted = get_val(t, 'is_admin', False) or get_val(t, 'key', '') in ['tibor', 'liz', 'family']
    sec_rule = "" if is_trusted else "GUEST. CRITICAL: FORBIDDEN from reading /mnt/."
    ooda_rule = "OODA LOOP: Actively propose alternatives via `[OPTIONS: A | B]`."
    
    if cb['data'].startswith("act:"):
        action_id = cb['data'][4:]
        rich_prompt = get_button_context(action_id)
        if not rich_prompt: return await tg.answer_callback_query(cb['id'], text="⚠️ Action expired.", show_alert=True)
        btn_txt = "Task"
        for row in cb.get("message", {}).get("reply_markup", {}).get("inline_keyboard", []):
            for btn in row:
                if btn.get("callback_data") == cb.get("data"): btn_txt = btn.get("text", "Task")
        
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass
        await tg.answer_callback_query(cb['id'], text="Executing...")

        clean_btn = btn_txt.replace("✅", "").replace("⚙️", "").replace("🎯", "").strip()
        is_rejection = any(w in clean_btn.lower() for w in ["do not", "no", "cancel", "stop", "reject", "abort", "skip"])
        if is_rejection: enhanced_prompt = f"EXECUTE: {rich_prompt}\nCRITICAL UPDATE: The user REJECTED the previous proposal."
        else: enhanced_prompt = f"EXECUTE: {rich_prompt}\nCRITICAL INSTRUCTIONS:\n1. You MUST use the google account '{get_val(t, 'google_account','')}'.\n2. Focus ONLY on this specific request."

        res = await tg.send_message(chat_id, f"🚀 <b>Executing:</b> {clean_btn}...\n\n<i>⚙️ Analyzing task requirements...</i>", parse_mode="HTML")
        async def _ui_updater(msg):
            try: await tg.edit_message_text(chat_id, res['message_id'], f"🚀 <b>Executing:</b> {clean_btn}...\n\n<i>⚙️ {msg}</i>", parse_mode="HTML", disable_web_page_preview=True)
            except: pass

        try:
            report = await asyncio.wait_for(gog_scout(get_val(t, 'openclaw_container', 'openclaw-gateway-tibor'), enhanced_prompt, get_val(t, 'google_account',''), _ui_updater, task_name=f"Button: {clean_btn}"), timeout=240.0)
            kb_dict = build_dynamic_ui(report, enhanced_prompt)
            clean_rep = clean_html_for_telegram(re.sub(r'\[OPTIONS:.*?\]', '', report).replace("[YES/NO]", ""))
            if clean_rep.strip().lower() in ["completed", "completed.", "[]", ""]: clean_rep = "✅ Task executed successfully!"
            try: await tg.edit_message_text(chat_id, res['message_id'], f"🎯 <b>Result:</b>\n\n{clean_rep[:3500]}", parse_mode="HTML", reply_markup=kb_dict)
            except: await tg.edit_message_text(chat_id, res['message_id'], f"🎯 <b>Result:</b>\n\n{_safe_err(clean_rep).strip()[:3500]}", reply_markup=kb_dict)
        except Exception as task_err: await tg.send_message(chat_id, f"❌ Task Failed: {_safe_err(task_err)}")

async def handle_intent(chat_id: int, msg: dict):
    try:
        tenant_name, t = await check_security(chat_id)
        text = str(msg.get("text") or msg.get("caption") or "").strip()
        text_lower = text.lower()

        if not t: return

        doc = msg.get("document")
        photo = msg.get("photo")
        
        low_stock_words = ["katzenfutter", "cat food", "futter", "brot", "milch", "kaffee", "coffee", "einkaufsliste"]
        if any(w in text_lower for w in low_stock_words) and any(w in text_lower for w in ["kaufen", "leer", "aus", "fast kein", "brauchen", "setz"]):
            OpenLoops.add_shopping(tenant_name, text)
            return await tg.send_message(chat_id, f"🛒 <b>Added to Shopping List Open Loop:</b>\n{text}", parse_mode="HTML")

        if any(kw in text_lower for kw in ["zahl", "rechnung", "pay", "sepa", "iban"]) and "kannst du" in text_lower:
            pid = OpenLoops.add_payment(tenant_name, "Zahlung gewünscht (Missing PDF)", "?", "?", status="needs_doc")
            kb = [[{"text": "🛑 Drop Payment", "callback_data": f"drop_pay:{pid}"}]]
            return await tg.send_message(chat_id, "📌 <b>Zahlung notiert (Open Loop).</b>\n\nBitte sende die Rechnung als PDF hier in den Chat, damit ich IBAN/Betrag extrahieren kann.", parse_mode="HTML", reply_markup={"inline_keyboard": kb})

        is_pdf = bool(doc and ("pdf" in str(doc.get("mime_type", "")).lower() or str(doc.get("file_name", "")).lower().endswith(".pdf")))
        is_invoice = any(kw in text_lower for kw in ["zahl", "rechnung", "pay", "sepa", "iban"]) or (is_pdf and (not text_lower or "rechnung" in str(doc.get("file_name", "")).lower()))
        is_image_calendar = bool(photo or (doc and str(doc.get("mime_type", "")).startswith("image/"))) and not is_invoice

        # 🚨 POSTGRES REMOTE VALIDATOR
        sess = get_and_clear_auth(chat_id)
        if sess and ("localhost" in text_lower or "127.0.0.1" in text_lower or "code=" in text_lower or "state=" in text_lower):
            if text_lower.startswith("/"):
                return await tg.send_message(chat_id, "🛑 Auth session aborted by command.")

            email = sess["email"]
            t_openclaw = sess["container"]
            services = sess["services"]
            
            res = await tg.send_message(chat_id, "🔄 <i>⚙️ Verifying OAuth token via remote step 2...</i>", parse_mode="HTML")
            try:
                pasted_url = re.search(r'(http[^\s]+)', text)
                url_to_pass = pasted_url.group(1) if pasted_url else text.strip()
                
                cmd = ["docker", "exec", "-u", "root", "-e", f"GOG_KEYRING_PASSWORD={getattr(settings, 'gog_keyring_password', 'rangersofB5')}", t_openclaw, "gog", "auth", "add", email, "--services", services, "--remote", "--step", "2", "--auth-url", url_to_pass]
                proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20.0)
                out_str = stdout.decode('utf-8', errors='ignore') + "\n" + stderr.decode('utf-8', errors='ignore')
                
                if "error" in out_str.lower() or "failed" in out_str.lower() or "invalid" in out_str.lower():
                    await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Token Exchange Failed!</b>\n<pre>{_safe_err(out_str)}</pre>", parse_mode="HTML")
                else:
                    chk_proc = await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", "-e", f"GOG_KEYRING_PASSWORD={getattr(settings, 'gog_keyring_password', 'rangersofB5')}", t_openclaw, "gog", "auth", "list", stdout=asyncio.subprocess.PIPE)
                    chk_out, _ = await asyncio.wait_for(chk_proc.communicate(), timeout=5.0)
                    auth_list = chk_out.decode('utf-8', errors='ignore')
                    
                    if email.lower() not in auth_list.lower():
                        await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Account Mismatch Detected!</b>\nWe expected you to approve <b>{email}</b>, but you selected a different account in the Google pop-up.\n\nActive accounts:\n<pre>{_safe_err(auth_list.strip())}</pre>\n\nPlease type <code>/auth {email}</code> and try again.", parse_mode="HTML")
                        await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", t_openclaw, "gog", "auth", "remove", email)
                    else:
                        try:
                            with open("/attachments/dynamic_users.json", "r") as f: dt = json.load(f)
                        except: dt = {}
                        if str(chat_id) not in dt: dt[str(chat_id)] = {}
                        dt[str(chat_id)]["email"] = email
                        _atomic_write_json("/attachments/dynamic_users.json", dt)
                        await tg.edit_message_text(chat_id, res['message_id'], f"✅ <b>Authentication Successful for {email}!</b>\n\nRun /brief to pull your calendars.", parse_mode="HTML")
            except Exception as e: 
                await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Error exchanging token:</b> {_safe_err(e)}\n\n<pre>{_safe_err(out_str if 'out_str' in locals() else '')}</pre>", parse_mode="HTML")
            return

        if sess and text: set_auth(chat_id, sess["email"], sess["container"], sess["services"])

        if is_image_calendar:
            res = await tg.send_message(chat_id, "🖼️ <b>Photo received. Extracting schedule...</b>", parse_mode="HTML")
            try:
                file_id = photo[-1]['file_id'] if photo else doc['file_id']
                meta = await tg.get_file(file_id)
                img_bytes = await tg.download_file_bytes(meta['file_path'])
                extracted = await extract_calendar_from_image(img_bytes, "image/jpeg")
                events = extracted.get("events", [])
                if not events: return await tg.edit_message_text(chat_id, res['message_id'], "⚠️ No calendar events detected.")
                
                preview = "📅 <b>Found Events:</b>\n" + "".join([f"• {e.get('start')} - {e.get('title')}\n" for e in events])
                cid = OpenLoops.add_calendar(tenant_name, preview, events)
                kb = [[{"text": f"✅ Execute Import to EA", "callback_data": f"exec_cal:{cid}"}], [{"text": f"🛑 Discard", "callback_data": f"drop_cal:{cid}"}]]
                await tg.edit_message_text(chat_id, res['message_id'], preview + "\n\n<i>This import request has been added to your Open Loops.</i>", parse_mode="HTML", reply_markup={"inline_keyboard": kb})
            except Exception as e: await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ Vision Error: {_safe_err(e)}", parse_mode="HTML")
            return

        if is_invoice:
            res = await tg.send_message(chat_id, "💸 <b>Rechnung erkannt.</b>\nLese Daten aus...", parse_mode="HTML")
            try:
                file_id = doc["file_id"] if doc else photo[-1]["file_id"]
                meta = await tg.get_file(file_id)
                file_bytes = await tg.download_file_bytes(meta['file_path'])
                
                if is_pdf:
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                        pdf_text = "\n".join([page.extract_text() for page in reader.pages[:3] if page.extract_text()])
                        prompt = f"Extract invoice details. Return ONLY JSON matching {{\"iban\":\"AT...\", \"amount\":12.34, \"creditor\":\"Name\", \"reference\":\"Ref\"}}.\nText:\n{pdf_text[:4000]}"
                        sepa_json = await call_llm(prompt)
                    except Exception as pe: print(f"PyPDF Error: {pe}", flush=True); sepa_json = "{}"
                else:
                    b64_img = base64.b64encode(file_bytes).decode('utf-8')
                    body = {"model": getattr(settings, "llm_model", "gpt-4o"), "messages": [{"role": "user", "content": [{"type": "text", "text": 'Extract invoice details. Return ONLY JSON: {"iban": "AT...", "amount": 12.34, "creditor": "Name", "reference": "Ref"}'}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}]}]}
                    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {getattr(settings, 'litellm_api_key', '')}"}
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        resp = await client.post(getattr(settings, "litellm_base_url", "http://litellm:4000").rstrip("/") + "/v1/chat/completions", json=body, headers=headers)
                        sepa_json = resp.json()['choices'][0]['message']['content']

                m = re.search(r"\{[\s\S]*\}", sepa_json)
                if m:
                    sepa_data = json.loads(m.group(0))
                    if sepa_data.get("iban") and sepa_data.get("amount"):
                        amt = f"{float(sepa_data['amount']):.2f}"
                        pid = OpenLoops.add_payment(tenant_name, sepa_data.get("creditor","Unknown"), amt, sepa_data.get("iban"))
                        qr_bytes, _ = generate_epc_qr(sepa_data.get("creditor",""), sepa_data.get("iban",""), float(sepa_data.get("amount",0)), sepa_data.get("reference",""))
                        xml_bytes = generate_pain001_xml(sepa_data.get("creditor",""), sepa_data.get("iban",""), float(sepa_data.get("amount",0)), sepa_data.get("reference",""))
                        if qr_bytes and xml_bytes:
                            copy_block = f"📋 <b>Copy-Block</b>\nEmpfänger: <code>{sepa_data.get('creditor')}</code>\nIBAN: <code>{sepa_data['iban']}</code>\nBetrag: <code>{amt}</code>\nZweck: <code>{sepa_data.get('reference')}</code>"
                            kb = [[{"text": "✅ Als bezahlt markieren", "callback_data": f"mark_paid:{pid}"}]]
                            await tg.edit_message_text(chat_id, res['message_id'], "✅ <b>Daten extrahiert! Rechnung zu Open Loops hinzugefügt.</b>", parse_mode="HTML")
                            await tg.send_document(chat_id, xml_bytes.encode('utf-8'), "SEPA_Transfer.xml")
                            await tg.send_photo(chat_id, qr_bytes, caption=f"📱 <b>EPC-QR Code</b>\n\n{copy_block}", parse_mode="HTML", reply_markup={"inline_keyboard": kb})
                            try: await tg.delete_message(chat_id, res['message_id'])
                            except: pass
                            return
            except Exception as e: print(f"Vision/PDF Error: {e}", flush=True)
            try: await tg.edit_message_text(chat_id, res['message_id'], "⚠️ Konnte IBAN oder Betrag nicht eindeutig lesen.", parse_mode="HTML")
            except: pass
            return

        # 🚨 THE LOBOTOMY REVERSAL: Free-Text Agent is fully restored here!
        if text and not is_invoice and not is_image_calendar and not text.startswith("/") and not ("localhost" in text_lower or "127.0.0.1" in text_lower or "code=" in text_lower or "state=" in text_lower):
            t_openclaw = get_val(t, 'openclaw_container', 'openclaw-gateway-tibor')
            active_res = await tg.send_message(chat_id, "<i>⚙️ Analyzing request...</i>", parse_mode="HTML")
            prompt = f"EXECUTE: Answer or execute the user request: '{text}'. Be concise."
            
            async def _ui_updater(m):
                try: await tg.edit_message_text(chat_id, active_res['message_id'], f"<i>⚙️ {m[:80]}...</i>", parse_mode="HTML")
                except: pass
                
            try:
                report = await asyncio.wait_for(gog_scout(t_openclaw, prompt, get_val(t, 'google_account',''), _ui_updater, task_name="Intent: Free Text"), timeout=240.0)
                kb_dict = build_dynamic_ui(report, prompt)
                clean_rep = clean_html_for_telegram(re.sub(r'\[OPTIONS:.*?\]', '', report).replace("[YES/NO]", ""))
                if not clean_rep.strip() or clean_rep.strip() == "[]": clean_rep = "✅ Task executed successfully!"
                
                try: await tg.edit_message_text(chat_id, active_res['message_id'], f"🎯 <b>Result:</b>\n\n{clean_rep[:3500]}", parse_mode="HTML", reply_markup=kb_dict)
                except: await tg.edit_message_text(chat_id, active_res['message_id'], f"🎯 <b>Result:</b>\n\n{_safe_err(clean_rep).strip()[:3500]}", reply_markup=kb_dict)
            except Exception as task_err:
                await tg.edit_message_text(chat_id, active_res['message_id'], f"❌ Agent Failed: {_safe_err(task_err)}", parse_mode="HTML")
            return

    except Exception as e:
        print(f"INTENT CRASH: {traceback.format_exc()}", flush=True)

async def handle_command(chat_id: int, text: str, msg: dict):
    try:
        tenant_name, t = await check_security(chat_id)
        if not t: return 
        
        parts = text.strip().split(" ", 1)
        cmd = parts[0].lower().split('@')[0]

        if cmd == "/auth":
            target_email = parts[1].strip() if len(parts) > 1 else ""
            t_acc = get_val(t, 'google_account', 'tibor.girschele@gmail.com')
            
            if not target_email:
                kb = [
                    [{"text": f"🔑 All ({t_acc})", "callback_data": f"auth_cb:{save_button_context(f'all|{t_acc}')}"}],
                    [{"text": f"📅 Cal Only ({t_acc})", "callback_data": f"auth_cb:{save_button_context(f'cal|{t_acc}')}"}],
                    [{"text": "🔑 archon.megalon@gmail.com (All)", "callback_data": f"auth_cb:{save_button_context('all|archon.megalon@gmail.com')}"}],
                    [{"text": "✏️ Type a different email...", "callback_data": "cmd_auth_custom"}]
                ]
                return await tg.send_message(chat_id, "ℹ️ <b>Authentication</b>\nWhich Google Account do you want to authorize?", parse_mode="HTML", reply_markup={"inline_keyboard": kb})
            else:
                kb = [
                    [{"text": "🔑 All Scopes", "callback_data": f"auth_cb:{save_button_context(f'all|{target_email}')}"}],
                    [{"text": "📅 Calendar Only", "callback_data": f"auth_cb:{save_button_context(f'cal|{target_email}')}"}],
                    [{"text": "✉️ Gmail Only", "callback_data": f"auth_cb:{save_button_context(f'mail|{target_email}')}"}],
                    [{"text": "✏️ Type a different email...", "callback_data": "cmd_auth_custom"}],
                    [{"text": "❌ Cancel", "callback_data": f"auth_cb:{save_button_context('cancel|none')}"}]
                ]
                return await tg.send_message(chat_id, f"ℹ️ <b>Scopes for {target_email}</b>\nWhich permissions do you want to grant?", parse_mode="HTML", reply_markup={"inline_keyboard": kb})

        if cmd == "/brief":
            res = await tg.send_message(chat_id, "<i>Initializing...</i>", parse_mode="HTML")
            async def _update_status(msg_text):
                try: await tg.edit_message_text(chat_id, res['message_id'], msg_text, parse_mode="HTML", disable_web_page_preview=True)
                except: pass

            try:
                b = await asyncio.wait_for(build_briefing_for_tenant(t, status_cb=_update_status), timeout=240.0)
                txt = b.get("text", "⚠️ Error")
                
                inline_kb = []
                for row in b.get("dynamic_buttons", []): inline_kb.append(row)
                for opt in b.get("options", []):
                    if opt and "Option 1" not in opt and "Option 2" not in opt:
                        inline_kb.append([{"text": str(opt)[:40], "callback_data": f"act:{save_button_context(f'Deep dive: {opt}')}"}])
                markup = {"inline_keyboard": inline_kb} if inline_kb else None
                
                safe_txt = clean_html_for_telegram(txt)
                if len(safe_txt) > 3900: safe_txt = safe_txt[:3900] + "\n...[truncated]"

                try: await tg.edit_message_text(chat_id, res['message_id'], safe_txt, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
                except Exception: 
                    await tg.edit_message_text(chat_id, res['message_id'], _safe_err(safe_txt).strip(), reply_markup=markup, disable_web_page_preview=True)
            except Exception as e:
                err_str = traceback.format_exc()
                await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Briefing Failed:</b>\n<pre>{_safe_err(err_str)[:1500]}</pre>", parse_mode="HTML")
            return
            
    except Exception as e:
        print(f"COMMAND CRASH: {traceback.format_exc()}", flush=True)

async def safe_task(tag, coro):
    try: await coro
    except Exception as e: print(f"Task Crash [{tag}]: {traceback.format_exc()}", flush=True)

async def poll_loop():
    print("🤖 Telegram Bot Poller: ACTIVE (Enterprise Postgres V85)", flush=True)
    if not settings.telegram_bot_token: return
    
    asyncio.create_task(heartbeat_pinger())
    
    offset = 0
    try:
        with open("/attachments/tg_offset.json", "r") as f: offset = json.load(f).get("offset", 0)
    except: pass

    sem = asyncio.Semaphore(15)

    while True:
        try:
            updates = await tg.get_updates(offset, timeout_s=30)
            
            global LAST_HEARTBEAT
            LAST_HEARTBEAT = time.time()
            
            for u in updates:
                offset = u['update_id'] + 1
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
                        try: await asyncio.wait_for(_route_update(u_data), timeout=240.0)
                        except asyncio.TimeoutError: print("🚨 SENTINEL: Task timed out!", flush=True)
                
                asyncio.create_task(safe_task("Route Update", _run_with_guard(u)))
                
        except Exception as e: 
            print(f"POLL LOOP CRASH: {traceback.format_exc()}", flush=True)
            await asyncio.sleep(5)
