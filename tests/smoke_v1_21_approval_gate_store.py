from __future__ import annotations

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


class _FakeDB:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def execute(self, query: str, vars=None) -> None:
        self.calls.append((str(query), vars))


def test_approval_gate_schema_contracts_present() -> None:
    db_src = (ROOT / "ea/app/db.py").read_text(encoding="utf-8")
    store_src = (ROOT / "ea/app/execution/session_store.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS approval_gates" in db_src
    assert "ADD COLUMN IF NOT EXISTS approval_gate_id" in db_src
    assert "def create_approval_gate(" in store_src
    assert "def attach_approval_gate_action(" in store_src
    assert "def mark_approval_gate_decision(" in store_src
    _pass("v1.21 approval-gate schema contracts")


def test_approval_gate_store_behavior_with_stubbed_db() -> None:
    _install_psycopg2_stub()
    import app.execution.session_store as store

    fake = _FakeDB()
    original_get_db = store.get_db
    store.get_db = lambda: fake
    try:
        gate_id = store.create_approval_gate(
            session_id="sess-approval-1",
            tenant="chat_100284",
            chat_id=123,
            approval_class="explicit_callback_required",
            decision_payload={"reason": "high_risk"},
        )
        assert str(gate_id or "").strip()
        store.attach_approval_gate_action(str(gate_id), "act-approve-1")
        store.mark_approval_gate_decision(
            str(gate_id),
            decision_status="approved",
            decision_payload={"source": "callback"},
        )
    finally:
        store.get_db = original_get_db

    joined = "\n".join(query for (query, _vars) in fake.calls)
    assert "INSERT INTO approval_gates" in joined
    assert "UPDATE approval_gates" in joined
    _pass("v1.21 approval-gate store behavior")


if __name__ == "__main__":
    test_approval_gate_schema_contracts_present()
    test_approval_gate_store_behavior_with_stubbed_db()
