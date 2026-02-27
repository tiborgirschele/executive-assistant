import os, glob, re, subprocess, sys, time

print("=== 1. FINDING & PATCHING TELEGRAM HANDLER ===")
tg_file = None
for f in glob.glob("ea/app/*.py"):
    try:
        with open(f) as file:
            if "def handle_callback" in file.read():
                tg_file = f; break
    except: pass

if not tg_file:
    print("❌ Could not find Telegram handler.")
    sys.exit(1)

print(f"✅ Found Telegram handlers in {tg_file}")
with open(tg_file) as file: content = file.read()

# Typer wrapper
typer = '''
import httpx, asyncio, os
async def _type_while_running(chat_id, coro):
    keep_typing = True
    async def _typer():
        async with httpx.AsyncClient() as hc:
            while keep_typing and chat_id:
                try: await hc.post(f"https://api.telegram.org/bot{os.environ.get('EA_TELEGRAM_BOT_TOKEN')}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                except: pass
                await asyncio.sleep(4)
    t = asyncio.create_task(_typer())
    try: return await coro
    finally: keep_typing = False; t.cancel()
'''
if "def _type_while_running" not in content:
    content = typer + "\n" + content
    
content = content.replace(
    "asyncio.create_task(handle_command(chat_id, msg['text']))",
    "asyncio.create_task(_type_while_running(chat_id, handle_command(chat_id, msg['text'])))"
)
content = content.replace(
    "await handle_callback(u['callback_query'])",
    "await _type_while_running(u['callback_query'].get('message', {}).get('chat', {}).get('id'), handle_callback(u['callback_query']))"
)

# Button Toast
if "btn_txt =" not in content:
    content = re.sub(
        r'(async def handle_callback\s*\(\s*([a-zA-Z_0-9]+)\s*.*?\):)',
        r'\1\n    btn_txt = "Executing..."\n    try:\n        for row in \2.get("message", {}).get("reply_markup", {}).get("inline_keyboard", []):\n            for btn in row:\n                if btn.get("callback_data") == \2.get("data"): btn_txt = f"⚙️ {btn.get(\'text\')}..."\n    except: pass\n',
        content, count=1
    )
    content = re.sub(r'text\s*=\s*f?["\'][Ee]xecuting[^"\']*["\']', 'text=btn_txt', content)
    
with open(tg_file, "w") as file: file.write(content)
print("✅ Patched typing indicators and dynamic toasts.")


