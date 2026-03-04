
from app.intelligence.profile import build_profile_context
from app.intelligence.dossiers import build_trip_dossier
from app.intelligence.future_situations import build_future_situations

def test_future_situations_include_travel_and_risk(sample_trip_inputs):
    mails, calendar_events = sample_trip_inputs
    profile = build_profile_context(tenant="ea_bot", person_id="tibor")
    dossier = build_trip_dossier(mails=mails, calendar_events=calendar_events)
    situations = build_future_situations(profile=profile, dossiers=[dossier], calendar_events=calendar_events)
    kinds = {s.kind for s in situations}
    assert "travel_window" in kinds
    assert "risk_intersection" in kinds
