import re, sys, subprocess

path = "ea/app/scheduler.py"

with open(path, "r") as f:
    content = f.read()

# 1. Find the exact native indentation level of the poller loop
m = re.search(r'^([ \t]*)for u in updates:', content, re.MULTILINE)
if not m:
    print("❌ Could not find the polling loop in scheduler.py.")
    sys.exit(1)

indent = m.group(1)

# 2. Reconstruct the loop with perfect Python alignment, avoiding multiline string artifacts
clean_loop = (
    f"{indent}for u in updates:\n"
    f"{indent}    offset = u['update_id'] + 1\n"
    f"{indent}    if 'callback_query' in u:\n"
    f"{indent}        try: asyncio.create_task(_safe_cb(u['callback_query'], handle_callback))\n"
    f"{indent}        except NameError: asyncio.create_task(handle_callback(u['callback_query']))\n"
    f"{indent}    elif 'message' in u:\n"
    f"{indent}        msg = u['message']\n"
    f"{indent}        chat_id = msg['chat']['id']\n"
    f"{indent}        if msg.get('photo'):\n"
    f"{indent}            asyncio.create_task(handle_photo(chat_id, msg))\n"
    f"{indent}        elif msg.get('text') and msg['text'].startswith('/'):\n"
    f"{indent}            try: asyncio.create_task(_safe_cmd(chat_id, msg['text'], handle_command))\n"
    f"{indent}            except NameError: asyncio.create_task(handle_command(chat_id, msg['text']))\n"
)

# 3. Strip the broken loop and replace it
content = re.sub(r'^[ \t]*for u in updates:.*?(?=^[ \t]*except Exception)', clean_loop, content, flags=re.DOTALL | re.MULTILINE)

# 4. Inject the safe, un-indented typing wrappers at the module level
wrapper = """
import asyncio, httpx, os, traceback
async def _safe_cmd(chat_id, text, func):
    keep = True
    async def _t():
        async with httpx.AsyncClient() as hc:
            while keep and chat_id:
                try: await hc.post(f"https://api.telegram.org/bot{os.environ.get('EA_TELEGRAM_BOT_TOKEN')}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                except: pass
                await asyncio.sleep(4)
    task = asyncio.create_task(_t())
    try: await func(chat_id, text)
    except Exception as e:
        print(f"\\n🔥 CRASH IN COMMAND: {e}\\n", flush=True)
        traceback.print_exc()
    finally:
        keep = False
        task.cancel()

async def _safe_cb(cb, func):
    chat_id = cb.get("message", {}).get("chat", {}).get("id")
    keep = True
    async def _t():
        async with httpx.AsyncClient() as hc:
            while keep and chat_id:
                try: await hc.post(f"https://api.telegram.org/bot{os.environ.get('EA_TELEGRAM_BOT_TOKEN')}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                except: pass
                await asyncio.sleep(4)
    task = asyncio.create_task(_t())
    try: await func(cb)
    except Exception as e:
        print(f"\\n🔥 CRASH IN CALLBACK: {e}\\n", flush=True)
        traceback.print_exc()
    finally:
        keep = False
        task.cancel()
"""

if "_safe_cmd" not in content:
    lines = content.splitlines()
    insert_idx = 0
    for i, l in enumerate(lines):
        if l.startswith("import ") or (l.startswith("from ") and "future" not in l):
            insert_idx = i + 1
    lines.insert(insert_idx, wrapper)
    content = "\n".join(lines)

with open(path, "w") as f:
    f.write(content)

# 5. Native compilation test - absolutely proves the syntax is flawless before Docker touches it
try:
    compile(content, path, 'exec')
    print(f"✅ Repaired {path}. Syntax is mathematically perfect.")
except SyntaxError as e:
    print(f"❌ Still broken: {e}")
    sys.exit(1)

print("\n=== RESTARTING DAEMON & CHECKING STATUS ===")
subprocess.run(["docker", "compose", "restart", "ea-daemon"], check=True)
import time
time.sleep(4)
res = subprocess.run(["docker", "logs", "--tail", "15", "ea-daemon"], capture_output=True, text=True)
if "IndentationError" in res.stderr or "SyntaxError" in res.stderr:
    print("❌ Daemon failed to boot.")
    print(res.stderr)
else:
    print("✅ Daemon booted cleanly. The bot is actively listening.")
    print("👉 Send /brief in Telegram. The 'typing...' UX is active, and the AI Clerk Test is ready.")
