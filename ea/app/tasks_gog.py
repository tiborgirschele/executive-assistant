from __future__ import annotations
import json
import subprocess
from typing import Any, Dict, List, Optional, Tuple

try:
    from app.audit import log_event
except Exception:
    def log_event(*args: Any, **kwargs: Any) -> None: pass

def _docker_exec(container: str, argv: List[str], timeout_s: int = 45) -> Tuple[int, str, str]:
    cmd = ["docker", "exec", container] + argv
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    return p.returncode, p.stdout or "", p.stderr or ""

def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty output")
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "[{":
            try:
                obj, _ = dec.raw_decode(text[i:])
                return obj
            except Exception:
                continue
    raise ValueError("no JSON found in output")

def _normalize_list(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for k in ("items", "tasklists", "lists", "data", "result"):
            v = obj.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []

def _with_account(cmd: List[str], account: Optional[str]) -> List[List[str]]:
    if not account or not cmd or cmd[0] != "gog":
        return [cmd]
    return [["gog", "--account", account] + cmd[1:], cmd + ["--account", account], cmd]

def _try_json_cmds(container: str, candidates: List[List[str]], account: Optional[str]) -> Tuple[Any, List[str]]:
    last_err = ""
    for base in candidates:
        for cmd in _with_account(base, account):
            rc, out, err = _docker_exec(container, cmd)
            if rc != 0:
                last_err = (err or out).strip()[:500]
                continue
            try:
                return _extract_json(out), cmd
            except Exception as e:
                last_err = f"json parse failed: {e}"
                continue
    raise RuntimeError(last_err or "no candidate command succeeded")

def tasklists(container: str, account: Optional[str] = None) -> List[Dict[str, Any]]:
    candidates = [["gog", "tasks", "lists", "--json"], ["gog", "tasks", "tasklists", "--json"]]
    obj, used = _try_json_cmds(container, candidates, account)
    return _normalize_list(obj)

def tasks_in_list(container: str, list_id: str, account: Optional[str] = None, include_completed: bool = False) -> List[Dict[str, Any]]:
    candidates = [["gog", "tasks", "list", list_id, "--json"], ["gog", "tasks", "list", "--list", list_id, "--json"]]
    if include_completed:
        candidates = [c + ["--include-completed"] for c in candidates] + candidates
    obj, used = _try_json_cmds(container, candidates, account)
    return _normalize_list(obj)

def fetch_tasks_best_effort(
    container: str,
    account: Optional[str] = None,
    include_completed: bool = False,
    max_lists: int = 6,
    max_per_list: int = 80
) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    try:
        lists = tasklists(container, account=account)[:max_lists]
    except Exception as e:
        warnings.append(f"tasklists failed: {e}")
        return [], warnings

    out: List[Dict[str, Any]] = []
    for tl in lists:
        list_id = str(tl.get("id") or tl.get("tasklist_id") or tl.get("taskListId") or "").strip()
        title = str(tl.get("title") or tl.get("name") or "").strip() or "Tasks"
        if not list_id:
            continue
        try:
            rows = tasks_in_list(container, list_id, account=account, include_completed=include_completed)
            for t in rows[:max_per_list]:
                t["_source_container"] = container
                t["_tasklist_id"] = list_id
                t["_tasklist_title"] = title
                out.append(t)
        except Exception as e:
            warnings.append(f"list {title} failed: {e}")
    return out, warnings

def mark_task_completed(container: str, list_id: str, task_id: str, account: Optional[str] = None) -> bool:
    cmd = ["gog", "tasks", "update", list_id, task_id, "--status", "completed"]
    last_err = ""
    for c in _with_account(cmd, account):
        rc, out, err = _docker_exec(container, c)
        if rc == 0:
            log_event(None, "tasks", "mark_completed_ok", f"{container} {list_id} {task_id}", {})
            return True
        last_err = (err or out).strip()[:400]
    log_event(None, "tasks", "mark_completed_fail", f"{container} {list_id} {task_id}", {"err": last_err})
    return False

def find_tasklist_id_by_name(container: str, name: str, account: Optional[str] = None) -> Optional[str]:
    try:
        lists = tasklists(container, account=account)
    except Exception:
        return None
    want = (name or "").strip().lower()
    for tl in lists:
        title = str(tl.get("title") or tl.get("name") or "").strip().lower()
        if title == want and (tl.get("id") or tl.get("tasklist_id") or tl.get("taskListId")):
            return str(tl.get("id") or tl.get("tasklist_id") or tl.get("taskListId"))
    # fallback: substring match
    for tl in lists:
        title = str(tl.get("title") or tl.get("name") or "").strip().lower()
        if want and want in title and (tl.get("id") or tl.get("tasklist_id") or tl.get("taskListId")):
            return str(tl.get("id") or tl.get("tasklist_id") or tl.get("taskListId"))
    return None

def create_task_best_effort(container: str, list_id: str, title: str, account: Optional[str] = None) -> bool:
    """
    Best-effort writer: tries multiple gog syntaxes.
    """
    t = (title or "").strip()
    if not list_id or not t:
        return False

    candidates = [
        ["gog", "tasks", "add", list_id, t],
        ["gog", "tasks", "create", list_id, t],
        ["gog", "tasks", "insert", list_id, t],
        ["gog", "tasks", "new", list_id, t],
        ["gog", "tasks", "add", "--list", list_id, "--title", t],
        ["gog", "tasks", "create", "--list", list_id, "--title", t],
    ]

    last_err = ""
    for base in candidates:
        for cmd in _with_account(base, account):
            rc, out, err = _docker_exec(container, cmd)
            if rc == 0:
                log_event(None, "tasks", "create_ok", f"{container} {list_id}", {"title": t})
                return True
            last_err = (err or out).strip()[:400]
    log_event(None, "tasks", "create_fail", f"{container} {list_id}", {"title": t, "err": last_err})
    return False
