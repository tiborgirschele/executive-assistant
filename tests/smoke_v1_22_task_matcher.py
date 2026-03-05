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


def test_task_matcher_module_presence() -> None:
    src = (ROOT / "ea/app/planner/task_matcher.py").read_text(encoding="utf-8")
    compiler_src = (ROOT / "ea/app/planner/intent_compiler.py").read_text(encoding="utf-8")
    assert "def infer_domain(" in src
    assert "def detect_high_risk_action(" in src
    assert "def match_task_type(" in src
    assert "from app.planner.task_matcher import" in compiler_src
    _pass("v1.22 task matcher module presence")


def test_task_matcher_behavior() -> None:
    from app.planner.task_matcher import detect_high_risk_action, infer_domain, match_task_type

    txt = "Render route video for tomorrow airport transfer"
    assert infer_domain(txt.lower()) == "travel"
    assert detect_high_risk_action(txt.lower()) is False
    assert match_task_type(txt.lower(), domain="travel", high_risk=False, url_present=False) == "route_video_render"

    txt2 = "Please pay invoice 123 and approve transfer now"
    assert infer_domain(txt2.lower()) == "finance"
    assert detect_high_risk_action(txt2.lower()) is True
    assert match_task_type(txt2.lower(), domain="finance", high_risk=True, url_present=False) == "approval_router"

    txt3 = "Can you summarize this URL https://example.com"
    assert match_task_type(txt3.lower(), domain="general", high_risk=False, url_present=True) == "run_secondary_research_pass"
    _pass("v1.22 task matcher behavior")


if __name__ == "__main__":
    test_task_matcher_module_presence()
    test_task_matcher_behavior()
