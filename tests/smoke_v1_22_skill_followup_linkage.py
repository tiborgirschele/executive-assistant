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


def _install_optional_runtime_stubs() -> None:
    if "httpx" not in sys.modules:
        fake_httpx = types.ModuleType("httpx")

        class _DummyAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        fake_httpx.AsyncClient = _DummyAsyncClient
        sys.modules["httpx"] = fake_httpx


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_skill_followup_linkage_wiring() -> None:
    src = (ROOT / "ea/app/callback_commands.py").read_text(encoding="utf-8")
    assert "def _seed_skill_followups(" in src
    assert "_DEFERRED_SKILL_ARTIFACT_TYPES" in src
    assert "seed_followups_for_deferred_artifacts" in src
    assert "\"followup_ids\": followup_ids" in src
    assert "output_refs=action_output_refs" in src
    _pass("v1.22 skill followup linkage wiring")


def test_skill_followup_linkage_behavior() -> None:
    _install_psycopg2_stub()
    _install_optional_runtime_stubs()
    import app.callback_commands as cb

    captured = {
        "steps": [],
        "finalized": [],
        "events": [],
        "messages": [],
        "artifacts": [],
        "followups": [],
    }

    class _FakeTG:
        async def send_message(self, chat_id: int, text: str, parse_mode: str | None = None, reply_markup=None):
            captured["messages"].append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
            return {"ok": True, "message_id": 1}

    orig_create_session = cb.create_execution_session
    orig_mark_running = cb.mark_execution_session_running
    orig_mark_step = cb.mark_execution_step_status
    orig_finalize = cb.finalize_execution_session
    orig_append_event = cb.append_execution_event
    orig_execute = cb.execute_typed_action
    orig_seed = cb.seed_followups_for_deferred_artifacts

    cb.create_execution_session = lambda **kwargs: "sess-skill-followup-1"
    cb.mark_execution_session_running = lambda session_id: None
    cb.mark_execution_step_status = (
        lambda session_id, step_key, status, **kwargs: captured["steps"].append((step_key, status, dict(kwargs or {})))
    )
    cb.finalize_execution_session = (
        lambda session_id, status, outcome=None, last_error=None: captured["finalized"].append(
            {"session_id": session_id, "status": status, "outcome": dict(outcome or {}), "last_error": last_error}
        )
    )
    cb.append_execution_event = lambda session_id, **kwargs: captured["events"].append(dict(kwargs or {}))
    cb.execute_typed_action = lambda **kwargs: {
        "text": "✅ Skill action executed.",
        "result": {
            "ok": True,
            "status": "executed",
            "artifacts": [{"artifact_type": "travel_decision_pack", "preview": "Route decision options"}],
        },
    }
    cb.seed_followups_for_deferred_artifacts = lambda **kwargs: {
        "followup_ids": ["fol-skill-1"],
        "output_refs": ["artifact:art-skill-1", "followup:fol-skill-1"],
        "commitment_key": "skill:trip_context_pack:chat_100284:sess-skill-fo",
    }

    try:
        asyncio.run(
            cb._execute_typed_action_callback(
                tg=_FakeTG(),
                chat_id=1001,
                tenant_name="chat_100284",
                tenant_cfg={},
                action_row={"action_type": "skill:trip_context_pack", "payload_json": {"operation": "generate"}},
            )
        )
    finally:
        cb.create_execution_session = orig_create_session
        cb.mark_execution_session_running = orig_mark_running
        cb.mark_execution_step_status = orig_mark_step
        cb.finalize_execution_session = orig_finalize
        cb.append_execution_event = orig_append_event
        cb.execute_typed_action = orig_execute
        cb.seed_followups_for_deferred_artifacts = orig_seed

    assert captured["finalized"], "expected finalized session"
    outcome = dict(captured["finalized"][0].get("outcome") or {})
    assert "fol-skill-1" in list(outcome.get("followup_ids") or [])

    execute_rows = [row for row in captured["steps"] if row[0] == "execute_intent" and row[1] == "completed"]
    assert execute_rows
    execute_kwargs = dict(execute_rows[0][2] or {})
    assert "followup:fol-skill-1" in list(execute_kwargs.get("output_refs") or [])

    _pass("v1.22 skill followup linkage behavior")


if __name__ == "__main__":
    test_skill_followup_linkage_wiring()
    test_skill_followup_linkage_behavior()
