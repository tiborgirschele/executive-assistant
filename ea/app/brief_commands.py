from __future__ import annotations

import json
import os
import threading
import time

_BRIEF_INFLIGHT_LOCK = threading.Lock()
_BRIEF_INFLIGHT_CHATS: set[int] = set()


def brief_dedupe_interval_sec() -> int:
    try:
        value = int(os.getenv("EA_BRIEF_COMMAND_MIN_INTERVAL_SEC", "120"))
    except Exception:
        value = 120
    return max(0, value)


def brief_command_throttled(chat_id: int) -> bool:
    """
    Return True if /brief was recently requested for this chat.
    Persists state across restarts in attachments volume.
    """
    min_interval_sec = brief_dedupe_interval_sec()
    if min_interval_sec <= 0:
        return False
    state_path = os.path.join(
        os.getenv("EA_ATTACHMENTS_DIR", "/attachments"),
        ".brief_last_command.json",
    )
    now = int(time.time())
    key = str(int(chat_id))
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f) if f else {}
        if not isinstance(state, dict):
            state = {}
    except Exception:
        state = {}
    last_ts = int((state or {}).get(key) or 0)
    if last_ts > 0 and (now - last_ts) < min_interval_sec:
        return True
    try:
        state[key] = now
        os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
        tmp = state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, state_path)
    except Exception:
        pass
    return False


def brief_enter(chat_id: int) -> bool:
    with _BRIEF_INFLIGHT_LOCK:
        if int(chat_id) in _BRIEF_INFLIGHT_CHATS:
            return False
        _BRIEF_INFLIGHT_CHATS.add(int(chat_id))
        return True


def brief_exit(chat_id: int) -> None:
    with _BRIEF_INFLIGHT_LOCK:
        _BRIEF_INFLIGHT_CHATS.discard(int(chat_id))
