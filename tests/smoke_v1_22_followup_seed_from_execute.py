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


def _install_optional_runtime_stubs() -> None:
    if "httpx" not in sys.modules:
        fake_httpx = types.ModuleType("httpx")

        class _DummyAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

        fake_httpx.AsyncClient = _DummyAsyncClient
        sys.modules["httpx"] = fake_httpx


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_followup_seed_wiring_presence() -> None:
    src = (ROOT / "ea/app/intent_runtime.py").read_text(encoding="utf-8")
    assert "_FOLLOWUP_ARTIFACT_TYPES" in src
    assert "def _seed_execution_followups(" in src
    assert '"followup_ids": followup_ids' in src
    assert "output_refs=render_output_refs" in src
    _pass("v1.22 followup seed wiring presence")


def test_followup_seed_behavior() -> None:
    _install_psycopg2_stub()
    _install_optional_runtime_stubs()
    import app.intent_runtime as runtime

    upsert_calls: list[dict[str, object]] = []
    followup_calls: list[dict[str, object]] = []

    orig_upsert = runtime._upsert_commitment
    orig_followup = runtime._create_followup
    runtime._upsert_commitment = lambda **kwargs: upsert_calls.append(dict(kwargs or {})) or True
    runtime._create_followup = lambda **kwargs: followup_calls.append(dict(kwargs or {})) or "fol-100"
    try:
        ids = runtime._seed_execution_followups(
            tenant_key="chat_100284",
            session_id="sess-xyz-123",
            intent_spec={"objective": "Review options", "domain": "travel"},
            execute_meta={"output_artifact_type": "travel_decision_pack", "task_type": "travel_rescue"},
            artifact_id="art-200",
            rendered_text="<b>Option A</b> with reroute",
        )
        ignored = runtime._seed_execution_followups(
            tenant_key="chat_100284",
            session_id="sess-xyz-123",
            intent_spec={"objective": "Review options", "domain": "travel"},
            execute_meta={"output_artifact_type": "chat_response", "task_type": "free_text_response"},
            artifact_id="art-201",
            rendered_text="plain",
        )
    finally:
        runtime._upsert_commitment = orig_upsert
        runtime._create_followup = orig_followup

    assert ids == ["fol-100"]
    assert ignored == []
    assert upsert_calls, "expected commitment upsert from followup seed"
    assert followup_calls, "expected followup create call"
    assert str(followup_calls[0].get("artifact_id") or "") == "art-200"
    _pass("v1.22 followup seed behavior")


if __name__ == "__main__":
    test_followup_seed_wiring_presence()
    test_followup_seed_behavior()
