from __future__ import annotations

import html
from typing import Any

from app.execution import (
    compile_intent_spec,
    create_execution_session,
    finalize_execution_session,
    mark_execution_session_running,
    mark_execution_step_status,
)


async def handle_skill_command(
    *,
    tg,
    chat_id: int,
    command_text: str,
    tenant_name: str,
) -> None:
    from app.actions import create_action
    from app.skills.capability_router import build_capability_plan
    from app.skills.registry import list_skills, skill_or_raise

    session_id = create_execution_session(
        tenant=str(tenant_name or ""),
        chat_id=int(chat_id),
        intent_spec=compile_intent_spec(
            text=f"Handle slash skill command: {str(command_text or '').strip()}",
            tenant=str(tenant_name or ""),
            chat_id=int(chat_id),
            has_url=False,
        ),
        plan_steps=[
            {"step_key": "compile_intent", "step_title": "Compile Slash Command Intent"},
            {"step_key": "execute_intent", "step_title": "Validate and Stage Skill Action"},
            {"step_key": "persist_result", "step_title": "Persist Command Result"},
        ],
        source="slash_command_skill",
    )
    if session_id:
        mark_execution_session_running(session_id)
        mark_execution_step_status(
            session_id,
            "compile_intent",
            "completed",
            result={"command": "/skill", "chat_id": int(chat_id)},
        )

    async def _final_reply(
        *,
        text: str,
        result_status: str,
        session_status: str,
        reply_markup: dict[str, Any] | None = None,
    ):
        if session_id:
            mark_execution_step_status(
                session_id,
                "persist_result",
                "running",
                result={"result_status": result_status},
            )
            mark_execution_step_status(
                session_id,
                "persist_result",
                "completed",
                result={"result_status": result_status},
            )
            finalize_execution_session(
                session_id,
                status=session_status,
                outcome={"command": "/skill", "result_status": result_status},
            )
        return await tg.send_message(chat_id, text, parse_mode="HTML", reply_markup=reply_markup)

    if session_id:
        mark_execution_step_status(
            session_id,
            "execute_intent",
            "running",
            evidence={"command_text": str(command_text or "")[:300]},
        )

    tokens = str(command_text or "").strip().split()
    if len(tokens) < 2:
        skills = [str(row.get("key") or "") for row in list_skills()]
        avail = ", ".join(sorted([k for k in skills if k])) or "none"
        if session_id:
            mark_execution_step_status(
                session_id,
                "execute_intent",
                "completed",
                result={"result_status": "usage", "available_skill_count": len(skills)},
            )
        return await _final_reply(
            text=(
                "Usage: <code>/skill &lt;skill_key&gt; [operation] [notes]</code>\n\n"
                f"Available: <code>{html.escape(avail, quote=False)}</code>"
            ),
            result_status="usage",
            session_status="completed",
        )

    skill_key = str(tokens[1] or "").strip().lower()
    try:
        contract = skill_or_raise(skill_key)
    except Exception:
        if session_id:
            mark_execution_step_status(
                session_id,
                "execute_intent",
                "completed",
                result={"result_status": "unknown_skill", "skill_key": skill_key},
            )
        return await _final_reply(
            text=f"⚠️ Unknown skill: <code>{html.escape(skill_key, quote=False)}</code>",
            result_status="unknown_skill",
            session_status="completed",
        )

    operation = str(tokens[2] or "").strip().lower() if len(tokens) >= 3 else (
        str(contract.operations[0]) if contract.operations else "plan"
    )
    if operation not in tuple(contract.operations):
        if session_id:
            mark_execution_step_status(
                session_id,
                "execute_intent",
                "completed",
                result={"result_status": "unsupported_operation", "skill_key": skill_key, "operation": operation},
            )
        return await _final_reply(
            text=(
                f"⚠️ Unsupported operation for <code>{html.escape(skill_key, quote=False)}</code>.\n"
                f"Allowed: <code>{html.escape(', '.join(contract.operations), quote=False)}</code>"
            ),
            result_status="unsupported_operation",
            session_status="completed",
        )

    notes = " ".join(tokens[3:]).strip()
    action_payload: dict[str, Any] = {"operation": operation, "payload": {}}
    if notes:
        action_payload["payload"]["notes"] = notes[:500]

    act_id = create_action(
        tenant=str(tenant_name or ""),
        action_type=f"skill:{skill_key}",
        payload=action_payload,
        days=2,
    )
    planning_task = str(getattr(contract, "planning_task_type", "") or "").strip().lower() or skill_key
    plan = build_capability_plan(planning_task)
    primary = str((plan or {}).get("primary") or "").strip()
    fallbacks = list((plan or {}).get("fallbacks") or [])
    lines = [
        f"🧩 <b>Skill queued:</b> <code>{html.escape(skill_key, quote=False)}</code> / <code>{html.escape(operation, quote=False)}</code>",
    ]
    if primary:
        lines.append(f"Primary capability: <code>{html.escape(primary, quote=False)}</code>")
    if fallbacks:
        lines.append(f"Fallbacks: <code>{html.escape(', '.join(str(x) for x in fallbacks), quote=False)}</code>")
    if notes:
        lines.append(f"Notes: {html.escape(notes[:160], quote=False)}")
    kb = {"inline_keyboard": [[{"text": "▶️ Execute Skill Plan", "callback_data": f"act:{act_id}"}]]}
    if session_id:
        mark_execution_step_status(
            session_id,
            "execute_intent",
            "completed",
            result={"result_status": "queued", "skill_key": skill_key, "operation": operation, "action_id": act_id},
        )
    return await _final_reply(
        text="\n".join(lines),
        result_status="queued",
        session_status="completed",
        reply_markup=kb,
    )


__all__ = ["handle_skill_command"]
