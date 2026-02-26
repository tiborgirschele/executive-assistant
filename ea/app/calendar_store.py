from __future__ import annotations
import hashlib, json, uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, date
from typing import Any, Dict, List, Optional, Tuple

from app.db import connect
from app.settings import settings

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _canon(tenant: str, start: datetime, end: datetime, title: str, location: str) -> str:
    return "|".join([
        tenant.strip().lower(),
        start.astimezone(timezone.utc).isoformat(),
        end.astimezone(timezone.utc).isoformat(),
        (title or "").strip().lower(),
        (location or "").strip().lower(),
    ])

def dedupe_hash(tenant: str, start: datetime, end: datetime, title: str, location: str) -> str:
    return _sha256(_canon(tenant, start, end, title, location))

def ics_token_for_tenant(tenant: str) -> str:
    secret = (settings.calendar_ics_secret or "").strip()
    if not secret:
        return ""
    return _sha256(secret + "|" + tenant.strip().lower())[:32]

def verify_ics_token(tenant: str, token: str) -> bool:
    want = ics_token_for_tenant(tenant)
    if not want or not token:
        return False
    # constant-ish time compare
    if len(token) != len(want):
        return False
    ok = 0
    for a, b in zip(token, want):
        ok |= (ord(a) ^ ord(b))
    return ok == 0

def ensure_schema() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS calendar_events (
        id UUID PRIMARY KEY,
        tenant TEXT NOT NULL,
        start_ts TIMESTAMPTZ NOT NULL,
        end_ts TIMESTAMPTZ NOT NULL,
        title TEXT NOT NULL,
        location TEXT,
        notes TEXT,
        source_type TEXT,
        source_id TEXT,
        dedupe_hash TEXT NOT NULL,
        created_ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE UNIQUE INDEX IF NOT EXISTS calendar_events_tenant_dedupe_idx
        ON calendar_events(tenant, dedupe_hash);

    CREATE TABLE IF NOT EXISTS calendar_imports (
        import_id UUID PRIMARY KEY,
        tenant TEXT NOT NULL,
        source_type TEXT,
        source_id TEXT,
        filename TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        extracted JSONB,
        preview TEXT,
        created_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        committed_ts TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS calendar_notifications (
        id BIGSERIAL PRIMARY KEY,
        tenant TEXT NOT NULL,
        event_id UUID NOT NULL REFERENCES calendar_events(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        scheduled_ts TIMESTAMPTZ NOT NULL,
        sent_ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        payload JSONB
    );
    CREATE INDEX IF NOT EXISTS calendar_notifications_lookup
        ON calendar_notifications(tenant, event_id, kind, sent_ts);
    """
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()

@dataclass(frozen=True)
class CalEvent:
    start_ts: datetime
    end_ts: datetime
    title: str
    location: str = ""
    notes: str = ""
    source_type: str = ""
    source_id: str = ""

def _to_dt(s: str) -> datetime:
    # expects ISO w/ tz
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def create_import(*, tenant: str, source_type: str, source_id: str, filename: str,
                  extracted: Dict[str, Any], preview: str) -> str:
    ensure_schema()
    iid = str(uuid.uuid4())
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calendar_imports (import_id, tenant, source_type, source_id, filename, status, extracted, preview)
                VALUES (%s,%s,%s,%s,%s,'pending',%s,%s)
                """,
                (iid, tenant, source_type, source_id, filename, json.dumps(extracted or {}), preview or ""),
            )
        conn.commit()
    return iid

def get_import(tenant: str, import_id: str) -> Optional[Dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT import_id, tenant, source_type, source_id, filename, status, extracted, preview, created_ts, committed_ts "
                "FROM calendar_imports WHERE tenant=%s AND import_id=%s",
                (tenant, import_id),
            )
            row = cur.fetchone()
    if not row:
        return None
    keys = ["import_id","tenant","source_type","source_id","filename","status","extracted","preview","created_ts","committed_ts"]
    out = dict(zip(keys, row))
    return out

def discard_import(tenant: str, import_id: str) -> bool:
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE calendar_imports SET status='discarded' WHERE tenant=%s AND import_id=%s AND status='pending'",
                (tenant, import_id),
            )
            n = cur.rowcount
        conn.commit()
    return n > 0

def _insert_event(conn, tenant: str, ev: CalEvent) -> bool:
    h = dedupe_hash(tenant, ev.start_ts, ev.end_ts, ev.title, ev.location)
    eid = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO calendar_events (id, tenant, start_ts, end_ts, title, location, notes, source_type, source_id, dedupe_hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (tenant, dedupe_hash) DO NOTHING
            """,
            (eid, tenant, ev.start_ts, ev.end_ts, ev.title, ev.location, ev.notes, ev.source_type, ev.source_id, h),
        )
        return cur.rowcount > 0

def commit_import(tenant: str, import_id: str) -> Tuple[int, str]:
    """
    Commits normalized events stored in import.extracted['normalized_events'].
    Returns (inserted_count, status_message)
    """
    ensure_schema()
    imp = get_import(tenant, import_id)
    if not imp:
        return (0, "import not found")
    if imp.get("status") != "pending":
        return (0, f"import status is {imp.get('status')}, not pending")

    extracted = imp.get("extracted") or {}
    if isinstance(extracted, str):
        extracted = json.loads(extracted)
    norm = extracted.get("normalized_events") or []
    if not isinstance(norm, list) or not norm:
        return (0, "no normalized_events in import")

    inserted = 0
    with connect() as conn:
        for d in norm:
            if not isinstance(d, dict):
                continue
            try:
                start_ts = _to_dt(str(d.get("start_ts")))
                end_ts = _to_dt(str(d.get("end_ts")))
                title = str(d.get("title") or "").strip()
                if not title:
                    continue
                ev = CalEvent(
                    start_ts=start_ts,
                    end_ts=end_ts,
                    title=title,
                    location=str(d.get("location") or "").strip(),
                    notes=str(d.get("notes") or "").strip(),
                    source_type=str(imp.get("source_type") or ""),
                    source_id=str(imp.get("source_id") or ""),
                )
                if _insert_event(conn, tenant, ev):
                    inserted += 1
            except Exception:
                continue

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE calendar_imports SET status='committed', committed_ts=NOW() WHERE tenant=%s AND import_id=%s",
                (tenant, import_id),
            )
        conn.commit()

    return (inserted, "committed")

def list_events_range(tenant: str, start_ts: datetime, end_ts: datetime) -> List[Dict[str, Any]]:
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, start_ts, end_ts, title, location, notes
                FROM calendar_events
                WHERE tenant=%s AND start_ts >= %s AND start_ts < %s
                ORDER BY start_ts ASC
                """,
                (tenant, start_ts, end_ts),
            )
            rows = cur.fetchall() or []
    out = []
    for r in rows:
        out.append({
            "id": str(r[0]),
            "start_ts": r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]),
            "end_ts": r[2].isoformat() if hasattr(r[2], "isoformat") else str(r[2]),
            "title": r[3],
            "location": r[4] or "",
            "notes": r[5] or "",
        })
    return out

