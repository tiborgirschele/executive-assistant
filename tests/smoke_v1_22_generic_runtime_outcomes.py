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


def test_generic_runtime_outcome_source_for_live_execution_mode() -> None:
    import app.skills.generic as generic
    from app.skills.router import dispatch_skill_operation

    calls: list[dict[str, object]] = []
    original = generic.record_provider_outcome
    generic.record_provider_outcome = lambda **kwargs: calls.append(dict(kwargs))
    try:
        res = dispatch_skill_operation(
            skill_key="draft_and_polish",
            operation="polish",
            tenant="chat_100284",
            chat_id=123,
            payload={"notes": "Warm and concise", "execution_mode": "provider"},
        )
    finally:
        generic.record_provider_outcome = original

    assert bool(res.get("ok")) is True
    assert str(res.get("status") or "") == "executed"
    assert calls, "expected provider outcome call"
    row = calls[-1]
    assert str(row.get("source") or "") == "skill_runtime"
    assert str(row.get("outcome_status") or "") == "success"
    assert int(row.get("score_delta") if row.get("score_delta") is not None else -999) == 1
    _pass("v1.22 generic runtime outcome source for live execution mode")


if __name__ == "__main__":
    test_generic_runtime_outcome_source_for_live_execution_mode()
