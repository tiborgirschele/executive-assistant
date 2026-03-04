from __future__ import annotations

import pathlib
import sys
import types
import importlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
for path in (str(ROOT), str(EA_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def _with_stubbed_payments_registry_import():
    old_payments = sys.modules.get("app.skills.payments")
    old_registry = sys.modules.get("app.skills.registry")
    stub = types.ModuleType("app.skills.payments")

    def _stub_run_operation(*, operation: str, tenant: str, chat_id: int, payload: dict | None = None):
        return {
            "ok": True,
            "status": "stubbed",
            "operation": operation,
            "tenant": tenant,
            "chat_id": chat_id,
            "payload": dict(payload or {}),
        }

    stub.run_operation = _stub_run_operation
    sys.modules["app.skills.payments"] = stub
    if "app.skills.registry" in sys.modules:
        del sys.modules["app.skills.registry"]
    registry = importlib.import_module("app.skills.registry")
    return registry, old_payments, old_registry


def test_skill_registry_contracts() -> None:
    payments_src = (ROOT / "ea/app/skills/payments.py").read_text(encoding="utf-8")
    assert "def run_operation(" in payments_src
    registry, old_payments, old_registry = _with_stubbed_payments_registry_import()
    assert "payments" in registry.SKILL_REGISTRY
    try:
        contract = registry.skill_or_raise("payments")
        assert contract.key == "payments"
        assert "generate_demo_draft" in contract.operations
        assert "handle_action" in contract.operations
        assert "approvethis" in contract.capabilities
        assert callable(contract.handler)
        listed = registry.list_skills()
        assert any((entry.get("key") == "payments" for entry in listed))
        row = next((entry for entry in listed if entry.get("key") == "payments"), {})
        caps = row.get("capabilities") if isinstance(row, dict) else []
        assert any((isinstance(c, dict) and c.get("key") == "approvethis" for c in (caps or [])))
    finally:
        if old_registry is not None:
            sys.modules["app.skills.registry"] = old_registry
        else:
            sys.modules.pop("app.skills.registry", None)
        if old_payments is not None:
            sys.modules["app.skills.payments"] = old_payments
        else:
            sys.modules.pop("app.skills.payments", None)
    _pass("v1.19.3 skill registry contracts")


def test_skill_router_dispatch_contract() -> None:
    registry, old_payments, old_registry = _with_stubbed_payments_registry_import()
    SKILL_REGISTRY = registry.SKILL_REGISTRY
    SkillContract = registry.SkillContract
    from app.skills.router import dispatch_skill_operation

    original_registry = dict(SKILL_REGISTRY)
    called: dict[str, object] = {}

    def _demo_handler(*, operation: str, tenant: str, chat_id: int, payload: dict) -> dict:
        called["operation"] = operation
        called["tenant"] = tenant
        called["chat_id"] = chat_id
        called["payload"] = payload
        return {"ok": True, "status": "handled", "operation": operation}

    try:
        SKILL_REGISTRY["demo"] = SkillContract(
            key="demo",
            display_name="Demo",
            operations=("do_thing",),
            handler=_demo_handler,
            capabilities=("apix_drive",),
        )
        ok = dispatch_skill_operation(
            skill_key="demo",
            operation="do_thing",
            tenant="chat_100284",
            chat_id=123,
            payload={"x": 1},
        )
        assert ok.get("ok") is True
        assert called.get("operation") == "do_thing"
        assert called.get("tenant") == "chat_100284"
        assert called.get("chat_id") == 123
        bad = dispatch_skill_operation(
            skill_key="demo",
            operation="unknown",
            tenant="chat_100284",
            chat_id=123,
            payload={},
        )
        assert bad.get("ok") is False
        assert bad.get("status") == "unsupported_operation"
    finally:
        SKILL_REGISTRY.clear()
        SKILL_REGISTRY.update(original_registry)
        if old_registry is not None:
            sys.modules["app.skills.registry"] = old_registry
        else:
            sys.modules.pop("app.skills.registry", None)
        if old_payments is not None:
            sys.modules["app.skills.payments"] = old_payments
        else:
            sys.modules.pop("app.skills.payments", None)
    _pass("v1.19.3 skill router dispatch contract")


if __name__ == "__main__":
    test_skill_registry_contracts()
    test_skill_router_dispatch_contract()
