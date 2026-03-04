from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLL = ROOT / "ea/app/poll_listener.py"
GATE = ROOT / "ea/app/newspaper/pdf_quality_gate.py"


def main() -> int:
    poll_src = POLL.read_text(encoding="utf-8")
    gate_src = GATE.read_text(encoding="utf-8")
    assert "from app.newspaper.pdf_quality_gate import validate_newspaper_pdf_bytes" in poll_src
    assert "validate_newspaper_pdf_bytes(pdf_bytes, min_pages=4, min_images=3)" in poll_src
    assert "brief_newspaper_pdf_quality_gate_failed" in poll_src
    assert "def validate_newspaper_pdf_bytes(" in gate_src
    assert "min_pages: int = 4" in gate_src
    assert "min_images: int = 3" in gate_src
    print("PASS: newspaper pdf quality gate wiring smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
