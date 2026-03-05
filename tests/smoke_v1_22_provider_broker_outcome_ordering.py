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


def test_provider_broker_outcome_ordering_behavior() -> None:
    _install_psycopg2_stub()
    import app.planner.provider_broker as broker

    orig_recent = broker.recent_provider_adjustments
    orig_perf = broker.recent_provider_performance
    broker.recent_provider_adjustments = lambda **kwargs: {
        "oneair": -20,
        "avomap": 6,
        "browseract": 0,
    }
    broker.recent_provider_performance = lambda **kwargs: {
        "oneair": {"success_adjustment": -8, "latency_adjustment": -4, "sample_count": 9},
        "avomap": {"success_adjustment": 4, "latency_adjustment": 2, "sample_count": 9},
    }
    try:
        ranked = broker.rank_task_capabilities(
            task_type="travel_rescue",
            candidates=["oneair", "avomap", "browseract"],
            preferred=None,
        )
    finally:
        broker.recent_provider_adjustments = orig_recent
        broker.recent_provider_performance = orig_perf

    assert ranked and str(ranked[0].get("capability") or "") == "avomap"
    top_reasons = list(ranked[0].get("reasons") or [])
    assert "recent_outcome:+6" in top_reasons
    assert "recent_success:+4" in top_reasons
    assert "recent_latency:+2" in top_reasons

    oneair_row = next((row for row in ranked if str(row.get("capability") or "") == "oneair"), {})
    oneair_reasons = list(oneair_row.get("reasons") or [])
    assert "recent_outcome:-20" in oneair_reasons
    assert "recent_success:-8" in oneair_reasons
    assert "recent_latency:-4" in oneair_reasons

    _pass("v1.22 provider broker outcome ordering")


if __name__ == "__main__":
    test_provider_broker_outcome_ordering_behavior()
