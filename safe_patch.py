import os, re, sys

path = "ea/app/scheduler.py"
with open(path, "r") as f: content = f.read()

# 1. Verify the file is actually restored
if content.strip().startswith("try:"):
    print("❌ ERROR: The file is still truncated!")
    print("👉 Please restore the file in VS Code (Right-Click -> Timeline) before running this.")
    sys.exit(1)

# 2. Add the UX wrapper functions cleanly at the global module level
wrapper = """
import httpx, traceback, asyncio, os

async def _safe_cmd(chat_id, txt):
    keep = True
    async def _typer():
        async with httpx.AsyncClient() as hc:
            while keep and chat_id:
                try: await hc.post(f"https://api.telegram.org/bot{os.environ.get('EA_TELEGRAM_BOT_TOKEN')}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                except: pass
                await asyncio.sleep(4)
    t = asyncio.create_task(_typer())
    try: await handle_command(chat_id, txt)
    except Exception as e:
        print(f"\\n🔥 CRASH IN COMMAND: {e}\\n", flush=True)
        traceback.print_exc()
    finally:
        keep = False
        t.cancel()

async def _safe_cb(cb):
    chat_id = cb.get("message", {}).get("chat", {}).get("id")
    keep = True
    async def _typer():
        async with httpx.AsyncClient() as hc:
            while keep and chat_id:
                try: await hc.post(f"https://api.telegram.org/bot{os.environ.get('EA_TELEGRAM_BOT_TOKEN')}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                except: pass
                await asyncio.sleep(4)
    t = asyncio.create_task(_typer())
    try: await handle_callback(cb)
    except Exception as e:
        print(f"\\n🔥 CRASH IN CALLBACK: {e}\\n", flush=True)
        traceback.print_exc()
    finally:
        keep = False
        t.cancel()
"""

if "_safe_cmd" not in content:
    lines = content.splitlines()
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_idx = i + 1
    lines.insert(insert_idx, wrapper.strip())
    content = "\n".join(lines)

# 3. Inline replace the exact calls to avoid touching ANY indentation
content = re.sub(
    r"asyncio\.create_task\(\s*handle_command\(\s*chat_id,\s*msg\['text'\]\s*\)\s*\)",
    r"asyncio.create_task(_safe_cmd(chat_id, msg['text']))",
    content
)

content = re.sub(
    r"await\s+handle_callback\(\s*u\['callback_query'\]\s*\)",
    r"await _safe_cb(u['callback_query'])",
    content
)
content = re.sub(
    r"asyncio\.create_task\(\s*handle_callback\(\s*u\['callback_query'\]\s*\)\s*\)",
    r"asyncio.create_task(_safe_cb(u['callback_query']))",
    content
)

with open(path, "w") as f: f.write(content)

# 4. Prove syntax is flawless
try:
    compile(content, path, 'exec')
    print(f"✅ Repaired {path}. Syntax is mathematically perfect.")
except SyntaxError as e:
    print(f"❌ Syntax Error: {e}")
    sys.exit(1)
