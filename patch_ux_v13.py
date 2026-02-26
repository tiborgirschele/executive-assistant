import re, os

print("1️⃣ Building the Open Loops State Manager...")
open_loops_code = """import json, os, uuid

LOOPS_FILE = "/attachments/open_loops.json"

class OpenLoops:
    @classmethod
    def _load(cls):
        if not os.path.exists(LOOPS_FILE): return {}
        try:
            with open(LOOPS_FILE, "r") as f: return json.load(f)
        except: return {}

    @classmethod
    def _save(cls, data):
        os.makedirs(os.path.dirname(LOOPS_FILE), exist_ok=True)
        tmp = LOOPS_FILE + ".tmp"
        with open(tmp, "w") as f: json.dump(data, f)
        os.replace(tmp, LOOPS_FILE)

    @classmethod
    def _ensure_tenant(cls, d, tenant):
        if tenant not in d: d[tenant] = {"shopping": [], "payments": [], "calendars": []}
        for k in ["shopping", "payments", "calendars"]:
            if k not in d[tenant]: d[tenant][k] = []

    @classmethod
    def add_shopping(cls, tenant: str, item: str):
        d = cls._load()
        cls._ensure_tenant(d, tenant)
        if item not in d[tenant]["shopping"]: d[tenant]["shopping"].append(item)
        cls._save(d)

    @classmethod
    def clear_shopping(cls, tenant: str):
        d = cls._load()
        cls._ensure_tenant(d, tenant)
        d[tenant]["shopping"] = []
        cls._save(d)

    @classmethod
    def add_payment(cls, tenant: str, desc: str, amount: str, iban: str, status: str = "ready"):
        d = cls._load()
        cls._ensure_tenant(d, tenant)
        pid = str(uuid.uuid4())[:8]
        d[tenant]["payments"].append({"id": pid, "desc": desc, "amount": amount, "iban": iban, "status": status})
        cls._save(d)
        return pid

    @classmethod
    def remove_payment(cls, tenant: str, pid: str):
        d = cls._load()
        cls._ensure_tenant(d, tenant)
        d[tenant]["payments"] = [p for p in d[tenant]["payments"] if p["id"] != pid]
        cls._save(d)

    @classmethod
    def add_calendar(cls, tenant: str, preview: str, events: list):
        d = cls._load()
        cls._ensure_tenant(d, tenant)
        cid = str(uuid.uuid4())[:8]
        d[tenant]["calendars"].append({"id": cid, "preview": preview, "events": events})
        cls._save(d)
        return cid

    @classmethod
    def remove_calendar(cls, tenant: str, cid: str):
        d = cls._load()
        cls._ensure_tenant(d, tenant)
        d[tenant]["calendars"] = [c for c in d[tenant]["calendars"] if c["id"] != cid]
        cls._save(d)
            
    @classmethod
    def get_calendar(cls, tenant: str, cid: str):
        d = cls._load()
        for c in d.get(tenant, {}).get("calendars", []):
            if c["id"] == cid: return c
        return None

    @classmethod
    def get_dashboard(cls, tenant: str):
        d = cls._load().get(tenant, {})
        txt = ""
        btns = []
        
        if d.get("payments"):
            txt += "💳 <b>Pending Payments:</b>\\n"
            for p in d["payments"]: 
                if p.get("status") == "needs_doc":
                    txt += f"  └ ⚠️ {p['desc']} (Needs PDF)\\n"
                    btns.append([{"text": f"🛑 Drop Payment", "callback_data": f"drop_pay:{p['id']}"}])
                else:
                    txt += f"  └ {p['desc']} (€{p['amount']})\\n"
                    btns.append([{"text": f"✅ Paid: {p['desc'][:15]}", "callback_data": f"mark_paid:{p['id']}"}])
                    
        if d.get("calendars"):
            txt += "🗓️ <b>Pending Calendar Imports:</b>\\n"
            for c in d["calendars"]:
                txt += f"  └ Import Request ({len(c['events'])} events)\\n"
                btns.append([{"text": "✅ Execute Cal Import", "callback_data": f"exec_cal:{c['id']}"}])
                btns.append([{"text": "🛑 Discard Cal Import", "callback_data": f"drop_cal:{c['id']}"}])
                
        if d.get("shopping"):
            txt += "🛒 <b>Shopping List:</b>\\n"
            for s in d["shopping"]: txt += f"  └ {s}\\n"
            btns.append([{"text": "🧹 Clear Shopping List", "callback_data": "clear_shopping"}])
        
        if txt: txt = "🚨 <b>OPEN LOOPS (ACTION REQUIRED)</b>\\n" + txt + "\\n━━━━━━━━━━━━━━━━━━\\n\\n"
        return txt, btns
"""
with open("ea/app/open_loops.py", "w", encoding="utf-8") as f: f.write(open_loops_code)


