from .client import safe_llm_call
from .trust_boundary import validate_model_output, wrap_untrusted_evidence

# Keep package import cycle-safe; the contract gateway imports submodules from
# this package (policy/trust_boundary), so resolve at call time.
DEFAULT_SYSTEM_PROMPT = "Du bist ein präziser Executive Assistant."


def ask_text(prompt: str, **kwargs):
    from app.contracts.llm_gateway import ask_text as _contract_ask_text

    return _contract_ask_text(prompt, **kwargs)

__all__ = [
    "safe_llm_call",
    "ask_text",
    "DEFAULT_SYSTEM_PROMPT",
    "validate_model_output",
    "wrap_untrusted_evidence",
]
