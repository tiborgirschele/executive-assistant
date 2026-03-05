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


def test_free_text_high_risk_stages_blocking_approval_gate() -> None:
    _install_psycopg2_stub()
    _install_httpx_stub()
    import app.intent_runtime as ir

    captured: dict[str, object] = {
        "steps": [],
        "finalized": [],
        "actions": [],
        "approval_gates": [],
        "approval_gate_attaches": [],
        "messages": [],
        "gog_called": False,
    }

    class _FakeTG:
        async def send_message(self, chat_id: int, text: str, parse_mode: str | None = None, reply_markup=None):
            captured["messages"].append({"kind": "send", "chat_id": int(chat_id), "text": str(text)})
            return {"ok": True, "message_id": 77}

        async def edit_message_text(
            self,
            chat_id: int,
            message_id: int,
            text: str,
            parse_mode: str | None = None,
            reply_markup=None,
            **kwargs,
        ):
            captured["messages"].append(
                {
                    "kind": "edit",
                    "chat_id": int(chat_id),
                    "message_id": int(message_id),
                    "text": str(text),
                    "parse_mode": parse_mode,
                    "reply_markup": reply_markup,
                }
            )
            return {"ok": True}

    orig_create_session = ir.create_execution_session
    orig_mark_running = ir.mark_execution_session_running
    orig_mark_step = ir.mark_execution_step_status
    orig_finalize = ir.finalize_execution_session
    orig_append = ir.append_execution_event
    orig_create_action = ir.create_action
    orig_create_gate = ir.create_approval_gate
    orig_attach_gate = ir.attach_approval_gate_action
    orig_mark_gate = ir.mark_approval_gate_decision
    orig_gog = ir.gog_scout

    try:
        ir.create_execution_session = lambda **kwargs: "sess-highrisk-1"
        ir.mark_execution_session_running = lambda session_id: None
        ir.mark_execution_step_status = (
            lambda session_id, step_key, status, **kwargs: captured["steps"].append((step_key, status, dict(kwargs)))
        )
        ir.finalize_execution_session = (
            lambda session_id, status, outcome=None, last_error=None: captured["finalized"].append(
                {"session_id": session_id, "status": status, "outcome": dict(outcome or {}), "last_error": last_error}
            )
        )
        ir.append_execution_event = lambda *args, **kwargs: None
        ir.create_approval_gate = (
            lambda **kwargs: captured["approval_gates"].append(dict(kwargs)) or "gate-approve-1"
        )
        ir.attach_approval_gate_action = (
            lambda approval_gate_id, action_id: captured["approval_gate_attaches"].append(
                {"approval_gate_id": str(approval_gate_id), "action_id": str(action_id)}
            )
        )
        ir.mark_approval_gate_decision = lambda *args, **kwargs: None
        ir.create_action = (
            lambda tenant, action_type, payload, days=1, **kwargs: captured["actions"].append(
                {
                    "tenant": str(tenant),
                    "action_type": str(action_type),
                    "payload": dict(payload),
                    "days": int(days),
                    "kwargs": dict(kwargs or {}),
                }
            )
            or "act-approve-1"
        )

        async def _forbidden_gog(*args, **kwargs):
            captured["gog_called"] = True
            raise AssertionError("gog_scout must not run before explicit approval")

        ir.gog_scout = _forbidden_gog

        async def _run() -> None:
            await ir.handle_free_text_intent(
                tg=_FakeTG(),
                chat_id=99,
                tenant_name="tenant_demo",
                text="Please pay this invoice now",
                tenant_cfg={},
                safe_err=lambda e: str(e),
            )

        asyncio.run(_run())

        assert captured["actions"], "high-risk free-text must stage an approval typed action"
        staged = captured["actions"][0]
        assert staged["action_type"] == "intent:approval_execute"
        assert staged["payload"].get("session_id") == "sess-highrisk-1"
        assert staged["payload"].get("approval_gate_id") == "gate-approve-1"
        assert captured["approval_gates"], "approval gate row must be created for high-risk intent"
        assert captured["approval_gate_attaches"], "approval gate must be linked to staged typed action"
        assert captured["finalized"], "session should finalize as partial awaiting approval"
        fin = captured["finalized"][0]
        assert fin["status"] == "partial"
        assert fin["outcome"].get("result") == "awaiting_approval"
        assert fin["outcome"].get("approval_gate_id") == "gate-approve-1"
        step_pairs = {(step, status) for (step, status, _kwargs) in captured["steps"]}
        assert ("safety_gate", "completed") in step_pairs
        assert ("execute_intent", "queued") in step_pairs
        assert captured["gog_called"] is False
        edit_rows = [row for row in captured["messages"] if row.get("kind") == "edit"]
        assert edit_rows, "approval prompt should edit active message"
        reply_markup = edit_rows[-1].get("reply_markup") or {}
        kb_rows = list(reply_markup.get("inline_keyboard") or [])
        assert kb_rows and kb_rows[0] and "act:act-approve-1" in str(kb_rows[0][0].get("callback_data") or "")
        _pass("v1.20 free-text high-risk approval gate behavior")
    finally:
        ir.create_execution_session = orig_create_session
        ir.mark_execution_session_running = orig_mark_running
        ir.mark_execution_step_status = orig_mark_step
        ir.finalize_execution_session = orig_finalize
        ir.append_execution_event = orig_append
        ir.create_action = orig_create_action
        ir.create_approval_gate = orig_create_gate
        ir.attach_approval_gate_action = orig_attach_gate
        ir.mark_approval_gate_decision = orig_mark_gate
        ir.gog_scout = orig_gog