print("2️⃣ Upgrading briefings.py (7-Day Horizon, Regex Fix & Control Panel)...")
with open("ea/app/briefings.py", "r", encoding="utf-8") as f: code = f.read()

if "from app.open_loops import OpenLoops" not in code:
    code = "from app.open_loops import OpenLoops\n" + code

code = code.replace('if "executive assistant" in summary or "ea " in summary:', 'if "executive" in summary or "ea" in summary or "assistant" in summary:')

# Force 7 days lookup
code = re.sub(
    r'raw_cal = await gog_cli\(t_openclaw, \["calendar", "events", "list", cid, "--json"\], t_account\)',
    r'raw_cal = await gog_cli(t_openclaw, ["calendar", "events", "list", cid, "--days", "7", "--json"], t_account)',
    code
)

# Inject Dashboard
code = code.replace('html = "🎩 <b>Executive Action Briefing</b>\\n\\n"', 'loops_txt, loop_btns = OpenLoops.get_dashboard(t_key)\n        html = "🎩 <b>Executive Action Briefing</b>\\n\\n" + loops_txt')
code = code.replace('"options": clean_opts}', '"options": clean_opts, "dynamic_buttons": loop_btns}')

# Force LLM to include ALL events
code = re.sub(
    r'3\. CALENDAR: Format the upcoming schedule cleanly\.',
    r'3. CALENDAR: You MUST list ALL events provided in the JSON timeline for the next 7 days. Do not omit ANY future events.',
    code
)

with open("ea/app/briefings.py", "w", encoding="utf-8") as f: f.write(code)


print("3️⃣ Patching poll_listener.py (Curl Auth Sniper, Scopes & Intent Catchers)...")
with open("ea/app/poll_listener.py", "r", encoding="utf-8") as f: poll_code = f.read()

if "from app.open_loops import OpenLoops" not in poll_code:
    poll_code = poll_code.replace("from app.sepa_xml import generate_pain001_xml", "from app.sepa_xml import generate_pain001_xml\nfrom app.open_loops import OpenLoops")

