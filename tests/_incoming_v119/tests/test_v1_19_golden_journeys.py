
from app.intelligence.profile import build_profile_context
from app.intelligence.dossiers import build_trip_dossier
from app.intelligence.future_situations import build_future_situations
from app.intelligence.readiness import build_readiness_dossier
from app.intelligence.critical_lane import build_critical_actions

def test_golden_trip_holiday_with_risk(sample_trip_inputs):
    mails, calendar_events = sample_trip_inputs
    profile = build_profile_context(
        tenant="ea_bot",
        person_id="tibor",
        runtime_confidence_note="Critical scan should stay cautious after runtime recovery.",
    )
    dossier = build_trip_dossier(mails=mails, calendar_events=calendar_events)
    future = build_future_situations(profile=profile, dossiers=[dossier], calendar_events=calendar_events)
    readiness = build_readiness_dossier(profile=profile, dossiers=[dossier], future_situations=future)
    critical = build_critical_actions(profile, [dossier])
    assert dossier.exposure_eur >= 15000
    assert dossier.risk_hits
    assert future
    assert readiness.status in {"critical", "watch"}
    assert critical.actions
