

import os
import asyncio
import re
import time
import shutil
from app.settings import settings

try:
    import docker as docker_sdk
except Exception:
    docker_sdk = None


def _llm_env_values() -> tuple[str, str, str]:
    gemini_key = (
        getattr(settings, "gemini_api_key", None)
        or os.environ.get("GEMINI_API_KEY")
        or ""
    )
    litellm_key = (
        getattr(settings, "litellm_api_key", None)
        or os.environ.get("LITELLM_API_KEY")
        or ""
    )
    model = os.environ.get("LLM_MODEL", "gemini/gemini-2.5-flash")
    return gemini_key, litellm_key, model


def _llm_env_cli_args() -> list[str]:
    gemini_key, litellm_key, model = _llm_env_values()
    args: list[str] = ["-e", f"LLM_MODEL={model}"]
    if gemini_key:
        args.extend(["-e", f"GEMINI_API_KEY={gemini_key}"])
    if litellm_key:
        args.extend(["-e", f"LITELLM_API_KEY={litellm_key}"])
    return args


def _llm_env_dict() -> dict[str, str]:
    gemini_key, litellm_key, model = _llm_env_values()
    env = {"LLM_MODEL": model}
    if gemini_key:
        env["GEMINI_API_KEY"] = gemini_key
    if litellm_key:
        env["LITELLM_API_KEY"] = litellm_key
    return env


def _env_cli_args(extra_env: dict[str, str] | None) -> list[str]:
    args: list[str] = []
    for k, v in (extra_env or {}).items():
        if v is None:
            continue
        args.extend(["-e", f"{k}={v}"])
    return args


def _merged_exec_env(extra_env: dict[str, str] | None) -> dict[str, str]:
    env = _llm_env_dict()
    for k, v in (extra_env or {}).items():
        if v is None:
            continue
        env[str(k)] = str(v)
    return env


async def docker_exec(
    container: str,
    argv: list[str],
    *,
    user: str = "root",
    extra_env: dict[str, str] | None = None,
    timeout_s: float = 30.0,
) -> str:
    cmd = ["docker", "exec", *_llm_env_cli_args(), *_env_cli_args(extra_env), "-u", user, container, *argv]
    try:
        if shutil.which("docker"):
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_s)
            return stdout.decode('utf-8', errors='replace')
    except Exception:
        pass

    # Fallback when docker CLI is unavailable in this runtime image.
    if docker_sdk is not None:
        try:
            def _exec_via_sdk() -> str:
                client = docker_sdk.DockerClient(base_url='unix://var/run/docker.sock')
                c = client.containers.get(container)
                out = c.exec_run(
                    argv,
                    user=user,
                    environment=_merged_exec_env(extra_env),
                    demux=False,
                )
                data = out.output if hasattr(out, "output") else out[1]
                if isinstance(data, (bytes, bytearray)):
                    return data.decode("utf-8", errors="replace")
                return str(data or "")
            return await asyncio.wait_for(asyncio.to_thread(_exec_via_sdk), timeout=timeout_s)
        except Exception:
            pass
    return "[]"


async def gog_cli(
    container: str,
    command: list,
    account: str = "",
    *,
    extra_env: dict[str, str] | None = None,
) -> str:
    del account  # Compatibility: account is carried via command/env by callers.
    return await docker_exec(
        container,
        ["gog"] + command,
        user="root",
        extra_env=extra_env,
        timeout_s=30.0,
    )

async def gog_scout(container: str, prompt: str, account: str, status_cb=None, task_name="Task") -> str:
    keyring_password = (
        getattr(settings, "gog_keyring_password", None)
        or os.environ.get("GOG_KEYRING_PASSWORD")
        or os.environ.get("EA_GOG_KEYRING_PASSWORD")
    )
    if not keyring_password:
        return "Execution keyring is not configured. Please ask the operator to set GOG keyring credentials."
    cmd = [
        "docker",
        "exec",
        *_llm_env_cli_args(),
        "-e",
        f"GOG_KEYRING_PASSWORD={keyring_password}",
        "-e",
        "WEB_PROVIDER=searxng",
        "-e",
        "SEARXNG_URL=http://searxng:8080",
    ]
    if account: cmd.extend(["-e", f"GOG_ACCOUNT={account}"])
    cmd.extend([container, "node", "/app/dist/index.js", "agent", "--message", prompt, "--session-id", "ea-exec"])
    
    print(f"\n========================================", flush=True)
    print(f"🚀 [AGENT DEPLOYED] {container}\n🎯 [TASK] {task_name}", flush=True)
    print(f"========================================\n", flush=True)
    
    if shutil.which("docker"):
        try:
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            output = []
            last_tg_update = 0
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode('utf-8', errors='replace').strip()
                if not line_str:
                    continue

                clean_line = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line_str)
                print(f"[{container}] {clean_line}", flush=True)
                output.append(clean_line)

                now = time.time()
                if status_cb and (now - last_tg_update > 1.2):
                    lower = clean_line.lower()
                    if "rate limit" in lower or "429" in lower:
                        asyncio.create_task(status_cb("⚠️ <b>API Rate Limit Hit:</b> Cycling keys..."))
                        last_tg_update = now
                    elif len(clean_line) < 150 and not clean_line.startswith("{") and not clean_line.startswith("["):
                        if any(k in lower for k in ["action", "observation", "creating", "inserting", "executing", "gog", "calendar", "fetching"]):
                            clean_display = clean_line.replace("<", "&lt;").replace(">", "&gt;")
                            clean_display = re.sub(r'^\[.*?\]\s*', '', clean_display)
                            asyncio.create_task(status_cb(f"<i>⚙️ {clean_display[:80]}...</i>"))
                            last_tg_update = now
            await process.wait()
            return "\n".join(output)
        except Exception:
            pass

    if docker_sdk is not None:
        try:
            def _exec_via_sdk() -> str:
                client = docker_sdk.DockerClient(base_url='unix://var/run/docker.sock')
                c = client.containers.get(container)
                out = c.exec_run(
                    ["node", "/app/dist/index.js", "agent", "--message", prompt, "--session-id", "ea-exec"],
                    user="root",
                    environment={
                        **_llm_env_dict(),
                        "GOG_KEYRING_PASSWORD": keyring_password,
                        "WEB_PROVIDER": "searxng",
                        "SEARXNG_URL": "http://searxng:8080",
                        **({"GOG_ACCOUNT": account} if account else {}),
                    },
                    demux=False,
                )
                data = out.output if hasattr(out, "output") else out[1]
                if isinstance(data, (bytes, bytearray)):
                    return data.decode("utf-8", errors="replace")
                return str(data or "")
            return await asyncio.wait_for(asyncio.to_thread(_exec_via_sdk), timeout=30.0)
        except Exception:
            pass

    return "Execution backend is temporarily unavailable. Please try again in a moment."