def events_for_day(tenant: str, day: date) -> List[Dict[str, Any]]:
    tzinfo = ZoneInfo(settings.tz) if ZoneInfo else timezone.utc
    start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=tzinfo).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    return list_events_range(tenant, start, end)

def was_notified_recently(tenant: str, event_id: str, kind: str, within_minutes: int = 240) -> bool:
    ensure_schema()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=int(within_minutes))
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM calendar_notifications
                WHERE tenant=%s AND event_id=%s AND kind=%s AND sent_ts >= %s
                LIMIT 1
                """,
                (tenant, event_id, kind, cutoff),
            )
            row = cur.fetchone()
    return bool(row)

def mark_notified(tenant: str, event_id: str, kind: str, scheduled_ts: datetime, payload: Dict[str, Any]) -> None:
    ensure_schema()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calendar_notifications (tenant, event_id, kind, scheduled_ts, payload)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (tenant, event_id, kind, scheduled_ts, json.dumps(payload or {})),
            )
        conn.commit()

def render_ics(tenant: str, events: List[Dict[str, Any]]) -> str:
    # Minimal iCalendar feed (UTC times)
    def esc(s: str) -> str:
        return (s or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//EA OS//Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc('EA OS - ' + tenant)}",
    ]

    for e in events:
        uid = esc(str(e.get("id") or str(uuid.uuid4())))
        start = _to_dt(str(e["start_ts"])).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        end = _to_dt(str(e["end_ts"])).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        summary = esc(str(e.get("title") or "Event"))
        loc = esc(str(e.get("location") or ""))
        desc = esc(str(e.get("notes") or ""))

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{summary}",
        ]
        if loc:
            lines.append(f"LOCATION:{loc}")
        if desc:
            lines.append(f"DESCRIPTION:{desc}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
