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


def test_brief_command_session_lifecycle_behavior() -> None:
    _install_psycopg2_stub()
    _install_httpx_stub()

    import app.brief_runtime as br

    captured: dict[str, object] = {
        "sessions": [],
        "steps": [],
        "finalized": [],
        "messages": [],
    }

    class _FakeTG:
        async def edit_message_text(self, chat_id: int, message_id: int, text: str, parse_mode=None, **kwargs):
            captured["messages"].append(
                {
                    "chat_id": int(chat_id),
                    "message_id": int(message_id),
                    "text": str(text),
                    "parse_mode": parse_mode,
                    "kwargs": dict(kwargs),
                }
            )
            return {"ok": True}

        async def delete_message(self, *args, **kwargs):
            return {"ok": True}

    orig_build = br.build_briefing_for_tenant
    orig_try_tpl = br._try_template_render_outbox
    orig_schedule = br._schedule_followups
    orig_create_delivery = br.create_briefing_delivery_session
    orig_activate_delivery = br.activate_briefing_delivery_session
    orig_to_thread = br.asyncio.to_thread

    orig_compile = br.compile_intent_spec
    orig_create = br.create_execution_session
    orig_running = br.mark_execution_session_running
    orig_step = br.mark_execution_step_status
    orig_finalize = br.finalize_execution_session

    try:
        async def _fake_build(tenant_cfg, status_cb=None):
            if status_cb:
                await status_cb("▶️ building")
            return {"text": "🎩 Brief ready", "options": ["Follow up"], "dynamic_buttons": []}

        async def _fake_try_tpl(**kwargs):
            return False

        async def _fake_schedule(**kwargs):
            return None

        br.build_briefing_for_tenant = _fake_build
        br._try_template_render_outbox = _fake_try_tpl
        br._schedule_followups = _fake_schedule
        br.create_briefing_delivery_session = lambda chat_id, status="active": 101
        br.activate_briefing_delivery_session = lambda session_id: None
        async def _fake_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)
        br.asyncio.to_thread = _fake_to_thread

        br.compile_intent_spec = lambda **kwargs: {"intent_type": "command", "objective": "Handle /brief"}
        br.create_execution_session = lambda **kwargs: captured["sessions"].append(dict(kwargs)) or "sess-brief-1"
        br.mark_execution_session_running = lambda session_id: None
        br.mark_execution_step_status = (
            lambda session_id, step_key, status, **kwargs: captured["steps"].append((step_key, status, dict(kwargs)))
        )
        br.finalize_execution_session = (
            lambda session_id, status, outcome=None, last_error=None: captured["finalized"].append(
                {
                    "session_id": session_id,
                    "status": status,
                    "outcome": dict(outcome or {}),
                    "last_error": last_error,
                }
            )
        )

        async def _run() -> None:
            await br.run_brief_command(
                tg=_FakeTG(),
                chat_id=555,
                tenant_name="tenant_demo",
                tenant_cfg={"key": "tenant_demo"},
                init_message_id=77,
                save_ctx=lambda s: "ctx-1",
                clean_html=lambda s: str(s),
                send_newspaper_pdf=lambda *args, **kwargs: asyncio.sleep(0),
                safe_task=lambda _name, aw: aw,
                incident_ref=lambda _prefix: "BRIEF-REF-1",
            )

        asyncio.run(_run())

        assert captured["sessions"], "brief command should create execution session"
        sess = captured["sessions"][0]
        assert sess.get("source") == "slash_command_brief"
        assert captured["finalized"], "brief command should finalize execution session"
        fin = captured["finalized"][0]
        assert fin["status"] == "completed"
        assert fin["outcome"].get("command") == "/brief"
        step_pairs = {(step, status) for (step, status, _kwargs) in captured["steps"]}
        assert ("compile_intent", "completed") in step_pairs
        assert ("execute_intent", "running") in step_pairs
        assert ("execute_intent", "completed") in step_pairs
        assert ("render_reply", "completed") in step_pairs
        assert ("persist_result", "completed") in step_pairs
        _pass("v1.20 brief command session lifecycle")
    finally:
        br.build_briefing_for_tenant = orig_build
        br._try_template_render_outbox = orig_try_tpl
        br._schedule_followups = orig_schedule
        br.create_briefing_delivery_session = orig_create_delivery
        br.activate_briefing_delivery_session = orig_activate_delivery
        br.asyncio.to_thread = orig_to_thread

        br.compile_intent_spec = orig_compile
        br.create_execution_session = orig_create
        br.mark_execution_session_running = orig_running
        br.mark_execution_step_status = orig_step
        br.finalize_execution_session = orig_finalize


if __name__ == "__main__":
    test_brief_command_session_lifecycle_behavior()
