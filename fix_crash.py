import glob, subprocess, time, sys, re

print("=== 1. DIAGNOSING THE CRASH ===")
res = subprocess.run(["docker", "logs", "--tail", "15", "ea-daemon"], capture_output=True, text=True)
print(res.stdout + res.stderr)

print("\n=== 2. FIXING SYNTAX ON THE HOST ===")
patched = False
for path in glob.glob("ea/app/*.py"):
    with open(path, "r") as f: content = f.read()
    orig = content
    
    # Python strictly requires from __future__ to be the absolute first line.
    # My previous script pushed it down, causing the fatal crash loop.
    if "from __future__ import annotations" in content and not content.startswith("from __future__"):
        content = re.sub(r"from __future__ import annotations\r?\n?", "", content)
        content = "from __future__ import annotations\n" + content.lstrip()
        
    if content != orig:
        with open(path, "w") as f: f.write(content)
        print(f"✅ Restored __future__ import to line 1 in {path}")
        patched = True
        
    # Verify the code compiles natively before we even bother Docker
    try:
        compile(content, path, 'exec')
    except SyntaxError as e:
        print(f"❌ SyntaxError in {path}: {e}")
        sys.exit(1)

if not patched:
    print("✅ Files were already syntactically correct.")

print("\n=== 3. RESTARTING EA-DAEMON ===")
subprocess.run(["docker", "compose", "restart", "ea-daemon"], check=True)
print("--> Waiting 6 seconds to verify stable boot...")
time.sleep(6)

print("\n=== 4. 🧪 VERIFYING CONTAINER HEALTH ===")
# Checking actual Docker state, not just grepping strings
res = subprocess.run(["docker", "ps", "--filter", "name=ea-daemon", "--format", "{{.Status}}"], capture_output=True, text=True)

if "Restarting" in res.stdout or "Exited" in res.stdout or not res.stdout.strip():
    print("❌ Daemon is STILL crashing! Logs:")
    res_logs = subprocess.run(["docker", "logs", "--tail", "20", "ea-daemon"], capture_output=True, text=True)
    print(res_logs.stdout + res_logs.stderr)
    sys.exit(1)
else:
    print(f"✅ Container is UP and STABLE: {res.stdout.strip()}")
    print("👉 Pick up your phone and type /brief. The bot will respond with the typing indicator!")
