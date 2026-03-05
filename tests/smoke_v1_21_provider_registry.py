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


def test_provider_registry_module_presence() -> None:
    src = (ROOT / "ea/app/planner/provider_registry.py").read_text(encoding="utf-8")
    router_src = (ROOT / "ea/app/skills/capability_router.py").read_text(encoding="utf-8")
    assert "class ProviderContract" in src
    assert "def providers_for_task(" in src
    assert "def provider_or_raise(" in src
    assert "from app.planner.provider_registry import provider_or_raise, providers_for_task" in router_src
    _pass("v1.21 provider registry module presence")


def test_provider_registry_behavior() -> None:
    _install_psycopg2_stub()
    from app.planner.provider_registry import list_provider_contracts, provider_or_raise, providers_for_task

    travel = set(providers_for_task("travel_rescue"))
    assert {"oneair", "avomap"}.issubset(travel)

    oneair = provider_or_raise("oneair")
    assert oneair.key == "oneair"
    assert oneair.invocation_method == "api"
    assert oneair.budget_policy == "travel_sidecar_daily"

    rows = list_provider_contracts()
    assert rows and any(str(row.get("key")) == "browseract" for row in rows)
    _pass("v1.21 provider registry behavior")


if __name__ == "__main__":
    test_provider_registry_module_presence()
    test_provider_registry_behavior()
