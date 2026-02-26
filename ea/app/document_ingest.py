from __future__ import annotations
import os, re, json
from datetime import datetime, timedelta, timezone, date
from typing import Any, Dict, List, Optional, Tuple

from app.audit import log_event
from app.settings import settings
from app.llm_vision import complete_json_with_image
from app.calendar_store import create_import

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")

def _tzinfo():
    return ZoneInfo(settings.tz) if ZoneInfo else timezone.utc

def _parse_date(s: str) -> Optional[date]:
    s = (s or "").strip()
    if not s:
        return None
    # try YYYY-MM-DD
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        pass
    # try DD.MM.YYYY
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if m:
        dd, mm, yy = m.group(1), m.group(2), m.group(3)
        try:
            return date(int(yy), int(mm), int(dd))
        except Exception:
            return None
    return None

def _parse_hhmm(s: Any) -> Optional[Tuple[int,int]]:
    if s is None:
        return None
    t = str(s).strip()
    m = _TIME_RE.match(t)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)))

def _dt_on(d: date, hh: int, mm: int) -> datetime:
    tz = _tzinfo()
    return datetime(d.year, d.month, d.day, hh, mm, 0, tzinfo=tz)

def _infer_end(start: datetime, next_start: Optional[datetime]) -> datetime:
    # Prefer next event start - 5m, else default duration
    if next_start and next_start > start:
        cand = next_start - timedelta(minutes=5)
        if cand > start + timedelta(minutes=10):
            return cand
    return start + timedelta(minutes=int(settings.calendar_default_duration_min))

def _mk_location(facility: str, room: str) -> str:
    f = (facility or "").strip()
    r = (room or "").strip()
    if f and r:
        return f"{f} – Raum {r}"
    if f:
        return f
    if r:
        return f"Raum {r}"
    return ""

def _preview_lines(tenant: str, facility: str, day: date, events: List[Dict[str, Any]]) -> str:
    tz = _tzinfo()
    hdr = f"📅 Import preview for {tenant}\n{day.strftime('%a %d.%m.%Y')} ({settings.tz})"
    if facility:
        hdr += f"\n📍 {facility}"
    lines = [hdr, ""]
    for e in events:
        st = datetime.fromisoformat(e["start_ts"]).astimezone(tz).strftime("%H:%M")
        en = datetime.fromisoformat(e["end_ts"]).astimezone(tz).strftime("%H:%M")
        loc = e.get("location") or ""
        title = e.get("title") or "Event"
        lines.append(f"- {st}–{en}  {title}" + (f"  ({loc})" if loc else ""))
        if e.get("notes"):
            lines.append(f"  note: {e['notes']}")
    return "\n".join(lines).strip()

async def ingest_schedule_photo_to_import(*, tenant: str, image_bytes: bytes, filename: str,
                                         source_type: str, source_id: str) -> Tuple[str, str]:
    """
    Returns (import_id, preview_text).
    """
    tz = settings.tz
    prompt = f"""
You are extracting actionable calendar events from a document photo.
Return ONLY valid JSON (no markdown, no commentary).

Goal:
- Detect date(s) and appointments with times.
- Titles should be human-readable (keep German if present).
- Capture room numbers like G208 if present.
- If end time missing, set it to null (do NOT guess inside the JSON).
- Put important notes (e.g., "lockere Kleidung") into notes.

Output schema:
{{
  "doc_type": "therapy_plan" | "schedule" | "unknown",
  "facility": "string or empty",
  "timezone": "{tz}",
  "dates": [
    {{
      "date": "YYYY-MM-DD or DD.MM.YYYY",
      "events": [
        {{
          "start_time": "HH:MM",
          "end_time": "HH:MM or null",
          "title": "string",
          "room": "string or empty",
          "notes": "string or empty"
        }}
      ]
    }}
  ]
}}

If you cannot find events, return:
{{"doc_type":"unknown","facility":"","timezone":"{tz}","dates":[]}}
""".strip()

    obj = await complete_json_with_image(prompt, image_bytes, mime="image/jpeg", timeout_s=120.0)

    facility = str(obj.get("facility") or "").strip()
    dates = obj.get("dates") or []
    if not isinstance(dates, list):
        dates = []

    # For MVP: commit only the first date block with events
    chosen_day: Optional[date] = None
    raw_events: List[Dict[str, Any]] = []

    for d in dates:
        if not isinstance(d, dict):
            continue
        dd = _parse_date(str(d.get("date") or ""))
        evs = d.get("events") or []
        if dd and isinstance(evs, list) and evs:
            chosen_day = dd
            raw_events = [e for e in evs if isinstance(e, dict)]
            break

    if not chosen_day or not raw_events:
        extracted = {"raw": obj, "normalized_events": []}
        preview = f"❌ No actionable events found in photo for tenant '{tenant}'."
        iid = create_import(
            tenant=tenant, source_type=source_type, source_id=source_id, filename=filename,
            extracted=extracted, preview=preview
        )
        return iid, preview

    # Normalize events: create ISO start/end with tz; infer missing end times
    norm: List[Dict[str, Any]] = []
    starts: List[datetime] = []
    for e in raw_events:
        st = _parse_hhmm(e.get("start_time"))
        if not st:
            continue
        starts.append(_dt_on(chosen_day, st[0], st[1]))

    # sort by start
    paired = []
    for e in raw_events:
        st = _parse_hhmm(e.get("start_time"))
        if not st:
            continue
        start_dt = _dt_on(chosen_day, st[0], st[1])
        paired.append((start_dt, e))
    paired.sort(key=lambda x: x[0])

    for i, (start_dt, e) in enumerate(paired):
        next_start = paired[i+1][0] if i+1 < len(paired) else None
        et = _parse_hhmm(e.get("end_time"))
        if et:
            end_dt = _dt_on(chosen_day, et[0], et[1])
            if end_dt <= start_dt:
                end_dt = _infer_end(start_dt, next_start)
        else:
            end_dt = _infer_end(start_dt, next_start)

        title = str(e.get("title") or "Appointment").strip()
        room = str(e.get("room") or "").strip()
        notes = str(e.get("notes") or "").strip()
        location = _mk_location(facility, room)

        norm.append({
            "start_ts": start_dt.isoformat(),
            "end_ts": end_dt.isoformat(),
            "title": title,
            "location": location,
            "notes": notes,
        })

    preview = _preview_lines(tenant, facility, chosen_day, norm)
    extracted = {"raw": obj, "normalized_events": norm, "facility": facility, "date": chosen_day.isoformat()}

    iid = create_import(
        tenant=tenant, source_type=source_type, source_id=source_id, filename=filename,
        extracted=extracted, preview=preview
    )

    log_event(tenant, "calendar", "import_created", "created calendar import from photo", {
        "import_id": iid, "count": len(norm), "facility": facility, "date": chosen_day.isoformat()
    })
    return iid, preview
