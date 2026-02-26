#!/usr/bin/env bash
set -e

echo "=== 1. FIXING SILENT CRASHES IN POLLER ==="
docker exec ea-daemon python3 -c '
import glob, re
for f in glob.glob("app/*.py"):
    with open(f, "r") as file: txt = file.read()
    orig = txt
    
    # Clean up the buggy wrapper if it exists
    if "def _type_while_running" in txt:
        txt = re.sub(r"import httpx, asyncio, os\nasync def _type_while_running.*?finally:\s*keep_typing = False;\s*t\.cancel\(\)\n?", "", txt, flags=re.DOTALL)
        txt = txt.replace("asyncio.create_task(_type_while_running(chat_id, handle_command(chat_id, msg[\"text\"])))", "asyncio.create_task(handle_command(chat_id, msg[\"text\"]))")
        txt = txt.replace("await _type_while_running(u[\"callback_query\"].get(\"message\", {}).get(\"chat\", {}).get(\"id\"), handle_callback(u[\"callback_query\"]))", "await handle_callback(u[\"callback_query\"])")

    wrapper = """
async def _safe_cmd_task(chat_id, txt):
    import httpx, asyncio, os, traceback
    keep_typing = True
    async def _typer():
        async with httpx.AsyncClient() as hc:
            while keep_typing and chat_id:
                try: await hc.post(f"https://api.telegram.org/bot{os.environ.get(\\"EA_TELEGRAM_BOT_TOKEN\\")}/sendChatAction", json={"chat_id": chat_id, "action": "typing"})
                except: pass
                await asyncio.sleep(4)
    t = asyncio.create_task(_typer())
    try:
        await handle_command(chat_id, txt)
    except Exception as e:
        print(f"\\n🔥 FATAL CRASH IN COMMAND TASK: {e}\\n", flush=True)
        traceback.print_exc()
    finally:
        keep_typing = False
        t.cancel()
"""
    if "async def _safe_cmd_task" not in txt and "asyncio.create_task(handle_command" in txt:
        txt = wrapper + "\\n" + txt
        txt = txt.replace("asyncio.create_task(handle_command(chat_id, msg[\"text\"]))", "asyncio.create_task(_safe_cmd_task(chat_id, msg[\"text\"]))")
        
    if txt != orig:
        with open(f, "w") as file: file.write(txt)
        print(f"✅ Secured {f} against silent task crashes.")
'

echo -e "\n=== 2. RESTARTING DAEMON ==="
docker compose restart ea-daemon > /dev/null
sleep 4

echo -e "\n=== 3. 🧪 INTERNAL SMOKE TEST: GENERATING BRIEFING ==="
echo "Executing the LLM and OpenClaw commands directly inside the container to verify the Clerk Test..."
docker exec ea-daemon python3 -c '
import asyncio, sys, traceback
sys.path.insert(0, "/app")

class DummyTenant:
    key = "tibor"
    label = "Tibor"
    openclaw_container = "openclaw-gateway-tibor"
    family_openclaw_container = "openclaw-gateway-family-girschele"
    tasks_enabled = True
    include_family = True

async def run():
    try:
        from app.briefings import build_briefing_for_tenant
        res = await build_briefing_for_tenant(DummyTenant())
        print("\n" + "="*50)
        print("✅ CLERK TEST BRIEFING OUTPUT (RAW):")
        print("="*50)
        print(res.get("text", "NO TEXT RETURNED"))
        print("="*50)
        print("🔘 BUTTONS:", res.get("options", []))
    except Exception as e:
        print("\n❌ CRASH DURING AI GENERATION:")
        traceback.print_exc()
        sys.exit(1)

asyncio.run(run())
'

echo -e "\n=== 4. LIVE TELEGRAM MONITORING ==="
echo "✅ If the briefing generated perfectly above, the AI Brain is 100% working."
echo "👉 Please type /brief in Telegram NOW. I am tailing the live logs to catch the exact API error:"
docker logs ea-daemon -f --tail 0
