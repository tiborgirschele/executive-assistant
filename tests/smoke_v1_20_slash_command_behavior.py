from __future__ import annotations

import asyncio
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
for path in (str(ROOT), str(EA_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _install_psycopg2_stub() -> None:
    if "psycopg2" in sys.modules:
        return
    fake_psycopg2 = types.ModuleType("psycopg2")
    fake_pool_mod = types.ModuleType("psycopg2.pool")
    fake_extras_mod = types.ModuleType("psycopg2.extras")

    class _ThreadedConnectionPool:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def getconn(self):
            raise RuntimeError("psycopg2 stub: no db connection available")

        def putconn(self, conn) -> None:
            return None

    fake_pool_mod.ThreadedConnectionPool = _ThreadedConnectionPool
    fake_psycopg2.pool = fake_pool_mod
    fake_extras_mod.RealDictCursor = object
    sys.modules["psycopg2"] = fake_psycopg2
    sys.modules["psycopg2.pool"] = fake_pool_mod
    sys.modules["psycopg2.extras"] = fake_extras_mod


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_skill_command_uses_planning_task_type_and_records_session() -> None:
    _install_psycopg2_stub()
    import app.skill_commands as sc
    import app.actions as actions
    import app.skills.capability_router as capability_router

    class _FakeContract:
        operations = ("plan", "polish")
        planning_task_type = "polish_human_tone"

    captured: dict[str, object] = {
        "step_calls": [],
        "finalized": [],
        "messages": [],
        "task_types": [],
        "created_actions": [],
    }

    class _FakeTG:
        async def send_message(self, chat_id: int, text: str, parse_mode: str | None = None, reply_markup=None):
            captured["messages"].append(
                {
                    "chat_id": int(chat_id),
                    "text": str(text),
                    "parse_mode": parse_mode,
                    "reply_markup": reply_markup,
                }
            )
            return {"ok": True, "message_id": 1}

    orig_create_session = sc.create_execution_session
    orig_mark_running = sc.mark_execution_session_running
    orig_mark_step = sc.mark_execution_step_status
    orig_finalize = sc.finalize_execution_session
    orig_create_action = actions.create_action
    orig_build_plan = capability_router.build_capability_plan

    try:
        sc.create_execution_session = lambda **kwargs: "sess-skill-1"
        sc.mark_execution_session_running = lambda session_id: None
        sc.mark_execution_step_status = (
            lambda session_id, step_key, status, **kwargs: captured["step_calls"].append((step_key, status, kwargs))
        )
        sc.finalize_execution_session = (
            lambda session_id, status, outcome=None, last_error=None: captured["finalized"].append(
                {
                    "session_id": session_id,
                    "status": status,
                    "outcome": dict(outcome or {}),
                    "last_error": last_error,
                }
            )
        )

        def _fake_create_action(tenant: str, action_type: str, payload: dict, days: int = 7) -> str:
            captured["created_actions"].append(
                {
                    "tenant": tenant,
                    "action_type": action_type,
                    "payload": dict(payload),
                    "days": days,
                }
            )
            return "act-skill-123"

        def _fake_build_plan(task_type: str, preferred: str | None = None) -> dict[str, object]:
            captured["task_types"].append(str(task_type))
            return {
                "ok": True,
                "status": "planned",
                "task_type": str(task_type),
                "primary": "undetectable",
                "fallbacks": ["prompting_systems"],
                "candidates": ["undetectable", "prompting_systems"],
            }

        actions.create_action = _fake_create_action
        capability_router.build_capability_plan = _fake_build_plan

        async def _run() -> None:
            await sc.handle_skill_command(
                tg=_FakeTG(),
                chat_id=42,
                command_text="/skill draft_and_polish polish Make this warmer and concise",
                tenant_name="tenant_demo",
            )

        asyncio.run(_run())

        assert captured["task_types"] == ["polish_human_tone"], "planning task type must come from contract"
        assert captured["created_actions"], "skill command must create a typed action"
        created = captured["created_actions"][0]
        assert created["action_type"] == "skill:draft_and_polish"
        assert captured["messages"], "skill command must send a reply"
        text = str(captured["messages"][0]["text"])
        assert "Primary capability" in text
        assert "undetectable" in text
        assert captured["finalized"], "session must be finalized"
        assert captured["finalized"][0]["status"] == "completed"
        step_pairs = {(step, status) for (step, status, _kwargs) in captured["step_calls"]}
        assert ("compile_intent", "completed") in step_pairs
        assert ("execute_intent", "running") in step_pairs
        assert ("execute_intent", "completed") in step_pairs
        assert ("persist_result", "completed") in step_pairs
        _pass("v1.20 slash command runtime behavior")
    finally:
        sc.create_execution_session = orig_create_session
        sc.mark_execution_session_running = orig_mark_running
        sc.mark_execution_step_status = orig_mark_step
        sc.finalize_execution_session = orig_finalize
        actions.create_action = orig_create_action
        capability_router.build_capability_plan = orig_build_plan


if __name__ == "__main__":
    test_skill_command_uses_planning_task_type_and_records_session()
