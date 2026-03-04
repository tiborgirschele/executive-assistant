
from app.intelligence.profile import build_profile_context
from app.intelligence.dossiers import build_trip_dossier
from app.intelligence.future_situations import build_future_situations

def test_v119_future_situation_carries_evidence(sample_trip_inputs):
    mails, calendar_events = sample_trip_inputs
    profile = build_profile_context(tenant="ea_bot", person_id="tibor")
    dossier = build_trip_dossier(mails=mails, calendar_events=calendar_events)
    situations = build_future_situations(profile=profile, dossiers=[dossier], calendar_events=calendar_events, horizon_hours=96)
    assert any(s.evidence for s in situations)
