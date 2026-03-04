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


def _install_httpx_stub() -> None:
    if "httpx" in sys.modules:
        return
    fake_httpx = types.ModuleType("httpx")

    class _AsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    fake_httpx.AsyncClient = _AsyncClient
    sys.modules["httpx"] = fake_httpx


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_typed_action_callback_session_finalizes_with_execution_result() -> None:
    _install_psycopg2_stub()
    _install_httpx_stub()
    import app.callback_commands as cc

    captured: dict[str, object] = {
        "sessions": [],
        "steps": [],
        "finalized": [],
        "events": [],
        "messages": [],
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
            return {"ok": True, "message_id": 2}

    orig_create_session = cc.create_execution_session
    orig_mark_running = cc.mark_execution_session_running
    orig_mark_step = cc.mark_execution_step_status
    orig_finalize = cc.finalize_execution_session
    orig_event = cc.append_execution_event
    orig_execute = cc.execute_typed_action

    try:
        cc.create_execution_session = lambda **kwargs: captured["sessions"].append(dict(kwargs)) or "sess-cb-1"
        cc.mark_execution_session_running = lambda session_id: None
        cc.mark_execution_step_status = (
            lambda session_id, step_key, status, **kwargs: captured["steps"].append((step_key, status, dict(kwargs)))
        )
        cc.finalize_execution_session = (
            lambda session_id, status, outcome=None, last_error=None: captured["finalized"].append(
                {
                    "session_id": session_id,
                    "status": status,
                    "outcome": dict(outcome or {}),
                    "last_error": last_error,
                }
            )
        )
        cc.append_execution_event = (
            lambda session_id, event_type, message="", level="info", payload=None: captured["events"].append(
                {
                    "session_id": session_id,
                    "event_type": event_type,
                    "message": message,
                    "level": level,
                    "payload": dict(payload or {}),
                }
            )
        )

        def _fake_execute_typed_action(*, tenant_name: str, chat_id: int, action_row: dict, dispatch_skill):
            return {
                "action_type": str(action_row.get("action_type") or ""),
                "result": {"ok": True, "status": "planned"},
                "text": "✅ <b>Skill action staged.</b>",
            }

        cc.execute_typed_action = _fake_execute_typed_action

        async def _run() -> None:
            await cc._execute_typed_action_callback(
                tg=_FakeTG(),
                chat_id=777,
                tenant_name="tenant_demo",
                action_row={
                    "id": "action-99",
                    "action_type": "skill:prompt_compiler",
                    "payload_json": {"operation": "compile", "payload": {"notes": "Compile decision memo"}},
                },
            )

        asyncio.run(_run())

        assert captured["sessions"], "typed callback must create execution session"
        session_payload = captured["sessions"][0]
        assert session_payload.get("source") == "typed_action_callback"
        assert captured["messages"], "typed callback must send user response"
        assert "Skill action staged" in str(captured["messages"][0]["text"])
        assert captured["finalized"], "typed callback must finalize session"
        fin = captured["finalized"][0]
        assert fin["status"] == "completed"
        assert bool(fin["outcome"].get("ok")) is True
        step_pairs = {(step, status) for (step, status, _kwargs) in captured["steps"]}
        assert ("compile_intent", "completed") in step_pairs
        assert ("execute_intent", "running") in step_pairs
        assert ("execute_intent", "completed") in step_pairs
        assert ("render_reply", "completed") in step_pairs
        _pass("v1.20 typed action callback runtime behavior")
    finally:
        cc.create_execution_session = orig_create_session
        cc.mark_execution_session_running = orig_mark_running
        cc.mark_execution_step_status = orig_mark_step
        cc.finalize_execution_session = orig_finalize
        cc.append_execution_event = orig_event
        cc.execute_typed_action = orig_execute


if __name__ == "__main__":
    test_typed_action_callback_session_finalizes_with_execution_result()
