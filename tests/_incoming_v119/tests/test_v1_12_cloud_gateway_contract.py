
from app.contracts.llm_gateway import DEFAULT_SYSTEM_PROMPT

def test_gateway_contract_exposes_default_system_prompt():
    assert "Executive Assistant" in DEFAULT_SYSTEM_PROMPT