def test_approved_action_executes_and_finalizes_parent_session() -> None:
    _install_psycopg2_stub()
    _install_httpx_stub()
    import app.intent_runtime as ir

    captured: dict[str, object] = {"steps": [], "finalized": [], "messages": [], "gate_decisions": []}

    class _FakeTG:
        async def send_message(self, chat_id: int, text: str, parse_mode: str | None = None, reply_markup=None):
            captured["messages"].append({"kind": "send", "text": str(text)})
            return {"ok": True, "message_id": 51}

        async def edit_message_text(
            self,
            chat_id: int,
            message_id: int,
            text: str,
            parse_mode: str | None = None,
            reply_markup=None,
            **kwargs,
        ):
            captured["messages"].append({"kind": "edit", "text": str(text), "parse_mode": parse_mode})
            return {"ok": True}

    orig_mark_running = ir.mark_execution_session_running
    orig_mark_step = ir.mark_execution_step_status
    orig_finalize = ir.finalize_execution_session
    orig_append = ir.append_execution_event
    orig_mark_gate = ir.mark_approval_gate_decision
    orig_gog = ir.gog_scout
    orig_build_ui = ir.build_dynamic_ui

    try:
        ir.mark_execution_session_running = lambda session_id: None
        ir.mark_execution_step_status = (
            lambda session_id, step_key, status, **kwargs: captured["steps"].append((step_key, status, dict(kwargs)))
        )
        ir.finalize_execution_session = (
            lambda session_id, status, outcome=None, last_error=None: captured["finalized"].append(
                {"session_id": session_id, "status": status, "outcome": dict(outcome or {}), "last_error": last_error}
            )
        )
        ir.append_execution_event = lambda *args, **kwargs: None
        ir.mark_approval_gate_decision = (
            lambda approval_gate_id, **kwargs: captured["gate_decisions"].append(
                {"approval_gate_id": str(approval_gate_id), **dict(kwargs)}
            )
        )
        ir.build_dynamic_ui = lambda report, prompt, save_ctx=None: {"inline_keyboard": []}

        async def _fake_gog(*args, **kwargs):
            return "Approved execution done."

        ir.gog_scout = _fake_gog

        async def _run() -> None:
            res = await ir.execute_approved_intent_action(
                tg=_FakeTG(),
                chat_id=99,
                tenant_name="tenant_demo",
                tenant_cfg={},
                action_payload={
                    "session_id": "sess-highrisk-1",
                    "approval_gate_id": "gate-approve-1",
                    "intent_text": "Please pay this invoice now",
                    "prompt": "EXECUTE: Do the approved action now.",
                },
                safe_err=lambda e: str(e),
            )
            assert bool(res.get("ok")) is True
            assert str(res.get("status")) == "completed"

        asyncio.run(_run())

        step_pairs = {(step, status) for (step, status, _kwargs) in captured["steps"]}
        assert ("safety_gate", "completed") in step_pairs
        assert ("execute_intent", "completed") in step_pairs
        assert ("render_reply", "completed") in step_pairs
        assert captured["gate_decisions"], "approval gate should be marked approved on callback resume"
        assert captured["gate_decisions"][0]["approval_gate_id"] == "gate-approve-1"
        assert captured["gate_decisions"][0]["decision_status"] == "approved"
        assert captured["finalized"], "parent session should finalize completed after approval"
        assert captured["finalized"][0]["status"] == "completed"
        assert "approval_mode" in (captured["finalized"][0]["outcome"] or {})
        _pass("v1.20 approved callback resumes free-text session behavior")
    finally:
        ir.mark_execution_session_running = orig_mark_running
        ir.mark_execution_step_status = orig_mark_step
        ir.finalize_execution_session = orig_finalize
        ir.append_execution_event = orig_append
        ir.mark_approval_gate_decision = orig_mark_gate
        ir.gog_scout = orig_gog
        ir.build_dynamic_ui = orig_build_ui


if __name__ == "__main__":
    test_free_text_high_risk_stages_blocking_approval_gate()
    test_approved_action_executes_and_finalizes_parent_session()