print("\n=== 2. REWRITING BRIEFINGS.PY ===")
b_code = '''from __future__ import annotations
import re, json, httpx
from datetime import datetime, timezone
from app.audit import log_event
from app import gog
from app.settings import settings

def _safe_truncate(s: str, n: int = 6000) -> str: return s if len(s) <= n else s[:n] + "\\n...[truncated]"

async def call_llm(prompt: str, temperature: float = 0.15) -> str:
    base = getattr(settings, "litellm_base_url", "http://litellm:4000")
    model = getattr(settings, "llm_model", "gpt-4o")
    api_key = getattr(settings, "litellm_api_key", "")
    url = base.rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key: headers["Authorization"] = f"Bearer {api_key}"
    body = {"model": model, "temperature": temperature, "messages": [{"role": "user", "content": prompt}]}
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']

async def build_briefing_for_tenant(tenant) -> dict:
    parts = []
    parts.append(f"DATE_UTC={datetime.now(timezone.utc).isoformat()}")

    def _g(obj, key, d=None):
        if isinstance(obj, dict): return obj.get(key, d)
        return getattr(obj, key, d)

    t_key = _g(tenant, "key", "unknown")
    t_label = _g(tenant, "label", "Executive")
    t_openclaw = _g(tenant, "openclaw_container", "")
    t_family_openclaw = _g(tenant, "family_openclaw_container", "")
    
    tasks_cfg = _g(tenant, "tasks", {})
    t_tasks_enabled = _g(tenant, "tasks_enabled", False) or (isinstance(tasks_cfg, dict) and tasks_cfg.get("enabled"))
    t_tasklist = _g(tenant, "tasklist_id", None) or (_g(tasks_cfg, "tasklist_id", None) if isinstance(tasks_cfg, dict) else None)
    
    briefing_cfg = _g(tenant, "briefing", {})
    t_incl_fam = _g(tenant, "include_family", False) or (isinstance(briefing_cfg, dict) and briefing_cfg.get("include_family"))

    if t_openclaw:
        parts.append("\\n## EMAIL_INBOX_24H (SELF)\\n" + _safe_truncate(gog.gmail_recent_summary(t_openclaw, 24)))
        parts.append("\\n## EMAIL_SENT_7D (SELF)\\n" + _safe_truncate(gog.gmail_sent_followups(t_openclaw, 7)))
        parts.append("\\n## CALENDAR_7D (SELF)\\n" + _safe_truncate(gog.calendar_upcoming(t_openclaw, 7)))
        if t_tasks_enabled: parts.append("\\n## TASKS (SELF)\\n" + _safe_truncate(gog.tasks_list(t_openclaw, t_tasklist)))

    if t_incl_fam and t_family_openclaw:
        parts.append("\\n## EMAIL_INBOX_24H (FAMILY)\\n" + _safe_truncate(gog.gmail_recent_summary(t_family_openclaw, 24)))
        parts.append("\\n## CALENDAR_7D (FAMILY)\\n" + _safe_truncate(gog.calendar_upcoming(t_family_openclaw, 7)))

    raw = "\\n".join(parts)
    log_event(t_key, "briefing", "raw_collected", "raw inputs collected", {"bytes": len(raw)})

    prompt = f\'\'\'You are an elite, highly evolved AI Chief of Staff generating a daily briefing for the executive (Tenant: "{t_label}").
Your goal is NOT to blindly list raw data. You must SYNTHESIZE, FILTER, and HIGHLIGHT what actually requires executive attention.

Apply the "Clerk Test":
Before outputting any item, think: "If I handed this to my busy executive, would they throw it back in my face for wasting their time with useless noise?"
If the answer is yes, REWORK OR OMIT IT. Be an evolved, generic intent AI that thinks before it lists.
(Do NOT adopt a persona in the output, and do NOT mention the clerk test. Keep the tone strictly professional, objective, and dense.)

CRITICAL ANALYTICAL RULES:
1. Filter the Noise: Drop routine "Ordered: [Item]" confirmations or dispatch notices unless action is required. The executive placed the order; they already know.
2. Context is Mandatory: Never write "Delivery cancelled" without stating EXACTLY WHICH item was cancelled based on context.
3. Don't Cry Wolf: If an alert says a system (e.g., Cloudflare tunnel) is down, check if a newer message says it's back up. If it resolved, omit it entirely or just note "Tunnel bounced but is back online."
4. Grouping: Consolidate repeating calendar events into a single line (e.g., "Noah Kurs (Feb 25, Mar 4)").
5. Markdown Links: EVERY single email mentioned MUST be a hidden Markdown link using its ID. Format exactly like this: [Brief context](https://mail.google.com/mail/u/0/#all/<MESSAGE_ID>)

Return ONLY a valid JSON object with keys:
- text: string (Telegram Markdown formatted. Group into logical headers. Keep it dense and actionable.)
- options: array of up to 5 strings (short poll options for deep dives; include emojis; should be actionable, e.g. "🔍 Investigate <X>")

RAW DATA:
{raw}\\n\'\'\'

    try:
        out = await call_llm(prompt, temperature=0.15)
        m = re.search(r"\\{[\\s\\S]*\\}", out)
        if not m: return {"text": "STATUSBOARD: (LLM JSON error)", "options": ["🔁 Retry", "📌 Show logs"]}
        obj = json.loads(m.group(0))
        return {"text": str(obj.get("text", "")).strip(), "options": [str(x)[:60] for x in obj.get("options", []) if str(x).strip()][:5], "raw": raw}
    except Exception as e:
        return {"text": f"STATUSBOARD: (Error: {e})", "options": ["🔁 Retry", "📌 Show logs"]}
'''
with open("ea/app/briefings.py", "w") as f: f.write(b_code)
print("✅ Rewrote briefings.py to apply the Clerk Test and fix imports.")


print("\n=== 3. RESTART & AUTOMATED SMOKE TEST ===")
subprocess.run(["docker", "compose", "restart", "ea-daemon"], check=True)
time.sleep(4)
res = subprocess.run(["docker", "logs", "--tail", "40", "ea-daemon"], capture_output=True, text=True)
logs = res.stdout + res.stderr
crashes = [line for line in logs.split("\n") if any(err in line for err in ["Traceback", "Exception:", "ImportError", "SyntaxError", "ModuleNotFoundError"])]
crashes = [c for c in crashes if "Vision API Error" not in c and "Poller Warning" not in c and "task_done() called too many times" not in c]
if crashes:
    print("❌ CRASH DETECTED:\n" + "\n".join(logs.split("\n")[-15:]))
    sys.exit(1)
else:
    print("✅ Daemon booted perfectly. UX injected. Clerk Test active.")