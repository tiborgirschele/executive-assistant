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


def test_typed_action_reference_guard_module_presence() -> None:
    src = (ROOT / "ea/app/actions.py").read_text(encoding="utf-8")
    assert "def _requires_session_reference(" in src
    assert "def _requires_approval_gate_reference(" in src
    _pass("v1.21 typed-action reference guard module presence")


def test_typed_action_reference_guard_behavior() -> None:
    _install_psycopg2_stub()
    import app.actions as actions

    fake = _FakeDB()
    orig_get_db = actions.get_db
    actions.get_db = lambda: fake
    try:
        blocked_skill = actions.create_action(
            tenant="tenant_demo",
            action_type="skill:prompt_compiler",
            payload={"operation": "compile"},
            days=1,
            session_id=None,
        )
        assert blocked_skill == ""

        allowed_skill = actions.create_action(
            tenant="tenant_demo",
            action_type="skill:prompt_compiler",
            payload={"operation": "compile"},
            days=1,
            session_id="sess-1",
        )
        assert str(allowed_skill).strip()

        blocked_intent = actions.create_action(
            tenant="tenant_demo",
            action_type="intent:approval_execute",
            payload={"prompt": "x"},
            days=1,
            session_id="sess-2",
            approval_gate_id=None,
        )
        assert blocked_intent == ""

        allowed_intent = actions.create_action(
            tenant="tenant_demo",
            action_type="intent:approval_execute",
            payload={"prompt": "x"},
            days=1,
            session_id="sess-2",
            approval_gate_id="gate-1",
        )
        assert str(allowed_intent).strip()
    finally:
        actions.get_db = orig_get_db

    inserts = [q for (q, _vars) in fake.calls if "INSERT INTO typed_actions" in q]
    assert len(inserts) == 2, "only reference-complete actions should persist"
    _pass("v1.21 typed-action reference guard behavior")


if __name__ == "__main__":
    test_typed_action_reference_guard_module_presence()
    test_typed_action_reference_guard_behavior()
