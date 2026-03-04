from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "ea/app/poll_listener.py"
GUARD_SRC = ROOT / "ea/app/brief_commands.py"


def test_brief_dedupe_guard_contract() -> None:
    src = SRC.read_text(encoding="utf-8")
    guard_src = GUARD_SRC.read_text(encoding="utf-8")

    assert "from app.brief_commands import" in src
    assert "EA_BRIEF_COMMAND_MIN_INTERVAL_SEC" in guard_src
    assert ".brief_last_command.json" in guard_src
    assert "def brief_command_throttled(" in guard_src
    assert "def brief_enter(" in guard_src
    assert "def brief_exit(" in guard_src

    assert "if _brief_command_throttled(chat_id):" in src
    assert "A briefing was already requested recently" in src
    assert "if not _brief_enter(chat_id):" in src
    assert "A briefing is already in progress" in src
    assert "finally:" in src and "_brief_exit(chat_id)" in src

    print("[SMOKE][HOST][PASS] brief dedupe guard contract")


if __name__ == "__main__":
    test_brief_dedupe_guard_contract()
