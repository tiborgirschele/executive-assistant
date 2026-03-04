
from app.intelligence.profile import build_profile_context
from app.intelligence.dossiers import build_trip_dossier
from app.intelligence.critical_lane import build_critical_actions
from app.intelligence.modes import select_briefing_mode

def test_v119_low_confidence_mode_for_degraded_runtime(sample_trip_inputs):
    mails, calendar_events = sample_trip_inputs
    profile = build_profile_context(
        tenant="ea_bot",
        person_id="tibor",
        runtime_confidence_note="Runtime degraded after watchdog recovery.",
    )
    dossier = build_trip_dossier(mails=mails, calendar_events=calendar_events)
    critical = build_critical_actions(profile, [dossier])
    mode = select_briefing_mode(profile, [dossier], critical)
    assert mode is not None
