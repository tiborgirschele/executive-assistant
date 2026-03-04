
from app.intelligence.profile import build_profile_context

def test_profile_context_has_confidence_and_defaults():
    ctx = build_profile_context(tenant="ea_bot", person_id="tibor")
    assert ctx.tenant == "ea_bot"
    assert ctx.person_id == "tibor"
    assert ctx.confidence.state in {"healthy", "degraded"}
    assert ctx.stable.noise_suppression_mode in {"aggressive", "normal", "light"}
