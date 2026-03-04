
from app.intelligence.dossiers import build_trip_dossier

def test_v119_trip_dossier_builds_evidence_and_exposure(sample_trip_inputs):
    mails, calendar_events = sample_trip_inputs
    dossier = build_trip_dossier(mails=mails, calendar_events=calendar_events)
    assert dossier.evidence
    assert dossier.exposure_eur >= 15000
