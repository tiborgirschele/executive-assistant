from __future__ import annotations

from typing import Any

from app.skills.registry import skill_or_raise


def dispatch_skill_operation(
    *,
    skill_key: str,
    operation: str,
    tenant: str,
    chat_id: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = skill_or_raise(skill_key)
    op = str(operation or "").strip().lower()
    if op not in contract.operations:
        return {
            "ok": False,
            "status": "unsupported_operation",
            "skill": contract.key,
            "operation": op,
        }
    return contract.handler(
        operation=op,
        tenant=str(tenant or ""),
        chat_id=int(chat_id),
        payload=dict(payload or {}),
    )
