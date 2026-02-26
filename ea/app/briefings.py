from __future__ import annotations
import re, json, httpx, asyncio, traceback, time, html
from datetime import datetime, timezone, timedelta
from app.gog import gog_cli
from app.settings import settings
from app.open_loops import OpenLoops

def _sanitize_telegram_html(text: str) -> str: return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _safe_extract_array(text: str) -> list:
    try:
        clean = re.sub(r'\x1b\[[0-9;]*m', '', text).strip()
        start = -1
        for i, c in enumerate(clean):
            if c in '[{':
                start = i
                break
        if start >= 0:
            obj = json.loads(clean[start:])
            if isinstance(obj, list): return obj
            if isinstance(obj, dict):
                for k in ['items', 'messages', 'events', 'result', 'data']:
                    if k in obj and isinstance(obj[k], list): return obj[k]
    except: pass
    try:
        m = re.search(r"\[[\s\S]*\]", text)
        if m: return json.loads(m.group(0))
    except: pass
    return []

def _safe_extract_obj(text: str) -> dict:
    try:
        m = re.search(r"\{[\s\S]*\}", text)
        return json.loads(m.group(0)) if m else {}
    except: return {}

def get_val(obj, key, default=""):
    if isinstance(obj, dict): return obj.get(key, default)
    return getattr(obj, key, default)

