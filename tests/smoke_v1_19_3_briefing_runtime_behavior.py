from __future__ import annotations

import asyncio
import json
import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
for path in (str(ROOT), str(EA_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def _ensure_runtime_stubs() -> None:
    if "httpx" not in sys.modules:
        class _DummyResponse:
            def __init__(self):
                self.text = ""
                self.content = b""

            def json(self):
                return {"ok": True, "result": {}}

        class _DummyAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def post(self, *args, **kwargs):
                return _DummyResponse()

            async def get(self, *args, **kwargs):
                return _DummyResponse()

        sys.modules["httpx"] = SimpleNamespace(AsyncClient=_DummyAsyncClient)

    if "psycopg2" not in sys.modules:
        class _DummyCursor:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def execute(self, *args, **kwargs):
                return None

            def fetchone(self):
                return None

            def fetchall(self):
                return []

        class _DummyConnection:
            def cursor(self, *args, **kwargs):
                return _DummyCursor()

            def commit(self):
                return None

        class _DummyThreadedConnectionPool:
            def __init__(self, *args, **kwargs):
                pass

            def getconn(self):
                return _DummyConnection()

            def putconn(self, conn):
                return None

        pool_mod = SimpleNamespace(ThreadedConnectionPool=_DummyThreadedConnectionPool)
        extras_mod = SimpleNamespace(RealDictCursor=object)
        psycopg2_mod = SimpleNamespace(pool=pool_mod, extras=extras_mod)
        sys.modules["psycopg2"] = psycopg2_mod
        sys.modules["psycopg2.pool"] = pool_mod
        sys.modules["psycopg2.extras"] = extras_mod


def test_raw_briefing_runtime_path_promotes_critical_action_without_internal_leak() -> None:
    _ensure_runtime_stubs()
    import app.briefings as brief
    from app.intelligence.source_acquisition import SourceAcquisitionResult

    original_collect = brief.collect_briefing_sources
    original_call_llm = brief.call_llm
    original_confidence_note = brief._runtime_confidence_note
    original_build_critical = brief.build_critical_actions
    original_build_readiness = brief.build_readiness_dossier
    original_build_prep = brief.build_preparation_plan
    original_build_epics = brief.build_epics_from_dossiers
    original_rank_epics = brief.rank_epics
    original_load_epics = brief.load_epic_snapshot
    original_save_epics = brief.save_epic_snapshot
    original_epic_deltas = brief.summarize_epic_deltas
    original_avomap = brief._avomap_prepare_card
    original_to_thread = brief.asyncio.to_thread

    async def _fake_collect(**kwargs):
        return SourceAcquisitionResult(
            mails=[
                {
                    "sender": "Billing",
                    "subject": "Invoice due today",
                    "snippet": "Action required",
                }
            ],
            calendar_events=[
                {
                    "summary": "Board Meeting",
                    "start": {"dateTime": "2026-03-05T10:00:00+01:00"},
                    "end": {"dateTime": "2026-03-05T11:00:00+01:00"},
                }
            ],
            accounts=["tibor@example.com"],
            diagnostics=["🔑 LLM Gateway: ✅ configured."],
        )

    async def _fake_call_llm(prompt, *args, **kwargs):
        return json.dumps(
            {
                "emails": [
                    {
                        "sender": "Billing",
                        "subject": "Invoice due today",
                        "churchill_action": "Assign owner before noon",
                        "action_button": "Assign owner",
                    }
                ],
                "calendar_summary": "Today: Board Meeting at 10:00",
            },
            ensure_ascii=False,
        )

    async def _fake_avomap_prepare(**kwargs):
        return "", {"status": "not_ready"}

    async def _inline_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    try:
        brief.collect_briefing_sources = _fake_collect
        brief.call_llm = _fake_call_llm
        brief.asyncio.to_thread = _inline_to_thread
        brief._runtime_confidence_note = lambda: "runtime recovered recently"
        brief.build_critical_actions = lambda *args, **kwargs: SimpleNamespace(
            actions=("Finance commitment deadline closes today; assign owner now.",),
            evidence=("invoice thread",),
            exposure_score=86,
            decision_window_score=81,
        )
        brief.build_readiness_dossier = lambda *args, **kwargs: SimpleNamespace(
            status="critical",
            score=42,
            blockers=("Owner missing for payment",),
            watch_items=(),
        )
        brief.build_preparation_plan = lambda *args, **kwargs: SimpleNamespace(
            actions=("Assign owner and stage response",),
            confidence_note="runtime healthy",
        )
        brief.build_epics_from_dossiers = lambda *args, **kwargs: []
        brief.rank_epics = lambda *args, **kwargs: []
        brief.load_epic_snapshot = lambda *args, **kwargs: []
        brief.save_epic_snapshot = lambda *args, **kwargs: None
        brief.summarize_epic_deltas = lambda *args, **kwargs: []
        brief._avomap_prepare_card = _fake_avomap_prepare

        result = asyncio.run(
            brief._raw_build_briefing_for_tenant(
                {
                    "openclaw_container": "openclaw",
                    "google_account": "tibor@example.com",
                    "key": "chat_100284",
                }
            )
        )

        assert isinstance(result, dict)
        text = str(result.get("text") or "")
        assert "<b>Immediate Action:</b>" in text
        assert "Finance commitment deadline closes today" in text
        assert "⚙️ Diagnostics" not in text
        assert "No critical items require your immediate attention." not in text
        assert "LLM Gateway:" not in text
    finally:
        brief.collect_briefing_sources = original_collect
        brief.call_llm = original_call_llm
        brief._runtime_confidence_note = original_confidence_note
        brief.build_critical_actions = original_build_critical
        brief.build_readiness_dossier = original_build_readiness
        brief.build_preparation_plan = original_build_prep
        brief.build_epics_from_dossiers = original_build_epics
        brief.rank_epics = original_rank_epics
        brief.load_epic_snapshot = original_load_epics
        brief.save_epic_snapshot = original_save_epics
        brief.summarize_epic_deltas = original_epic_deltas
        brief._avomap_prepare_card = original_avomap
        brief.asyncio.to_thread = original_to_thread

    _pass("v1.19.3 briefing runtime compose behavior")


def test_briefing_wrapper_sanitizes_toxic_payload() -> None:
    _ensure_runtime_stubs()
    import app.briefings as brief

    original_raw = brief._raw_build_briefing_for_tenant

    async def _fake_raw(*args, **kwargs):
        return {
            "text": '{"statusCode":500,"message":"Something went wrong","component_name":"llm gateway"}',
            "options": [],
            "dynamic_buttons": [],
        }

    try:
        brief._raw_build_briefing_for_tenant = _fake_raw
        result = asyncio.run(brief.build_briefing_for_tenant({"key": "chat_100284"}))
        text = str(result.get("text") or "")
        lowered = text.lower()
        assert "statuscode" not in lowered
        assert "llm gateway" not in lowered
        assert (
            "delivered in simplified mode today" in lowered
            or "preparing your briefing in safe mode" in lowered
        )
    finally:
        brief._raw_build_briefing_for_tenant = original_raw

    _pass("v1.19.3 wrapper toxic-payload sanitization")


if __name__ == "__main__":
    test_raw_briefing_runtime_path_promotes_critical_action_without_internal_leak()
    test_briefing_wrapper_sanitizes_toxic_payload()
