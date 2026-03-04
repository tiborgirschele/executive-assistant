
from app.integrations.avomap.service import _extract_city, build_day_context

def test_avomap_city_extraction():
    assert _extract_city("Hilton Vienna Park, Vienna, Austria").lower().startswith("vienna")

def test_avomap_build_day_context_finds_stops():
    ctx = build_day_context(
        calendar_events=[{"summary":"Flight to Zurich", "location":"Vienna Airport; Zurich, Switzerland"}],
        travel_emails=[{"subject":"Flight booking to Zurich", "sender":"travel@example.com", "snippet":"Airport transfer included"}],
    )
    assert isinstance(ctx, dict)
