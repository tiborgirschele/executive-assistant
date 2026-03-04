from __future__ import annotations

from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

from app.settings import settings


def _parse_iso_datetime(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        if ZoneInfo is not None:
            try:
                dt = dt.replace(tzinfo=ZoneInfo(settings.tz))
            except Exception:
                dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_extracted_calendar_events(
    events: list[dict] | None,
    *,
    default_duration_min: int = 30,
) -> list[dict]:
    """
    Normalize extracted calendar events into a stable import shape.
    - Drops rows without a parseable start timestamp.
    - Infers end timestamp when missing/invalid.
    - Normalizes timestamps to ISO with timezone info.
    """
    duration_min = max(5, int(default_duration_min))
    out: list[dict] = []
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        start_dt = _parse_iso_datetime(ev.get("start"))
        if start_dt is None:
            continue
        end_dt = _parse_iso_datetime(ev.get("end"))
        if end_dt is None or end_dt <= start_dt:
            end_dt = start_dt + timedelta(minutes=duration_min)
        title = str(ev.get("title") or "Appointment").strip() or "Appointment"
        location = str(ev.get("location") or "").strip()
        out.append(
            {
                "title": title[:200],
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "location": location[:200],
            }
        )
    out.sort(key=lambda e: str(e.get("start") or ""))
    return out

