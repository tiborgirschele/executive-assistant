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


class _FakeDB:
    def __init__(self, fetchone_rows: list[dict | None]):
        self._rows = list(fetchone_rows)
        self.exec_calls: list[tuple[str, tuple | None]] = []
        self.fetchone_calls: list[tuple[str, tuple | None]] = []

    def fetchone(self, query: str, vars=None):
        self.fetchone_calls.append((str(query), vars))
        if not self._rows:
            return None
        return self._rows.pop(0)

    def execute(self, query: str, vars=None):
        self.exec_calls.append((str(query), vars))

    def commit(self):
        return None


def _install_execution_capture(module):
    captured: dict[str, object] = {
        "steps": [],
        "finalized": [],
        "events": [],
    }
    orig = {
        "create": module.create_execution_session,
        "running": module.mark_execution_session_running,
        "step": module.mark_execution_step_status,
        "finalize": module.finalize_execution_session,
        "event": module.append_execution_event,
    }
    module.create_execution_session = lambda **kwargs: "sess-ext-1"
    module.mark_execution_session_running = lambda session_id: None
    module.mark_execution_step_status = (
        lambda session_id, step_key, status, **kwargs: captured["steps"].append((step_key, status, dict(kwargs)))
    )
    module.finalize_execution_session = (
        lambda session_id, status, outcome=None, last_error=None: captured["finalized"].append(
            {
                "session_id": session_id,
                "status": status,
                "outcome": dict(outcome or {}),
                "last_error": last_error,
            }
        )
    )
    module.append_execution_event = (
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
    return captured, orig


def _restore_execution_capture(module, orig: dict[str, object]) -> None:
    module.create_execution_session = orig["create"]
    module.mark_execution_session_running = orig["running"]
    module.mark_execution_step_status = orig["step"]
    module.finalize_execution_session = orig["finalize"]
    module.append_execution_event = orig["event"]


def test_metasurvey_event_behavior_runtime() -> None:
    _install_psycopg2_stub()
    _install_httpx_stub()
    import app.intake.metasurvey_feedback as mf

    fake_db = _FakeDB(
        [
            {
                "tenant": "chat_12345",
                "payload_json": {
                    "hidden_fields": {"principal": "p1", "tenant": "chat_12345"},
                    "answers": {
                        "prioritize_topics": "travel",
                        "suppress_topics": "spam",
                        "publishers": "ft",
                        "depth": "short",
                    },
                },
            }
        ]
    )

    captured, orig_exec = _install_execution_capture(mf)
    orig_get_db = mf.get_db
    orig_pe = mf.PersonalizationEngine
    feedback_calls: list[dict[str, str]] = []

    class _FakePE:
        def record_feedback(self, **kwargs):
            feedback_calls.append({k: str(v) for k, v in kwargs.items()})

    try:
        mf.get_db = lambda: fake_db
        mf.PersonalizationEngine = _FakePE
        asyncio.run(mf.process_metasurvey_submission("evt-meta-1"))

        assert captured["finalized"], "metasurvey flow must finalize execution session"
        fin = captured["finalized"][0]
        assert fin["status"] == "completed"
        assert fin["outcome"].get("external_event_status") == "processed"
        assert feedback_calls, "metasurvey flow should apply personalization feedback"
        assert any("UPDATE external_events" in q and "status='processed'" in q for q, _ in fake_db.exec_calls)
        _pass("v1.20 metasurvey runtime behavior")
    finally:
        mf.get_db = orig_get_db
        mf.PersonalizationEngine = orig_pe
        _restore_execution_capture(mf, orig_exec)


def test_approvethis_event_behavior_runtime() -> None:
    _install_psycopg2_stub()
    _install_httpx_stub()
    import app.approvals.normalizer as normalizer

    fake_db = _FakeDB(
        [
            {
                "tenant": "chat_333",
                "payload_json": {"status": "approved", "metadata": {}},
            }
        ]
    )

    captured, orig_exec = _install_execution_capture(normalizer)
    orig_get_db = normalizer.get_db

    try:
        normalizer.get_db = lambda: fake_db
        asyncio.run(normalizer.process_approvethis_event("evt-approval-1"))

        assert captured["finalized"], "approvethis flow must finalize execution session"
        fin = captured["finalized"][0]
        assert fin["status"] == "completed"
        assert fin["outcome"].get("reason") == "missing_internal_ref"
        assert any("UPDATE external_events" in q and "status='discarded'" in q for q, _ in fake_db.exec_calls)
        _pass("v1.20 approvethis runtime behavior")
    finally:
        normalizer.get_db = orig_get_db
        _restore_execution_capture(normalizer, orig_exec)


def test_browseract_event_behavior_runtime() -> None:
    _install_psycopg2_stub()
    _install_httpx_stub()
    import app.intake.browseract as browseract

    fake_db = _FakeDB(
        [
            {
                "tenant": "chat_777",
                "event_type": "browseract.http_ingress_test",
                "payload_json": {"template_id": "tpl_42"},
            }
        ]
    )

    captured, orig_exec = _install_execution_capture(browseract)
    orig_get_db = browseract.get_db

    try:
        browseract.get_db = lambda: fake_db
        asyncio.run(browseract.process_browseract_event("evt-browser-1"))

        assert captured["finalized"], "browseract flow must finalize execution session"
        fin = captured["finalized"][0]
        assert fin["status"] == "completed"
        assert fin["outcome"].get("external_event_status") == "processed"
        assert bool(fin["outcome"].get("template_found")) is True
        assert any("template_registry" in q for q, _ in fake_db.exec_calls)
        assert any("UPDATE external_events" in q and "status='processed'" in q for q, _ in fake_db.exec_calls)
        _pass("v1.20 browseract runtime behavior")
    finally:
        browseract.get_db = orig_get_db
        _restore_execution_capture(browseract, orig_exec)


if __name__ == "__main__":
    test_metasurvey_event_behavior_runtime()
    test_approvethis_event_behavior_runtime()
    test_browseract_event_behavior_runtime()
