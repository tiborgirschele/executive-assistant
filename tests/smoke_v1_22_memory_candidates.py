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
        self.execute_calls: list[tuple[str, object]] = []
        self.fetchone_calls: list[tuple[str, object]] = []
        self.fetchall_calls: list[tuple[str, object]] = []

    def execute(self, query: str, vars=None) -> None:
        self.execute_calls.append((str(query), vars))

    def fetchone(self, query: str, vars=None):
        self.fetchone_calls.append((str(query), vars))
        return {"memory_candidate_id": "mem-1"}

    def fetchall(self, query: str, vars=None):
        self.fetchall_calls.append((str(query), vars))
        return [
            {
                "memory_candidate_id": "mem-1",
                "concept": "travel",
                "candidate_fact": "Trip has high exposure",
                "review_status": "approved",
            }
        ]


def test_memory_candidate_contract_presence() -> None:
    db_src = (ROOT / "ea/app/db.py").read_text(encoding="utf-8")
    module_src = (ROOT / "ea/app/planner/memory_candidates.py").read_text(encoding="utf-8")
    migration = ROOT / "ea/schema/20260305_v1_22_memory_candidates.sql"
    assert "CREATE TABLE IF NOT EXISTS memory_candidates" in db_src
    assert "def emit_memory_candidate(" in module_src
    assert "def mark_memory_candidate_review(" in module_src
    assert "def list_memory_candidates(" in module_src
    assert migration.exists(), "missing memory-candidate migration"
    _pass("v1.22 memory-candidate contract presence")


def test_memory_candidate_behavior() -> None:
    _install_psycopg2_stub()
    import app.planner.memory_candidates as mc

    fake = _FakeDB()
    orig_get_db = mc._get_db
    mc._get_db = lambda: fake
    try:
        candidate_id = mc.emit_memory_candidate(
            tenant_key="chat_100284",
            source_session_id="sess-1",
            concept="travel",
            candidate_fact="Trip to Zurich is at risk",
            confidence=0.8,
            payload={"source": "session"},
        )
        ok = mc.mark_memory_candidate_review(
            memory_candidate_id=candidate_id,
            review_status="approved",
            reviewer="operator",
            review_note="looks good",
        )
        rows = mc.list_memory_candidates(tenant_key="chat_100284", review_status="approved", limit=5)
    finally:
        mc._get_db = orig_get_db

    assert candidate_id == "mem-1"
    assert ok is True
    assert rows and str(rows[0].get("memory_candidate_id") or "") == "mem-1"
    assert fake.fetchone_calls, "expected insert returning call"
    assert fake.execute_calls, "expected review update call"
    assert fake.fetchall_calls, "expected list query call"
    _pass("v1.22 memory-candidate behavior")


if __name__ == "__main__":
    test_memory_candidate_contract_presence()
    test_memory_candidate_behavior()