# 🚨 THE REDIRECT SNIPER: Extracts the final Google Link effortlessly via cURL
new_auth_flow = """async def trigger_auth_flow(chat_id: int, email: str, t: dict, scopes: str = ""):
    res = await tg.send_message(chat_id, f"🔄 Starting auth for <b>{email}</b>...\\n<i>⚙️ Requesting OAuth URL...</i>", parse_mode="HTML")
    try:
        t_openclaw = get_val(t, 'openclaw_container', 'openclaw-gateway-tibor')
        await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", "-e", f"GOG_ACCOUNT={email}", t_openclaw, "gog", "auth", "logout")
        await asyncio.sleep(0.5)

        cmd = ["docker", "exec", "-i", "-e", f"GOG_ACCOUNT={email}", t_openclaw, "gog", "auth", "login"]
        if scopes: cmd.extend(["--scopes", scopes])
        
        proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        
        local_url = google_url = None
        for _ in range(40):
            try:
                line_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=1.0)
                if not line_bytes: break
                line = re.sub(r'\\x1b\\[[0-9;]*m', '', line_bytes.decode('utf-8', errors='ignore').strip())
                
                m_loc = re.search(r'(http://(?:127\\.0\\.0\\.1|localhost):\\d+)', line)
                if m_loc:
                    local_url = m_loc.group(1).replace("localhost", "127.0.0.1")
                    await asyncio.sleep(1.5)
                    # 🚨 THE REDIRECT STEALER FIX!
                    try:
                        c_proc = await asyncio.create_subprocess_exec("docker", "exec", t_openclaw, "sh", "-c", f"curl -s -i {local_url}", stdout=asyncio.subprocess.PIPE)
                        c_out, _ = await asyncio.wait_for(c_proc.communicate(), timeout=4.0)
                        m_redir = re.search(r'(?i)location:\\s*([^\\r\\n]+)', c_out.decode('utf-8'))
                        if m_redir: google_url = m_redir.group(1).strip()
                    except: pass
                    break
            except asyncio.TimeoutError:
                try: proc.stdin.write(b"\\n"); await proc.stdin.drain()
                except: pass
                    
        if google_url:
            AUTH_SESSIONS[chat_id] = {"state": "waiting_for_token", "proc": proc, "email": email}
            auth_msg = (
                f"🔗 <b>Authorization Required</b>\\n\\n"
                f"1. <b><a href='{google_url}'>Click here to open Google in your browser</a></b>\\n"
                f"2. Log in and approve the permissions.\\n"
                f"3. Google will eventually redirect you to a broken localhost page (e.g. 'This site can\\'t be reached').\\n"
                f"4. <b>COPY the full URL from your browser's address bar and paste it back into this chat.</b>"
            )
            await tg.edit_message_text(chat_id, res['message_id'], auth_msg, parse_mode="HTML", disable_web_page_preview=True)
        else:
            await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ <b>Failed to extract auth URL.</b> (Could not read Location header)", parse_mode="HTML")
    except Exception as e: await tg.edit_message_text(chat_id, res['message_id'], f"⚠️ Error: {_safe_err(e)}", parse_mode="HTML")"""

poll_code = re.sub(r'async def trigger_auth_flow[\s\S]*?(?=async def handle_callback)', new_auth_flow + '\n\n', poll_code)

# Add callback handlers for Open Loops
callbacks = """    # 🚨 OPEN LOOPS CATCHERS
    if cb['data'] == "clear_shopping":
        OpenLoops.clear_shopping(tenant_name)
        await tg.answer_callback_query(cb['id'], text="Shopping List Cleared!")
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass
        return await tg.send_message(chat_id, "✅ <b>Shopping List marked as Done.</b>", parse_mode="HTML")

    if cb['data'].startswith("mark_paid:"):
        pid = cb['data'].split(":")[1]
        OpenLoops.remove_payment(tenant_name, pid)
        await tg.answer_callback_query(cb['id'], text="Marked Paid!")
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass
        return await tg.send_message(chat_id, "✅ <b>Rechnung als bezahlt markiert und entfernt.</b>", parse_mode="HTML")

    if cb['data'].startswith("drop_pay:"):
        pid = cb['data'].split(":")[1]
        OpenLoops.remove_payment(tenant_name, pid)
        await tg.answer_callback_query(cb['id'], text="Payment Dropped!")
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
            await native_calendar_import(chat_id, t, cal_data["events"])
        return

    if cb['data'].startswith("drop_cal:"):
        cid = cb['data'].split(":")[1]
        OpenLoops.remove_calendar(tenant_name, cid)
        await tg.answer_callback_query(cb['id'], text="Import Dropped!")
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass
        return await tg.send_message(chat_id, "🛑 <b>Calendar Import Discarded.</b>", parse_mode="HTML")

    if cb['data'].startswith("cmd_auth_all:"):
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass
        await trigger_auth_flow(chat_id, cb['data'].split(":", 1)[1], t, scopes="")
        return

    if cb['data'].startswith("cmd_auth_cal:"):
        try: await tg.edit_message_reply_markup(chat_id, cb['message']['message_id'], reply_markup={"inline_keyboard": []})
        except: pass
        await trigger_auth_flow(chat_id, cb['data'].split(":", 1)[1], t, scopes="https://www.googleapis.com/auth/calendar")
        return"""

