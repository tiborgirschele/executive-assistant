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
        self.fetchall_calls: list[tuple[str, object]] = []

    def execute(self, query: str, vars=None) -> None:
        self.execute_calls.append((str(query), vars))

    def fetchall(self, query: str, vars=None):
        self.fetchall_calls.append((str(query), vars))
        return [
            {"provider_key": "oneair", "score_delta": 3, "outcome_status": "success", "latency_ms": 12000, "source": "runtime"},
            {"provider_key": "oneair", "score_delta": 4, "outcome_status": "completed", "latency_ms": 14000, "source": "runtime"},
            {"provider_key": "avomap", "score_delta": -2, "outcome_status": "failed", "latency_ms": 92000, "source": "runtime"},
            {"provider_key": "oneair", "score_delta": 20, "outcome_status": "synthetic_preview", "latency_ms": 2000, "source": "synthetic_preview"},
        ]


def test_provider_outcome_module_presence() -> None:
    broker_src = (ROOT / "ea/app/planner/provider_broker.py").read_text(encoding="utf-8")
    outcome_src = (ROOT / "ea/app/planner/provider_outcomes.py").read_text(encoding="utf-8")
    db_src = (ROOT / "ea/app/db.py").read_text(encoding="utf-8")
    assert "recent_provider_adjustments" in broker_src
    assert "def record_provider_outcome(" in outcome_src
    assert "def recent_provider_adjustments(" in outcome_src
    assert "def recent_provider_performance(" in outcome_src
    assert "CREATE TABLE IF NOT EXISTS provider_outcomes" in db_src
    _pass("v1.21 provider-outcome module presence")


def test_provider_outcome_behavior() -> None:
    _install_psycopg2_stub()
    import app.planner.provider_outcomes as outcomes

    fake = _FakeDB()
    original_get_db = outcomes._get_db
    outcomes._get_db = lambda: fake
    try:
        outcomes.record_provider_outcome(
            tenant_key="chat_100284",
            provider_key="oneair",
            task_type="travel_rescue",
            outcome_status="success",
            score_delta=3,
            source="skill_runtime",
        )
        adjustments = outcomes.recent_provider_adjustments(task_type="travel_rescue", lookback_hours=24, limit=50)
        perf = outcomes.recent_provider_performance(task_type="travel_rescue", lookback_hours=24, limit=50)
    finally:
        outcomes._get_db = original_get_db

    assert fake.execute_calls, "expected provider outcome insert"
    assert fake.fetchall_calls, "expected provider outcome aggregation query"
    assert int(adjustments.get("oneair") or 0) == 7
    assert int(adjustments.get("avomap") or 0) == -2
    assert int((perf.get("oneair") or {}).get("score_adjustment") or 0) == 7
    assert int((perf.get("avomap") or {}).get("score_adjustment") or 0) == -2
    _pass("v1.21 provider-outcome behavior")


if __name__ == "__main__":
    test_provider_outcome_module_presence()
    test_provider_outcome_behavior()
