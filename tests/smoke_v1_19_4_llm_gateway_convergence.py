from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
for path in (str(ROOT), str(EA_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_llm_gateway_package_exports_contract_entrypoint() -> None:
    src = (ROOT / "ea/app/llm_gateway/__init__.py").read_text(encoding="utf-8")
    assert "def ask_text(prompt: str, **kwargs):" in src
    assert "from app.contracts.llm_gateway import ask_text as _contract_ask_text" in src
    assert "DEFAULT_SYSTEM_PROMPT" in src
    assert "__all__" in src
    _pass("v1.19.4 llm gateway package export contract")


def test_safe_llm_call_delegates_to_contract_gateway() -> None:
    import app.contracts.llm_gateway as contract
    from app.llm_gateway.client import safe_llm_call

    captured: dict[str, object] = {}
    original = contract.ask_text

    def _stub_ask_text(prompt: str, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return "stubbed_gateway_response"

    contract.ask_text = _stub_ask_text
    try:
        out = safe_llm_call(
            "hello gateway",
            task_type="profile_summary",
            data_class="derived_summary",
            tenant="chat_100284",
            person_id="person_demo",
            correlation_id="cid-demo",
        )
    finally:
        contract.ask_text = original

    assert out == "stubbed_gateway_response"
    assert captured.get("prompt") == "hello gateway"
    assert captured.get("task_type") == "profile_summary"
    assert captured.get("data_class") == "derived_summary"
    assert captured.get("tenant") == "chat_100284"
    assert captured.get("person_id") == "person_demo"
    assert captured.get("correlation_id") == "cid-demo"
    _pass("v1.19.4 safe_llm_call delegates to contract gateway")


if __name__ == "__main__":
    test_llm_gateway_package_exports_contract_entrypoint()
    test_safe_llm_call_delegates_to_contract_gateway()
