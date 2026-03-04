from __future__ import annotations

import importlib
import pathlib
import sys
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
for path in (str(ROOT), str(EA_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def _import(name: str):
    return importlib.import_module(name)


def test_v119_module_presence() -> None:
    assert _import("app.intelligence.profile")
    assert _import("app.intelligence.dossiers")
    assert _import("app.intelligence.future_situations")
    assert _import("app.intelligence.readiness")
    assert _import("app.intelligence.critical_lane")
    assert _import("app.intelligence.preparation_planner")
    assert _import("app.intelligence.household_graph")
    assert _import("app.intelligence.modes")
    assert (ROOT / "tests/_incoming_v119/tests/test_v1_19_golden_journeys.py").exists()
    _pass("v1.19 care-intelligence module presence")


def test_v119_behavior_contracts() -> None:
    from app.intelligence.critical_lane import build_critical_actions
    from app.intelligence.dossiers import build_trip_dossier
    from app.intelligence.future_situations import build_future_situations
    from app.intelligence.modes import select_briefing_mode
    from app.intelligence.preparation_planner import build_preparation_plan
    from app.intelligence.profile import build_profile_context
    from app.intelligence.readiness import build_readiness_dossier

    future_start = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    mails = [
        {
            "subject": "Holiday booking confirmation - EUR 15,000",
            "from": "travel@example.com",
            "snippet": "Flight booking with layover in Tel Aviv. Rebooking terms attached.",
        }
    ]
    events = [
        {
            "summary": "Flight to Zurich",
            "location": "Vienna Airport; Tel Aviv Airport; Zurich, Switzerland",
            "start": {"dateTime": future_start},
            "end": {"dateTime": future_start},
            "_calendar": "primary",
        }
    ]

    profile = build_profile_context(
        tenant="ea_bot",
        person_id="tibor",
        runtime_confidence_note="Runtime degraded after watchdog recovery.",
    )
    dossier = build_trip_dossier(mails=mails, calendar_events=events)
    future = build_future_situations(profile=profile, dossiers=[dossier], calendar_events=events, horizon_hours=96)
    readiness = build_readiness_dossier(profile=profile, dossiers=[dossier], future_situations=future)
    critical = build_critical_actions(profile, [dossier])
    mode = select_briefing_mode(profile, [dossier], critical)
    plan = build_preparation_plan(profile=profile, readiness=readiness, epics=tuple())

    kinds = {s.kind for s in future}
    assert dossier.kind == "trip"
    assert dossier.exposure_eur >= 15000
    assert dossier.risk_hits
    assert "travel_window" in kinds
    assert "risk_intersection" in kinds
    assert readiness.status in {"critical", "watch"}
    assert critical.exposure_score > 0
    assert critical.decision_window_score > 0
    assert mode in {"low_confidence", "risk_mode", "travel_mode"}
    assert "wire transfer" not in str(plan).lower()
    _pass("v1.19 care-intelligence behavior contracts")


def test_incoming_pack_contracts() -> None:
    from tests.run_incoming_v119_pack import run_pack

    summary = run_pack()
    assert int(summary.get("failed", 1)) == 0, summary
    _pass("v1.19 incoming test-pack contracts")


if __name__ == "__main__":
    test_v119_module_presence()
    test_v119_behavior_contracts()
    test_incoming_pack_contracts()
