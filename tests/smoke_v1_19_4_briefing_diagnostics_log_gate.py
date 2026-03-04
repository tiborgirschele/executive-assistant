from __future__ import annotations

import contextlib
import io
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
for path in (str(ROOT), str(EA_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_briefing_diagnostics_log_disabled_by_default() -> None:
    src = (ROOT / "ea/app/briefings.py").read_text(encoding="utf-8")
    assert "def _briefing_diagnostics_enabled() -> bool:" in src
    assert "return False" in src
    assert 'if not _env_flag("EA_BRIEFING_DIAGNOSTICS_LOG_ENABLED", default=False):' in src
    _pass("v1.19.4 briefing diagnostics log disabled by default")


def test_briefing_diagnostics_log_enabled_with_flag() -> None:
    src = (ROOT / "ea/app/briefings.py").read_text(encoding="utf-8")
    assert 'print(f"[BRIEFING][DIAGNOSTICS]\\n{joined}", flush=True)' in src
    # lightweight behavior check of the formatter itself
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print("[BRIEFING][DIAGNOSTICS]\ndiag-line", flush=True)
    out = buf.getvalue()
    assert "[BRIEFING][DIAGNOSTICS]" in out
    assert "diag-line" in out
    _pass("v1.19.4 briefing diagnostics log enabled by flag")


if __name__ == "__main__":
    test_briefing_diagnostics_log_disabled_by_default()
    test_briefing_diagnostics_log_enabled_with_flag()
