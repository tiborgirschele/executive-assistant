

import os
import asyncio
import re
import time

async def gog_cli(container: str, command: list, account: str = "") -> str:
    cmd = ["docker", "exec", "-e", f"GEMINI_API_KEY={os.environ.get('GEMINI_API_KEY', '')}", "-e", f"LITELLM_API_KEY={os.environ.get('GEMINI_API_KEY', '')}", "-e", "LLM_MODEL=gemini/gemini-2.5-flash", "-u", "root", container, "gog"] + command
    try:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30.0)
        return stdout.decode('utf-8', errors='replace')
    except Exception as e: return "[]"

async def gog_scout(container: str, prompt: str, account: str, status_cb=None, task_name="Task") -> str:
    cmd = ["docker", "exec", "-e", f"GEMINI_API_KEY={os.environ.get('GEMINI_API_KEY', '')}", "-e", f"LITELLM_API_KEY={os.environ.get('GEMINI_API_KEY', '')}", "-e", "LLM_MODEL=gemini/gemini-2.5-flash",  "-e", "GOG_KEYRING_PASSWORD=rangersofB5", "-e", "WEB_PROVIDER=searxng", "-e", "SEARXNG_URL=http://searxng:8080"]
    if account: cmd.extend(["-e", f"GOG_ACCOUNT={account}"])
    cmd.extend([container, "node", "/app/dist/index.js", "agent", "--message", prompt, "--session-id", "ea-exec"])
    
    print(f"\n========================================", flush=True)
    print(f"🚀 [AGENT DEPLOYED] {container}\n🎯 [TASK] {task_name}", flush=True)
    print(f"========================================\n", flush=True)
    
    try:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        output = []
        last_tg_update = 0
        while True:
            line = await process.stdout.readline()
            if not line: break
            line_str = line.decode('utf-8', errors='replace').strip()
            if not line_str: continue
            
            clean_line = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line_str)
            print(f"[{container}] {clean_line}", flush=True)
            output.append(clean_line)
            
            now = time.time()
            if status_cb and (now - last_tg_update > 1.2):
                lower = clean_line.lower()
                if "rate limit" in lower or "429" in lower:
                    asyncio.create_task(status_cb(f"⚠️ <b>API Rate Limit Hit:</b> Cycling keys..."))
                    last_tg_update = now
                # UNFILTERED HEARTBEAT: Streams the Agent's thoughts and bash commands directly to Telegram!
                elif len(clean_line) < 150 and not clean_line.startswith("{") and not clean_line.startswith("["):
                    if any(k in lower for k in ["action", "observation", "creating", "inserting", "executing", "gog", "calendar", "fetching"]):
                        clean_display = clean_line.replace("<", "&lt;").replace(">", "&gt;")
                        clean_display = re.sub(r'^\[.*?\]\s*', '', clean_display) # Strip container prefix
                        asyncio.create_task(status_cb(f"<i>⚙️ {clean_display[:80]}...</i>"))
                        last_tg_update = now
        await process.wait()
        return "\n".join(output)
    except Exception as e: return f"Error: {e}"
