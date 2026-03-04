
from app.contracts.telegram import sanitize_incident_copy

def test_incident_copy_adds_correlation_ref_for_simplified_mode():
    out = sanitize_incident_copy(
        '{"statusCode":400,"message":"invalid template id"}',
        correlation_id="abc123",
        mode="simplified-first",
    )
    assert "ref: abc123" in out
    assert "invalid template id" not in out
