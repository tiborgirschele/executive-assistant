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


def test_generic_skill_execution_returns_artifact() -> None:
    from app.skills.router import dispatch_skill_operation

    res = dispatch_skill_operation(
        skill_key="draft_and_polish",
        operation="polish",
        tenant="chat_100284",
        chat_id=123,
        payload={"notes": "Make this update warmer and concise."},
    )
    assert bool(res.get("ok")) is True
    assert str(res.get("status")) == "executed"
    artifacts = list(res.get("artifacts") or [])
    assert artifacts and isinstance(artifacts[0], dict)
    assert str(artifacts[0].get("preview") or "").startswith("Make this update")
    _pass("v1.21 generic skill execution artifact behavior")


def test_typed_action_text_supports_executed_generic_skill() -> None:
    from app.skills.router import dispatch_skill_operation
    from app.skills.runtime_action_exec import execute_typed_action

    out = execute_typed_action(
        tenant_name="chat_100284",
        chat_id=123,
        action_row={
            "action_type": "skill:draft_and_polish",
            "payload_json": {"operation": "polish", "payload": {"notes": "Tighten wording please."}},
        },
        dispatch_skill=dispatch_skill_operation,
    )
    text = str(out.get("text") or "").lower()
    assert "skill action executed" in text
    assert "preview:" in text
    _pass("v1.21 typed-action executed-skill rendering")


if __name__ == "__main__":
    test_generic_skill_execution_returns_artifact()
    test_typed_action_text_supports_executed_generic_skill()
