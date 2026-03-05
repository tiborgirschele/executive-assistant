from __future__ import annotations

import re
from typing import Any

from app.planner.intent_compiler import compile_intent_spec_v2


def _surface_type(msg: dict[str, Any]) -> str:
    if msg.get("photo"):
        return "photo"
    if msg.get("document"):
        return "document"
    if msg.get("voice"):
        return "voice"
    if msg.get("audio"):
        return "audio"
    if msg.get("text") or msg.get("caption"):
        return "text"
    return "unknown"


def build_route_signal(msg: dict[str, Any]) -> dict[str, Any]:
    payload = dict(msg or {})
    text = str(payload.get("text") or payload.get("caption") or "").strip()
    has_url = bool(re.search(r"https?://", text))
    preview = compile_intent_spec_v2(text=text, has_url=has_url) if text and not text.startswith("/") else {}
    return {
        "surface_type": _surface_type(payload),
        "has_url": has_url,
        "is_command": bool(text.startswith("/")),
        "domain": str((preview or {}).get("domain") or ""),
        "task_type": str((preview or {}).get("task_type") or ""),
        "intent_type": str((preview or {}).get("intent_type") or ""),
    }


__all__ = ["build_route_signal"]
