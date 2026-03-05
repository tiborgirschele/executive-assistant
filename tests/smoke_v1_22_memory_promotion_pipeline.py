from __future__ import annotations

import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
for path in (str(ROOT), str(EA_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


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


class _FakeDB:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, object]] = []
        self.session_rows: dict[str, dict[str, object]] = {}

    def execute(self, query: str, vars=None) -> None:
        self.execute_calls.append((str(query), vars))

    def fetchone(self, query: str, vars=None):
        if "FROM execution_sessions" in str(query or ""):
            key = str((vars or [None])[0] or "")
            return self.session_rows.get(key)
        return None


def test_finalize_emits_memory_candidate() -> None:
    _install_psycopg2_stub()
    import app.execution.session_store as store
    import app.planner.memory_candidates as mc

    fake_db = _FakeDB()
    fake_db.session_rows["sess-1"] = {
        "tenant": "chat_100284",
        "intent_type": "free_text",
        "objective": "Rebook Zurich trip with safer layover and preserve value",
        "intent_spec_json": {"task_type": "travel_rescue", "domain": "travel"},
    }

    captured: list[dict[str, object]] = []

    def _fake_emit(**kwargs):
        captured.append(dict(kwargs))
        return "mem-candidate-1"

    orig_get_db = store.get_db
    orig_emit = mc.emit_memory_candidate
    store.get_db = lambda: fake_db
    mc.emit_memory_candidate = _fake_emit
    try:
        store.finalize_execution_session("sess-1", status="completed", outcome={"result": "delivered"})
        store.finalize_execution_session("sess-1", status="failed", outcome={"result": "failed"}, last_error="boom")
    finally:
        store.get_db = orig_get_db
        mc.emit_memory_candidate = orig_emit

    assert captured, "expected memory candidate emission on completed finalize"
    first = captured[0]
    assert str(first.get("tenant_key") or "") == "chat_100284"
    assert str(first.get("source_session_id") or "") == "sess-1"
    assert str(first.get("concept") or "") == "travel_rescue"
    assert "rebook zurich trip" in str(first.get("candidate_fact") or "").lower()
    assert len(captured) == 1, "failed finalize should not emit memory candidate"
    _pass("v1.22 session-finalize memory emission")


def test_teable_sync_ingests_approved_candidates() -> None:
    _install_httpx_stub()
    _install_psycopg2_stub()
    import app.integrations.teable.sync_worker as sw
    import app.planner.memory_candidates as mc

    sample_rows = [
        {
            "memory_candidate_id": "mem-1",
            "tenant_key": "chat_100284",
            "concept": "travel_rescue",
            "candidate_fact": "Trip rebooking path is approved for review.",
            "confidence": 0.81,
            "sensitivity": "personal",
            "sharing_policy": "private",
            "review_status": "approved",
            "reviewer": "operator",
            "payload_json": {"source": "session_finalize"},
            "created_at": "2026-03-05T08:00:00+00:00",
            "reviewed_at": "2026-03-05T08:05:00+00:00",
        }
    ]

    orig_list = mc.list_memory_candidates_for_sync
    mc.list_memory_candidates_for_sync = lambda **kwargs: list(sample_rows)
    try:
        rows = sw.collect_approved_memory_candidate_rows(limit=10)
        fields = sw.build_memory_record_fields_from_candidate(rows[0])
        blocked = sw.build_memory_record_fields_from_candidate(
            {
                "memory_candidate_id": "mem-2",
                "concept": "dump",
                "candidate_fact": '{"role":"assistant","content":"traceback ... tool_call ..."}',
                "review_status": "approved",
            }
        )
    finally:
        mc.list_memory_candidates_for_sync = orig_list

    assert rows and str(rows[0].get("memory_candidate_id") or "") == "mem-1"
    assert isinstance(fields, dict)
    assert str(fields.get("Concept") or "") == "travel_rescue"
    assert str(fields.get("Source") or "") == "session_finalize"
    assert blocked is None
    _pass("v1.22 teable approved-candidate ingestion helpers")


if __name__ == "__main__":
    test_finalize_emits_memory_candidate()
    test_teable_sync_ingests_approved_candidates()
