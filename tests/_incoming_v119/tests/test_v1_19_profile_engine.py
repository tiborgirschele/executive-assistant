
from app.intelligence.profile import build_profile_context

def test_v119_profile_contains_confidence_layer():
    ctx = build_profile_context(
        tenant="ea_bot",
        person_id="tibor",
        runtime_confidence_note="Runtime auto-recovered recently.",
        mode="standard",
        location_hint="Vienna",
    )
    assert ctx.situational.location_hint == "Vienna"
    assert ctx.confidence.state == "degraded"
    assert ctx.confidence.score < 1.0