async def safe_gog(container, cmd, account, timeout=20.0):
    try: return await asyncio.wait_for(gog_cli(container, cmd, account), timeout=timeout)
    except asyncio.TimeoutError: 
        await asyncio.create_subprocess_exec("docker", "exec", "-u", "root", container, "sh", "-c", "pkill -f gog 2>/dev/null || true")
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
            try: await status_cb("\n".join(ui_history) + "\n<i>⚙️ Synthesizing...</i>")
            except: pass

    await _log("Discovering Authorized Google Accounts...")
    try:
        raw_auths = await safe_gog(t_openclaw, ["auth", "list"], "", timeout=10.0)
        accounts = list(set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', raw_auths)))
        if not accounts: accounts = [t_account] if t_account else [""]
        diag_logs.append(f"🔑 Accounts: {', '.join([a.split('@')[0] for a in accounts if a])}")
    except Exception as e:
        accounts = [t_account] if t_account else [""]
        diag_logs.append(f"⚠️ Auth List Err: {str(e)[:50]}")

    await _log("Fetching & Python Filtering Emails...")
    clean_mails = []
    
    junk_kws = [
        'eff', 'andrew lock', 'stack overflow', 'dodo', 'appsumo', 'dyson', 'facebook', 'linkedin', 
        'bestsecret', 'mediamarkt', 'voyage', 'babysits', 'stacksocial', 'digital trends', 'the futurist', 
        'newsletter', 'spiceworks', 'ikea', 'paypal', 'gog.com', 'steam', 'humble bundle', 'indie gala', 
        'promotions', 'penny', 'chummer', 'samsung', 'mtg', 'omi ai', 'omi', 'akupara', 'cinecenter', 
        'beta', 'early access', 'n8n', 'versandinformation', 'danke für', 'we got your full', 
        'out for delivery', 'ihre bestellung bei', 'paket kommt', 'order confirmed', 'wird zugestellt',
        'hardloop', 'bergzeit', 'betzold', 'immmo', 'zalando', 'klarna', 'amazon', 'lieferando'
    ]
    keep_kws = ['nicht zugestellt', 'wartet auf abholung', 'fehlgeschlagen', 'abholbereit', 'action required']
    
    for acc in accounts:
        try:
            raw_mails = await safe_gog(t_openclaw, ["gmail", "messages", "search", "newer_than:1d", "--limit", "40", "--json"], acc, timeout=20.0)
            mails = _safe_extract_array(raw_mails)
            for m in mails:
                raw_val = json.dumps(m, ensure_ascii=False).lower()
                if any(kp in raw_val for kp in keep_kws):
                    m['_account'] = acc
                    clean_mails.append(m)
                    continue
                if any(j in raw_val for j in junk_kws): continue
                m['_account'] = acc
                clean_mails.append(m)
        except Exception as e: diag_logs.append(f"⚠️ Mails ({acc.split('@')[0] if acc else 'def'}) Err: {str(e)[:30]}")

    await _log("Fetching Calendar Events (including earlier today)...")
    clean_cal = []
    now = datetime.now(timezone.utc)
    
    # 🚨 THE TIME-TRAVEL FIX: Rewind 16 hours to ensure 08:00 AM events are captured!
    today_start = (now - timedelta(hours=16)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    target_cals = []
    for acc in accounts:
        target_cals.append((acc, "primary", "primary"))
        target_cals.append((acc, "Executive Assistant", "EA Shared"))
            
    for acc, cid, cname in target_cals:
        acc_lbl = acc.split('@')[0] if acc else 'def'
        try:
            # 🚨 CASCADE FLAGS: Different versions of Google APIs use different flags. We try them all!
            flags_to_try = [
                ["--timeMin", today_start],
                ["--time-min", today_start],
                ["--start", today_start],
                [] # Ultimate fallback to NOW
            ]
            
            events = []
            for flags in flags_to_try:
                cmd = ["calendar", "events", "list", cid, "--limit", "50", "--json"] + flags
                raw_cal = await safe_gog(t_openclaw, cmd, acc, timeout=12.0)
                events = _safe_extract_array(raw_cal)
                if events: break
                
            if not events: 
                diag_logs.append(f"ℹ️ Cal '{cname}' ({acc_lbl}): 0 events.")
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
                        if end_ts <= now - timedelta(hours=24): continue
                        clean_cal.append(ev)
                        added += 1
                    except:
                        clean_cal.append(ev)
                        added += 1
                else: 
                    clean_cal.append(ev)
                    added += 1
                    
            diag_logs.append(f"✅ Cal '{cname}' ({acc_lbl}): kept {added} events.")
        except Exception as e: 
            err_str = str(e).lower()
            if "not found" not in err_str and "404" not in err_str:
                diag_logs.append(f"⚠️ Cal '{cname}' ({acc_lbl}) Err: {str(e)[:30]}")

    await _log("Synthesizing Executive Action Report...")
    prompt = f"""You are an elite, ruthless Executive Assistant. I demand extreme noise reduction. NO BULLSHIT.
CRITICAL CULLING RULES:
1. THE PURGE: You MUST completely delete ALL package delivery updates, shipping notices, order confirmations, and standard payment receipts from the JSON. Do NOT include them with a note saying "ignore this". ERASE THEM ENTIRELY.
2. EXCEPTION: You MAY include a package/delivery alert ONLY IF it is a FAILURE ("konnte nicht zugestellt werden") or requires manual pickup ("wartet auf Abholung").
3. CHURCHILL TONE: For the critical emails that remain, state brutally and concisely WHY it requires action in 1 sentence.
4. CALENDARS: Format ALL events provided in the JSON timeline into a clean schedule. Group them cleanly by Day/Date. Note that these are sourced from multiple different calendars.

DATA:
Mails: {json.dumps(clean_mails, ensure_ascii=False)}
Calendars: {json.dumps(clean_cal, ensure_ascii=False)}

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
        html_out = "🎩 <b>Executive Action Briefing</b>\n\n" + loops_txt
        options = []
        
        if obj.get("emails") and len(obj["emails"]) > 0:
            html_out += "<b>Requires Attention:</b>\n"
            for e in obj["emails"]:
                s_name = _sanitize_telegram_html(e.get('sender', 'Unknown'))
                subj = _sanitize_telegram_html(e.get('subject', ''))
                reason = _sanitize_telegram_html(e.get('churchill_action', ''))
                html_out += f"• <b>{s_name}</b>: <i>{subj}</i>\n  └ <i>{reason}</i>\n\n"
                if e.get('action_button'): options.append(e.get('action_button'))
        else:
            html_out += "<i>No critical items require your immediate attention.</i>\n\n"
            
        html_out += f"<b>Calendars:</b>\n{_sanitize_telegram_html(obj.get('calendar_summary', 'No upcoming events.'))}"
        
        if diag_logs: html_out += "\n\n<i>⚙️ Diagnostics:</i>\n<pre>" + html.escape("\n".join(diag_logs), quote=False) + "</pre>"

        clean_opts = [str(o) for o in options if "Option" not in str(o)][:3]
        return {"text": html_out, "options": clean_opts, "dynamic_buttons": loop_btns}
    except Exception as e: return {"text": f"⚠️ <b>Fatal Briefing Error:</b>\n<pre>{html.escape(str(e), quote=False)}</pre>", "options": ["🔁 Retry"]}