if "clear_shopping" not in poll_code:
    poll_code = poll_code.replace("if not t: return", "if not t: return\n" + callbacks)

# Intent hook for missing PDF ("kannst du das zahlen")
intent_hook = """        low_stock_words = ["katzenfutter", "cat food", "futter", "brot", "milch", "kaffee", "coffee", "einkaufsliste"]
        if any(w in text_lower for w in low_stock_words) and any(w in text_lower for w in ["kaufen", "leer", "aus", "fast kein", "brauchen", "setz"]):
            OpenLoops.add_shopping(tenant_name, text)
            return await tg.send_message(chat_id, f"🛒 <b>Added to Shopping List Open Loop:</b>\\n{text}", parse_mode="HTML")

        if any(kw in text_lower for kw in ["zahl", "rechnung", "pay", "sepa", "iban"]) and "kannst du" in text_lower:
            OpenLoops.add_payment(tenant_name, "Zahlung gewünscht (Missing PDF)", "?", "?", status="needs_doc")
            return await tg.send_message(chat_id, "📌 <b>Zahlung notiert (Open Loop).</b>\\n\\nBitte sende die Rechnung als PDF hier in den Chat, damit ich IBAN/Betrag extrahieren kann.", parse_mode="HTML")
"""
if "Zahlung gewünscht" not in poll_code:
    poll_code = poll_code.replace("is_pdf = bool(doc", intent_hook + "\n        is_pdf = bool(doc")

# Hook PDF uploads into Open Loops
if "OpenLoops.add_payment" not in poll_code:
    poll_code = poll_code.replace('kb = [[{"text": "✅ Als bezahlt markieren", "callback_data": "mark_paid"}]]', 'pid = OpenLoops.add_payment(tenant_name, sepa_data.get("creditor","Unknown"), amt, sepa_data.get("iban"))\n                            kb = [[{"text": "✅ Als bezahlt markieren", "callback_data": f"mark_paid:{pid}"}]]')

# Hook Calendar photo into Open Loops
if "OpenLoops.add_calendar" not in poll_code:
    poll_code = poll_code.replace('kb = [[{"text": f"✅ Safe Import to EA", "callback_data": f"native_cal:{save_button_context(json.dumps(events))}"}]]', 'cid = OpenLoops.add_calendar(tenant_name, preview, events)\n                kb = [[{"text": f"✅ Safe Import to EA", "callback_data": f"exec_cal:{cid}"}], [{"text": f"🛑 Discard", "callback_data": f"drop_cal:{cid}"}]]')

# Fix command handler scope options & buttons injection
if 'for row in dynamic_btns: inline_kb.append(row)' not in poll_code:
    poll_code = poll_code.replace('kb = [[{"text": f"🔑 {get_val(t, \'google_account\', \'Tibor\')}", "callback_data": f"cmd_auth:{get_val(t, \'google_account\')}"}]]', 't_acc = get_val(t, \'google_account\', \'Tibor\')\n            kb = [[{"text": f"🔑 All Scopes", "callback_data": f"cmd_auth_all:{t_acc}"}], [{"text": f"📅 Calendar Only", "callback_data": f"cmd_auth_cal:{t_acc}"}]]')
    poll_code = poll_code.replace('inline_kb = []\n            \n            # 🚨 INJECT DYNAMIC OPEN LOOPS BUTTONS\n            dynamic_btns = b.get("dynamic_buttons", [])\n            for row in dynamic_btns: inline_kb.append(row)', 'inline_kb = []\n            for row in b.get("dynamic_buttons", []): inline_kb.append(row)')
    poll_code = poll_code.replace('inline_kb = []\n            \n            for opt in b.get("options", []):', 'inline_kb = []\n            for row in b.get("dynamic_buttons", []): inline_kb.append(row)\n            for opt in b.get("options", []):')

with open("ea/app/poll_listener.py", "w", encoding="utf-8") as f: f.write(poll_code)

print("✅ Patched Auth Stealer, 7-Day Horizon, and Open Loops Routing.")
