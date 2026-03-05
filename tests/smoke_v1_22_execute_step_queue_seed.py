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


def test_execute_step_queue_seed_behavior() -> None:
    _install_psycopg2_stub()
    import app.planner.plan_store as store
    import app.planner.step_executor as step_exec

    orig_resolve = store.resolve_execute_step_metadata
    orig_select = store.select_queued_execute_step
    store.resolve_execute_step_metadata = lambda session_id, fallback=None: {
        "task_type": "travel_rescue",
        "output_artifact_type": "travel_decision_pack",
        "provider_candidates": ["oneair", "avomap"],
        "metadata_source": "ledger_execute_step",
        "metadata_provenance": ["ledger_evidence"],
    }
    store.select_queued_execute_step = lambda session_id: {
        "step_id": "step-exec-1",
        "step_order": 4,
        "step_key": "execute_intent",
        "step_kind": "execution",
        "status": "queued",
        "provider_key": "oneair",
        "output_refs_json": ["travel_decision_pack"],
    }

    marks: list[tuple[str, str, dict[str, object]]] = []
    events: list[dict[str, object]] = []

    def _mark_step(session_id: str, step_key: str, status: str, **kwargs) -> None:
        marks.append((str(step_key), str(status), dict(kwargs or {})))

    def _append_event(session_id: str, **kwargs) -> None:
        events.append(dict(kwargs or {}))

    async def _fake_reasoning(**kwargs):
        return "ok"

    async def _fake_ui(msg: str) -> None:
        return None

    try:
        out = asyncio.run(
            step_exec.execute_planned_reasoning_step(
                session_id="sess-exec-seed",
                plan_steps=[],
                intent_spec={},
                prompt="EXECUTE",
                container="openclaw-gateway",
                google_account="",
                ui_updater=_fake_ui,
                task_name="Intent: Free Text",
                mark_step=_mark_step,
                append_event=_append_event,
                run_reasoning_step_func=_fake_reasoning,
            )
        )
    finally:
        store.resolve_execute_step_metadata = orig_resolve
        store.select_queued_execute_step = orig_select

    assert str(out.get("execute_step_id") or "") == "step-exec-1"
    assert int(out.get("execute_step_order") or 0) == 4
    output_refs = list(out.get("output_refs") or [])
    assert "travel_decision_pack" in output_refs
    assert "execute_output:4:travel_decision_pack" in output_refs

    running_rows = [row for row in marks if row[0] == "execute_intent" and row[1] == "running"]
    completed_rows = [row for row in marks if row[0] == "execute_intent" and row[1] == "completed"]
    assert running_rows and completed_rows
    assert str(running_rows[0][2].get("step_id") or "") == "step-exec-1"

    completed_kwargs = dict(completed_rows[0][2] or {})
    assert str(completed_kwargs.get("step_id") or "") == "step-exec-1"
    assert "execute_output:4:travel_decision_pack" in list(completed_kwargs.get("output_refs") or [])

    done_events = [evt for evt in events if str(evt.get("event_type") or "") == "execute_intent_completed"]
    assert done_events
    payload = dict(done_events[0].get("payload") or {})
    assert str(payload.get("execute_step_id") or "") == "step-exec-1"
    assert "execute_output:4:travel_decision_pack" in list(payload.get("output_refs") or [])
    _pass("v1.22 execute-step queue seed behavior")


if __name__ == "__main__":
    test_execute_step_queue_seed_behavior()
