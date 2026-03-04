
from app.intelligence.dossiers import build_trip_dossier

def test_trip_dossier_detects_high_value_and_risk(sample_trip_inputs):
    mails, calendar_events = sample_trip_inputs
    dossier = build_trip_dossier(mails=mails, calendar_events=calendar_events)
    assert dossier.kind == "trip"
    assert dossier.signal_count >= 1
    assert dossier.exposure_eur >= 15000
    assert dossier.risk_hits
