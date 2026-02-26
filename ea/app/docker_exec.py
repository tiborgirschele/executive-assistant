from __future__ import annotations
from typing import Dict, List, Optional, Tuple
import httpx
from app.settings import settings

def _client(timeout_s: float) -> httpx.Client:
    transport = httpx.HTTPTransport(uds=settings.docker_sock)
    return httpx.Client(base_url="http://docker", transport=transport, timeout=timeout_s)

def docker_exec(container: str, cmd: List[str], *, env: Optional[Dict[str, str]] = None,
               timeout_s: float = 180.0) -> Tuple[int, str]:
    body: Dict[str, object] = {"AttachStdout": True, "AttachStderr": True, "Cmd": cmd, "Tty": True}
    if env:
        body["Env"] = [f"{k}={v}" for k, v in env.items()]

    with _client(timeout_s) as c:
        r = c.post(f"/containers/{container}/exec", json=body)
        r.raise_for_status()
        exec_id = r.json().get("Id")
        if not exec_id:
            raise RuntimeError(f"No exec id: {r.text}")

        r2 = c.post(f"/exec/{exec_id}/start", json={"Detach": False, "Tty": True})
        r2.raise_for_status()
        out = r2.content.decode(errors="replace")

        r3 = c.get(f"/exec/{exec_id}/json")
        r3.raise_for_status()
        exit_code = int((r3.json() or {}).get("ExitCode") or 0)

    return exit_code, out
