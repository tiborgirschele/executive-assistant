
from app.intelligence.profile import build_profile_context
from app.intelligence.dossiers import build_trip_dossier
from app.intelligence.future_situations import build_future_situations
from app.intelligence.readiness import build_readiness_dossier
from app.intelligence.critical_lane import build_critical_actions

def test_readiness_becomes_critical_for_high_value_risky_trip(sample_trip_inputs):
    mails, calendar_events = sample_trip_inputs
    profile = build_profile_context(tenant="ea_bot", person_id="tibor")
    dossier = build_trip_dossier(mails=mails, calendar_events=calendar_events)
    situations = build_future_situations(profile=profile, dossiers=[dossier], calendar_events=calendar_events)
    readiness = build_readiness_dossier(profile=profile, dossiers=[dossier], future_situations=situations)
    critical = build_critical_actions(profile, [dossier])
    assert readiness.status in {"critical", "watch"}
    assert critical.actions
    assert critical.exposure_score > 0
    assert critical.decision_window_score > 0
