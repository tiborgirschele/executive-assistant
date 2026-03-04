from __future__ import annotations

from typing import Any, Callable


def build_generic_skill_handler(skill_key: str, capabilities: tuple[str, ...]) -> Callable[..., dict[str, Any]]:
    key = str(skill_key or "").strip().lower()
    caps = tuple(str(x or "").strip().lower() for x in capabilities if str(x or "").strip())

    def _run_operation(
        *,
        operation: str,
        tenant: str,
        chat_id: int,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "not_implemented",
            "skill": key,
            "operation": str(operation or "").strip().lower(),
            "tenant": str(tenant or ""),
            "chat_id": int(chat_id),
            "payload": dict(payload or {}),
            "capabilities": list(caps),
            "message": "Skill contract exists but implementation is pending.",
        }

    return _run_operation


__all__ = ["build_generic_skill_handler"]
