
from app.telegram.safety import (
    SAFE_PLACEHOLDER_COPY,
    SAFE_SIMPLIFIED_COPY,
    detect_forbidden_pattern,
    sanitize_telegram_text,
    install_telegram_safety,
)

def test_json_and_provider_trace_are_sanitized():
    raw = '{"statusCode":400,"message":"invalid template id"}'
    assert detect_forbidden_pattern(raw) is not None
    assert sanitize_telegram_text(raw) == SAFE_SIMPLIFIED_COPY
    assert sanitize_telegram_text(raw, placeholder=True) == SAFE_PLACEHOLDER_COPY

def test_internal_identifier_is_sanitized():
    raw = "OODA Diagnostic / Mum Brain / LLM Gateway / account_id=123"
    assert sanitize_telegram_text(raw) == SAFE_SIMPLIFIED_COPY

class _DummyTG:
    def __init__(self):
        self.sent = None
    async def send_message(self, chat_id, text, **kwargs):
        self.sent = text
        return {"ok": True}

def test_install_telegram_safety_wraps_send_message():
    tg = _DummyTG()
    patched = install_telegram_safety(tg)
    assert "send_message" in patched
