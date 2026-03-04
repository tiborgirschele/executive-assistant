from __future__ import annotations

import json
import os


def atomic_write_json(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        pass


def atomic_write_offset(offset: int, path: str = "/attachments/tg_offset.json") -> None:
    atomic_write_json(path, {"offset": int(offset)})


def read_offset(path: str = "/attachments/tg_offset.json") -> int:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        return int((data or {}).get("offset") or 0)
    except Exception:
        return 0
