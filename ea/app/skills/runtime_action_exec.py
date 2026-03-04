from __future__ import annotations

import html
import json
from typing import Any, Callable


def payload_to_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return dict(parsed)
        except Exception:
            return {}
    return {}


def typed_action_text(action_type: str, result: dict[str, Any]) -> str:
    status = str((result or {}).get("status") or "").strip()
    if action_type in ("confirm_payment", "cancel_payment"):
        if bool((result or {}).get("ok")):
            if status == "user_confirmed":
                return "🟢 <b>Payment confirmed and locked for execution.</b>"
            if status == "cancelled":
                return "🚫 <b>Payment draft cancelled.</b>"
            return "✅ <b>Payment action processed.</b>"
        return f"⚠️ <b>Payment action failed:</b> <code>{html.escape(status or 'unknown')}</code>"

    if action_type.startswith("skill:"):
        skill_key = action_type.split(":", 1)[1]
        operation = str((result or {}).get("operation") or "").strip()
        headline = f"🧩 <b>Skill result:</b> <code>{html.escape(skill_key)}</code>"
        if operation:
            headline += f" / <code>{html.escape(operation)}</code>"
        if status == "not_implemented":
            plan = (result or {}).get("plan") if isinstance((result or {}).get("plan"), dict) else {}
            primary = str((plan or {}).get("primary") or "").strip()
            fallbacks = list((plan or {}).get("fallbacks") or [])
            lines = [headline, "", "<i>Execution contract exists; implementation is pending.</i>"]
            if primary:
                lines.append(f"Primary capability: <code>{html.escape(primary)}</code>")
            if fallbacks:
                lines.append(f"Fallbacks: <code>{html.escape(', '.join(str(x) for x in fallbacks))}</code>")
            return "\n".join(lines)
        if bool((result or {}).get("ok")):
            return headline + "\n\n✅ <b>Skill action completed.</b>"
        return headline + f"\n\n⚠️ <b>Skill action failed:</b> <code>{html.escape(status or 'unknown')}</code>"

    return f"⚠️ <b>Unsupported typed action:</b> <code>{html.escape(action_type or 'unknown')}</code>"


def execute_typed_action(
    *,
    tenant_name: str,
    chat_id: int,
    action_row: dict[str, Any],
    dispatch_skill: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    action_type = str((action_row or {}).get("action_type") or "").strip()
    payload = payload_to_dict((action_row or {}).get("payload_json"))
    tenant = str(tenant_name or "")
    chat = int(chat_id)

    if action_type in ("confirm_payment", "cancel_payment"):
        result = dispatch_skill(
            skill_key="payments",
            operation="handle_action",
            tenant=tenant,
            chat_id=chat,
            payload={"action_type": action_type, "payload": payload},
        )
        return {"action_type": action_type, "result": result, "text": typed_action_text(action_type, result)}

    if action_type.startswith("skill:"):
        skill_key = action_type.split(":", 1)[1]
        operation = str(payload.get("operation") or "plan").strip().lower()
        op_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        result = dispatch_skill(
            skill_key=skill_key,
            operation=operation,
            tenant=tenant,
            chat_id=chat,
            payload=op_payload,
        )
        if isinstance(result, dict) and "operation" not in result:
            result["operation"] = operation
        return {"action_type": action_type, "result": result, "text": typed_action_text(action_type, result)}

    result = {"ok": False, "status": "unsupported_action"}
    return {"action_type": action_type, "result": result, "text": typed_action_text(action_type, result)}


__all__ = ["payload_to_dict", "typed_action_text", "execute_typed_action"]
