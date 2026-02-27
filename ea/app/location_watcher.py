from __future__ import annotations
import asyncio, json
from datetime import datetime, timedelta, timezone
from app.audit import log_event
from app.config import load_tenants
from app.db import connect
from app.places import load_places, haversine_m
from app.settings import settings
from app.telegram import TelegramClient

def _get_cursor(tenant: str) -> int:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT last_id FROM location_cursors WHERE tenant=%s", (tenant,))
            row = cur.fetchone()
    return int(row[0]) if row else 0

def _set_cursor(tenant: str, last_id: int) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO location_cursors (tenant, last_id, updated_ts)
                VALUES (%s,%s,NOW())
                ON CONFLICT (tenant) DO UPDATE SET last_id=EXCLUDED.last_id, updated_ts=NOW()
                """,
                (tenant, int(last_id)),
            )
        conn.commit()

def _shopping_open(tenant: str) -> list[str]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT item FROM shopping_list WHERE tenant=%s AND checked=false ORDER BY updated_ts DESC LIMIT 200", (tenant,))
            rows = cur.fetchall()
    return [r[0] for r in rows] if rows else []

def _recently_notified(tenant: str, place_id: str, suggestion_key: str, cooldown_min: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=int(cooldown_min))
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM location_notifications
                WHERE tenant=%s AND place_id=%s AND suggestion_key=%s AND sent_ts >= %s
                LIMIT 1
                """,
                (tenant, place_id, suggestion_key, cutoff),
            )
            row = cur.fetchone()
    return bool(row)

def _mark_notified(tenant: str, place_id: str, suggestion_key: str, payload: dict) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO location_notifications (tenant, place_id, suggestion_key, payload) VALUES (%s,%s,%s,%s)",
                (tenant, place_id, suggestion_key, json.dumps(payload or {})),
            )
        conn.commit()

async def location_loop() -> None:
    if not settings.telegram_bot_token:
        log_event(None, "location", "skip", "telegram token missing; location notifications disabled", {})
        return

    tg = TelegramClient(settings.telegram_bot_token)
    log_event(None, "location", "info", "location watcher started", {"interval_s": settings.location_poll_interval_s})

    while True:
        try:
            tenants, _, _ = load_tenants()
            places = load_places()

            for tname, t in tenants.items():
                last_id = _get_cursor(tname)
                with connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id, lat, lon, ts FROM location_events WHERE tenant=%s AND id > %s ORDER BY id ASC LIMIT 50",
                            (tname, last_id),
                        )
                        rows = cur.fetchall()

                if not rows:
                    continue

                max_id = last_id
                for eid, lat, lon, ts in rows:
                    max_id = max(max_id, int(eid))
                    if lat is None or lon is None:
                        continue

                    for p in places:
                        if float(p.lat) == 0.0 and float(p.lon) == 0.0:
                            continue
                        d = haversine_m(float(lat), float(lon), float(p.lat), float(p.lon))
                        if d > float(p.radius_m):
                            continue

                        for s in p.suggestions:
                            nt = tenants.get(s.notify_tenant)
                            if not nt or nt.telegram_chat_id <= 0:
                                continue
                            if _recently_notified(nt.name, p.id, s.key, s.cooldown_minutes):
                                continue

                            items = _shopping_open(nt.name)
                            items_l = [i.lower() for i in items]
                            hit = None
                            for kw in s.match_shopping_keywords:
                                for it in items_l:
                                    if kw and kw in it:
                                        hit = kw
                                        break
                                if hit:
                                    break
                            if not hit:
                                continue

                            maps = f"https://www.google.com/maps/dir/?api=1&destination={p.lat},{p.lon}"
                            msg = (
                                f"📍 Near {p.name}\n"
                                f"Action: {s.message}\n"
                                f"Reason: shopping list contains '{hit}'.\n"
                                f"Navigate: {maps}"
                            )
                            await tg.send_message(chat_id=nt.telegram_chat_id, text=msg, parse_mode=None)
                            _mark_notified(nt.name, p.id, s.key, {"place": p.name, "hit": hit, "maps": maps})
                            log_event(nt.name, "location", "notify", "sent location suggestion", {"place": p.name, "hit": hit})
                _set_cursor(tname, max_id)

        except Exception as e:
            log_event(None, "location", "error", "location watcher error", {"error": str(e)})

        await asyncio.sleep(float(settings.location_poll_interval_s))
