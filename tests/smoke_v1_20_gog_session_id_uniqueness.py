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


def test_gog_session_id_generation_is_unique_and_sanitized() -> None:
    import app.gog as gog

    sid1 = gog._build_gog_session_id(account="John.Doe+test@example.com", task_name="Plan: High Priority Travel")
    sid2 = gog._build_gog_session_id(account="John.Doe+test@example.com", task_name="Plan: High Priority Travel")

    assert isinstance(sid1, str) and isinstance(sid2, str)
    assert sid1 != sid2, "session ids should be unique per run"
    assert len(sid1) <= 96 and len(sid2) <= 96
    assert sid1.startswith("ea-exec-")
    assert "john-doe-test-example-co" in sid1
    assert "plan-high-priority-trave" in sid1
    _pass("v1.20 gog session id uniqueness")


def test_gog_source_has_no_fixed_session_id_literal() -> None:
    src = (ROOT / "ea/app/gog.py").read_text(encoding="utf-8")
    assert '"--session-id", "ea-exec"' not in src
    _pass("v1.20 gog fixed-session-id literal removed")


if __name__ == "__main__":
    test_gog_session_id_generation_is_unique_and_sanitized()
    test_gog_source_has_no_fixed_session_id_literal()
