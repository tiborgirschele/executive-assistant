from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from app.audit import log_event
from app.config import load_tenants
from app.db import connect
from app.places import load_places, haversine_m
from app.settings import settings
from app.telegram import TelegramClient
from app.calendar_store import ensure_schema, list_events_range, was_notified_recently, mark_notified

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

def _tzinfo():
    return ZoneInfo(settings.tz) if ZoneInfo else timezone.utc

def _last_location(tenant: str) -> Optional[Tuple[float,float]]:
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT lat, lon FROM location_events WHERE tenant=%s AND lat IS NOT NULL AND lon IS NOT NULL ORDER BY id DESC LIMIT 1",
                    (tenant,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return (float(row[0]), float(row[1]))
    except Exception:
        return None

def _match_destination_coords(location_text: str) -> Optional[Tuple[float,float,str]]:
    """
    Best-effort: match event.location against place.name (substring).
    """
    loc = (location_text or "").lower()
    if not loc:
        return None
    for p in load_places():
        if not p or float(p.lat) == 0.0 or float(p.lon) == 0.0:
            continue
        if (p.name or "").lower() in loc:
            return (float(p.lat), float(p.lon), p.name)
    return None

def _estimate_travel_minutes(distance_m: float) -> int:
    # crude heuristic:
    # - <2km: walking ~4.5km/h
    # - else: transit/car fallback ~20km/h
    if distance_m <= 0:
        return 0
    if distance_m < 2000:
        speed_m_s = 1.25  # ~4.5 km/h
    else:
        speed_m_s = 5.55  # ~20 km/h
    mins = int(round((distance_m / speed_m_s) / 60.0))
    return max(0, mins)

async def calendar_loop() -> None:
    if not settings.telegram_bot_token:
        log_event(None, "calendar", "skip", "telegram token missing; calendar reminders disabled", {})
        return

    ensure_schema()
    tg = TelegramClient(settings.telegram_bot_token)
    log_event(None, "calendar", "info", "calendar reminder loop started", {
        "loop_interval_s": settings.calendar_loop_interval_s,
        "soon_min": settings.calendar_remind_soon_min,
        "leave_buffer_min": settings.calendar_leave_buffer_min,
        "lookahead_h": settings.calendar_lookahead_hours,
    })

    while True:
        try:
            tenants, _, _ = load_tenants()
            now_utc = datetime.now(timezone.utc)
            horizon = now_utc + timedelta(hours=int(settings.calendar_lookahead_hours))

            for tname, t in (tenants or {}).items():
                if not t or int(getattr(t, "telegram_chat_id", 0) or 0) <= 0:
                    continue

                events = list_events_range(tname, now_utc, horizon)
                if not events:
                    continue

                # compute reminders
                for e in events:
                    try:
                        event_id = str(e.get("id") or "")
                        start_ts = datetime.fromisoformat(str(e["start_ts"]).replace("Z","+00:00"))
                        if start_ts.tzinfo is None:
                            start_ts = start_ts.replace(tzinfo=timezone.utc)
                        start_ts = start_ts.astimezone(timezone.utc)
                    except Exception:
                        continue

                    # 1) imminent reminder
                    soon_ts = start_ts - timedelta(minutes=int(settings.calendar_remind_soon_min))
                    if now_utc >= soon_ts and now_utc < soon_ts + timedelta(seconds=float(settings.calendar_loop_interval_s) + 5):
                        if not was_notified_recently(tname, event_id, "soon", within_minutes=360):
                            title = e.get("title") or "Event"
                            loc = e.get("location") or ""
                            st_local = start_ts.astimezone(_tzinfo()).strftime("%H:%M")
                            msg = f"⏰ Upcoming ({st_local}) — {title}"
                            if loc:
                                msg += f"\n📍 {loc}"
                            if e.get("notes"):
                                msg += f"\n📝 {e['notes']}"
                            await tg.send_message(chat_id=int(t.telegram_chat_id), text=msg, parse_mode=None)
                            mark_notified(tname, event_id, "soon", soon_ts, {"kind":"soon"})
                            log_event(tname, "calendar", "notify", "sent soon reminder", {"event_id": event_id})

                    # 2) leave reminder (only if we can estimate destination coords + have last location)
                    dest = _match_destination_coords(str(e.get("location") or ""))
                    cur_loc = _last_location(tname)
                    if dest and cur_loc:
                        dlat, dlon, pname = dest
                        clat, clon = cur_loc
                        dist_m = haversine_m(float(clat), float(clon), float(dlat), float(dlon))
                        travel_min = _estimate_travel_minutes(dist_m)
                        leave_ts = start_ts - timedelta(minutes=(travel_min + int(settings.calendar_leave_buffer_min)))

                        if now_utc >= leave_ts and now_utc < leave_ts + timedelta(seconds=float(settings.calendar_loop_interval_s) + 5):
                            if not was_notified_recently(tname, event_id, "leave", within_minutes=360):
                                title = e.get("title") or "Event"
                                st_local = start_ts.astimezone(_tzinfo()).strftime("%H:%M")
                                maps = f"https://www.google.com/maps/dir/?api=1&destination={dlat},{dlon}"
                                msg = (
                                    f"🚶 Leave now — {title}\n"
                                    f"🕒 Starts {st_local}\n"
                                    f"📍 Destination: {pname}\n"
                                    f"📏 Est. travel: ~{travel_min} min (+{settings.calendar_leave_buffer_min} buffer)\n"
                                    f"🗺️ {maps}"
                                )
                                await tg.send_message(chat_id=int(t.telegram_chat_id), text=msg, parse_mode=None)
                                mark_notified(tname, event_id, "leave", leave_ts, {"kind":"leave","travel_min":travel_min,"dist_m":dist_m,"maps":maps})
                                log_event(tname, "calendar", "notify", "sent leave reminder", {"event_id": event_id, "travel_min": travel_min})

        except Exception as e:
            log_event(None, "calendar", "error", "calendar loop error", {"error": str(e)})

        await asyncio.sleep(float(settings.calendar_loop_interval_s))
