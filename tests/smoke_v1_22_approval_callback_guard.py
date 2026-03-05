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


def test_approval_callback_guard_expired_and_replayed() -> None:
    _install_psycopg2_stub()
    _install_httpx_stub()
    import app.actions as actions
    import app.callback_commands as cc

    captured: dict[str, object] = {"answers": [], "executed": [], "consume_calls": 0}

    class _FakeTG:
        async def answer_callback_query(self, qid: str, text: str = "", show_alert: bool = False):
            captured["answers"].append({"id": str(qid), "text": str(text), "show_alert": bool(show_alert)})
            return {"ok": True}

        async def edit_message_reply_markup(self, *args, **kwargs):
            return {"ok": True}

    async def _fake_security(chat_id: int):
        return "chat_100284", {"openclaw_container": "openclaw-gateway-demo"}

    async def _fake_trigger(chat_id: int, email: str, tenant_cfg: dict, scopes: str = ""):
        return None

    orig_consume_action = actions.consume_action
    orig_peek_action = actions.peek_action
    orig_eval = cc.evaluate_approval_gate
    orig_exec = cc._execute_typed_action_callback
    orig_get_button_context = cc.get_button_context
    try:
        actions.peek_action = lambda tenant, aid: {
            "id": aid,
            "action_type": "intent:approval_execute",
            "approval_gate_id": "gate-1",
            "payload_json": {"session_id": "s", "prompt": "EXECUTE: x"},
        }

        def _consume_action(tenant, aid):
            captured["consume_calls"] = int(captured.get("consume_calls") or 0) + 1
            return {
                "id": aid,
                "action_type": "intent:approval_execute",
                "approval_gate_id": "gate-1",
                "payload_json": {"session_id": "s", "prompt": "EXECUTE: x"},
            }

        actions.consume_action = _consume_action

        async def _fake_exec(**kwargs):
            captured["executed"].append(dict(kwargs))
            return None

        cc._execute_typed_action_callback = _fake_exec
        cc.get_button_context = lambda action_id: (_ for _ in ()).throw(RuntimeError("should_not_read_button_context"))

        async def _run(reason: str) -> None:
            cc.evaluate_approval_gate = lambda gate_id: (False, reason)
            await cc.handle_callback_command(
                tg=_FakeTG(),
                cb={
                    "id": "cb-1",
                    "data": "act:action-1",
                    "message": {"chat": {"id": 101}, "message_id": 88, "reply_markup": {"inline_keyboard": []}},
                },
                check_security=_fake_security,
                auth_sessions=None,
                trigger_auth_flow=_fake_trigger,
            )

        asyncio.run(_run("expired"))
        asyncio.run(_run("already_approved"))
    finally:
        actions.consume_action = orig_consume_action
        actions.peek_action = orig_peek_action
        cc.evaluate_approval_gate = orig_eval
        cc._execute_typed_action_callback = orig_exec
        cc.get_button_context = orig_get_button_context

    answers = [str((row or {}).get("text") or "") for row in list(captured["answers"] or [])]
    assert any("expired" in txt.lower() for txt in answers), "expired gate should be blocked"
    assert any("already processed" in txt.lower() for txt in answers), "replayed gate should be blocked"
    assert int(captured.get("consume_calls") or 0) == 0, "invalid approval gate should not consume typed action"
    assert not captured["executed"], "guarded callbacks must not execute typed action"
    _pass("v1.22 approval callback guard behavior")


if __name__ == "__main__":
    test_approval_callback_guard_expired_and_replayed()
