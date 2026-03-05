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


def test_generic_skill_orchestration_outcomes() -> None:
    from app.skills.router import dispatch_skill_operation

    travel = dispatch_skill_operation(
        skill_key="travel_rescue",
        operation="plan",
        tenant="chat_100284",
        chat_id=123,
        payload={"trip_id": "demo_trip"},
    )
    assert travel.get("ok") is True
    assert travel.get("status") == "planned"
    assert travel.get("operation") == "plan"
    tplan = travel.get("plan") if isinstance(travel.get("plan"), dict) else {}
    assert tplan.get("primary") == "oneair"
    assert "avomap" in list(tplan.get("fallbacks") or [])

    intake = dispatch_skill_operation(
        skill_key="guided_intake",
        operation="dispatch",
        tenant="chat_100284",
        chat_id=123,
        payload={"preferred_capability": "metasurvey"},
    )
    assert intake.get("ok") is True
    assert intake.get("status") == "staged"
    iplan = intake.get("plan") if isinstance(intake.get("plan"), dict) else {}
    assert iplan.get("primary") == "metasurvey"
    assert "involve_me" in list(iplan.get("fallbacks") or [])

    polish = dispatch_skill_operation(
        skill_key="draft_and_polish",
        operation="polish",
        tenant="chat_100284",
        chat_id=123,
        payload={"notes": "Make this warmer and concise"},
    )
    assert polish.get("ok") is True
    assert polish.get("status") == "executed"
    pplan = polish.get("plan") if isinstance(polish.get("plan"), dict) else {}
    assert pplan.get("primary") == "undetectable"
    parts = list(polish.get("artifacts") or [])
    assert parts and isinstance(parts[0], dict)
    _pass("v1.19.4 sidecar skill orchestration outcomes")


def test_typed_action_skill_execution_uses_capability_plan() -> None:
    from app.skills.router import dispatch_skill_operation
    from app.skills.runtime_action_exec import execute_typed_action

    out = execute_typed_action(
        tenant_name="chat_100284",
        chat_id=123,
        action_row={
            "action_type": "skill:trip_context_pack",
            "payload_json": {
                "operation": "build",
                "payload": {"preferred_capability": "avomap"},
            },
        },
        dispatch_skill=dispatch_skill_operation,
    )
    text = str(out.get("text") or "").lower()
    assert "skill result" in text
    assert "primary capability" in text
    assert "avomap" in text
    _pass("v1.19.4 typed skill action uses capability plan")


if __name__ == "__main__":
    test_generic_skill_orchestration_outcomes()
    test_typed_action_skill_execution_uses_capability_plan()
