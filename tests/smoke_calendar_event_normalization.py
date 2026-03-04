from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
EA_ROOT = ROOT / "ea"
if str(EA_ROOT) not in sys.path:
    sys.path.insert(0, str(EA_ROOT))


def test_calendar_event_normalization_contract() -> None:
    from app.intake.calendar_events import normalize_extracted_calendar_events

    normalized = normalize_extracted_calendar_events(
        [
            {"title": "B", "start": "2026-03-04T09:30:00+01:00", "end": "2026-03-04T10:00:00+01:00"},
            {"title": "A", "start": "2026-03-04T08:30:00+01:00", "end": ""},
            {"title": "X", "start": "", "end": "2026-03-04T12:00:00+01:00"},
            {"title": "", "start": "2026-03-04T11:00:00+01:00"},
        ],
        default_duration_min=30,
    )
    assert len(normalized) == 3, normalized
    assert [e["title"] for e in normalized] == ["A", "B", "Appointment"], normalized

    first = normalized[0]
    assert first["start"] == "2026-03-04T08:30:00+01:00", first
    assert first["end"] == "2026-03-04T09:00:00+01:00", first

    # End before start must be corrected to default duration.
    corrected = normalize_extracted_calendar_events(
        [
            {
                "title": "Reverse",
                "start": "2026-03-04T14:00:00+01:00",
                "end": "2026-03-04T13:00:00+01:00",
            }
        ]
    )
    assert corrected[0]["end"] == "2026-03-04T14:30:00+01:00", corrected[0]
    print("[SMOKE][HOST][PASS] calendar event normalization contract", flush=True)


if __name__ == "__main__":
    test_calendar_event_normalization_contract()

