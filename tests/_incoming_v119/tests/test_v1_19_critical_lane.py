
from app.intelligence.profile import build_profile_context
from app.intelligence.dossiers import build_trip_dossier
from app.intelligence.critical_lane import build_critical_actions

def test_v119_critical_lane_promotes_high_value_trip(sample_trip_inputs):
    mails, calendar_events = sample_trip_inputs
    profile = build_profile_context(
        tenant="ea_bot",
        person_id="tibor",
        runtime_confidence_note="Runtime auto-recovered recently."
    )
    dossier = build_trip_dossier(mails=mails, calendar_events=calendar_events)
    critical = build_critical_actions(profile, [dossier])
    joined = " ".join(critical.actions).lower()
    assert "trip" in joined or "travel" in joined
    assert critical.exposure_score > 0
