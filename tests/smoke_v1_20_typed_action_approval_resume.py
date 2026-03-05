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


def test_typed_action_callback_routes_approval_resume_actions() -> None:
    _install_psycopg2_stub()
    _install_httpx_stub()
    import app.callback_commands as cc
    import app.intent_runtime as ir

    captured: dict[str, object] = {
        "steps": [],
        "finalized": [],
        "messages": [],
        "approval_calls": [],
    }

    class _FakeTG:
        async def send_message(self, chat_id: int, text: str, parse_mode: str | None = None, reply_markup=None):
            captured["messages"].append({"chat_id": int(chat_id), "text": str(text), "parse_mode": parse_mode})
            return {"ok": True, "message_id": 31}

    orig_create_session = cc.create_execution_session
    orig_mark_running = cc.mark_execution_session_running
    orig_mark_step = cc.mark_execution_step_status
    orig_finalize = cc.finalize_execution_session
    orig_append = cc.append_execution_event
    orig_resume = ir.execute_approved_intent_action

    try:
        cc.create_execution_session = lambda **kwargs: "sess-cb-approval-1"
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
        cc.append_execution_event = lambda *args, **kwargs: None

        async def _fake_resume(**kwargs):
            captured["approval_calls"].append(dict(kwargs))
            return {"ok": True, "status": "completed", "text": "✅ approved flow done", "result": {"ok": True}}

        ir.execute_approved_intent_action = _fake_resume

        async def _run() -> None:
            await cc._execute_typed_action_callback(
                tg=_FakeTG(),
                chat_id=777,
                tenant_name="tenant_demo",
                tenant_cfg={"openclaw_container": "openclaw-gateway-demo"},
                action_row={
                    "id": "action-approval-1",
                    "action_type": "intent:approval_execute",
                    "payload_json": {"session_id": "sess-parent-1", "prompt": "EXECUTE: approved"},
                },
            )

        asyncio.run(_run())

        assert captured["approval_calls"], "callback must delegate approval action to intent_runtime resume helper"
        call = captured["approval_calls"][0]
        assert str(call.get("tenant_name")) == "tenant_demo"
        assert str((call.get("tenant_cfg") or {}).get("openclaw_container")) == "openclaw-gateway-demo"
        assert not captured["messages"], "approval resume path should not send duplicate callback message"
        assert captured["finalized"], "typed action callback session must finalize"
        assert captured["finalized"][0]["status"] == "completed"
        step_pairs = {(step, status) for (step, status, _kwargs) in captured["steps"]}
        assert ("execute_intent", "completed") in step_pairs
        assert ("render_reply", "completed") in step_pairs
        _pass("v1.20 typed action approval-resume callback behavior")
    finally:
        cc.create_execution_session = orig_create_session
        cc.mark_execution_session_running = orig_mark_running
        cc.mark_execution_step_status = orig_mark_step
        cc.finalize_execution_session = orig_finalize
        cc.append_execution_event = orig_append
        ir.execute_approved_intent_action = orig_resume


if __name__ == "__main__":
    test_typed_action_callback_routes_approval_resume_actions()
