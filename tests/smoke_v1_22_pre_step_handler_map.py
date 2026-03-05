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


def test_pre_step_handler_map_coverage() -> None:
    from app.planner.step_executor import (
        _PLANNER_PRE_EXEC_STEPS,
        _PRE_STEP_HANDLERS,
        _resolve_pre_step_kind,
    )

    required_kinds = {"compile", "context", "approval", "generic"}
    assert required_kinds.issubset(set(_PRE_STEP_HANDLERS.keys()))

    for step_key in sorted(_PLANNER_PRE_EXEC_STEPS):
        resolved_kind = _resolve_pre_step_kind(step_key=step_key, step_kind="")
        assert resolved_kind in _PRE_STEP_HANDLERS, f"missing_handler_for_step:{step_key}:{resolved_kind}"

    assert _resolve_pre_step_kind(step_key="compile_intent", step_kind="compile") in _PRE_STEP_HANDLERS
    assert _resolve_pre_step_kind(step_key="build_approval_context", step_kind="approval") in _PRE_STEP_HANDLERS
    _pass("v1.22 pre-step handler map coverage")


if __name__ == "__main__":
    test_pre_step_handler_map_coverage()
