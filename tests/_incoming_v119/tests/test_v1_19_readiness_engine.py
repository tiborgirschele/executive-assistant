
from app.intelligence.profile import build_profile_context
from app.intelligence.dossiers import build_trip_dossier
from app.intelligence.future_situations import build_future_situations
from app.intelligence.readiness import build_readiness_dossier

def test_v119_readiness_has_blockers_and_actions(sample_trip_inputs):
    mails, calendar_events = sample_trip_inputs
    profile = build_profile_context(tenant="ea_bot", person_id="tibor")
    dossier = build_trip_dossier(mails=mails, calendar_events=calendar_events)
    situations = build_future_situations(profile=profile, dossiers=[dossier], calendar_events=calendar_events)
    readiness = build_readiness_dossier(profile=profile, dossiers=[dossier], future_situations=situations)
    assert readiness.status in {"critical", "watch", "ready"}
    assert isinstance(readiness.suggested_actions, tuple)
