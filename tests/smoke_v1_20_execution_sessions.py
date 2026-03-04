from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
for path in (str(ROOT), str(EA_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


class _FakeDB:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def execute(self, query: str, vars=None) -> None:
        self.calls.append((str(query), vars))


def test_execution_store_contract_wiring() -> None:
    store_src = (ROOT / "ea/app/execution/session_store.py").read_text(encoding="utf-8")
    db_src = (ROOT / "ea/app/db.py").read_text(encoding="utf-8")
    assert "def compile_intent_spec(" in store_src
    assert "def create_execution_session(" in store_src
    assert "def mark_execution_step_status(" in store_src
    assert "def finalize_execution_session(" in store_src
    assert "CREATE TABLE IF NOT EXISTS execution_sessions" in db_src
    assert "CREATE TABLE IF NOT EXISTS execution_steps" in db_src
    assert "CREATE TABLE IF NOT EXISTS execution_events" in db_src
    _pass("v1.20 execution store contract wiring")


def test_execution_store_behavior_with_stubbed_db() -> None:
    import types

    # Host smoke runs without postgres client deps; stub psycopg2 before import.
    if "psycopg2" not in sys.modules:
        fake_psycopg2 = types.ModuleType("psycopg2")
        fake_pool = types.ModuleType("psycopg2.pool")
        fake_extras = types.ModuleType("psycopg2.extras")

        class _ThreadedPool:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def getconn(self):
                raise RuntimeError("stubbed pool should not be used in host smoke")

            def putconn(self, _conn) -> None:
                return

        fake_pool.ThreadedConnectionPool = _ThreadedPool
        fake_extras.RealDictCursor = object
        fake_extras.Json = lambda payload: payload
        fake_psycopg2.pool = fake_pool
        fake_psycopg2.extras = fake_extras
        fake_psycopg2.connect = lambda *args, **kwargs: None
        sys.modules["psycopg2"] = fake_psycopg2
        sys.modules["psycopg2.pool"] = fake_pool
        sys.modules["psycopg2.extras"] = fake_extras

    import app.execution.session_store as store

    fake = _FakeDB()
    original_get_db = store.get_db
    store.get_db = lambda: fake
    try:
        intent = store.compile_intent_spec(
            text="Read https://example.com and summarize the project deadline risk.",
            tenant="chat_1001",
            chat_id=1001,
            has_url=True,
        )
        assert intent.get("intent_type") == "url_analysis"
        assert intent.get("domain") in {"project", "general"}
        plan = store.build_plan_steps(intent_spec=intent)
        assert any(str(step.get("step_key")) == "compile_intent" for step in plan)
        assert any(str(step.get("step_key")) == "gather_evidence" for step in plan)
        session_id = store.create_execution_session(
            tenant="chat_1001",
            chat_id=1001,
            intent_spec=intent,
            plan_steps=plan,
            source="telegram_free_text",
            correlation_id="chat_1001:1001:test",
        )
        assert session_id
        store.mark_execution_session_running(session_id)
        store.mark_execution_step_status(session_id, "gather_evidence", "completed", evidence={"url": "x"})
        store.append_execution_event(
            session_id,
            event_type="custom_event",
            message="ok",
            payload={"k": "v"},
        )
        store.finalize_execution_session(session_id, status="completed", outcome={"ok": True})
    finally:
        store.get_db = original_get_db

    joined_queries = "\n".join(call[0] for call in fake.calls)
    assert "INSERT INTO execution_sessions" in joined_queries
    assert "INSERT INTO execution_steps" in joined_queries
    assert "UPDATE execution_sessions" in joined_queries
    assert "UPDATE execution_steps" in joined_queries
    assert "INSERT INTO execution_events" in joined_queries
    _pass("v1.20 execution store behavior with stubbed db")


if __name__ == "__main__":
    test_execution_store_contract_wiring()
    test_execution_store_behavior_with_stubbed_db()
