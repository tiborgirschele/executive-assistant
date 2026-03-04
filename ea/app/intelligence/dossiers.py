from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class Dossier:
    kind: str
    title: str
    signal_count: int
    exposure_eur: float = 0.0
    risk_hits: tuple[str, ...] = field(default_factory=tuple)
    near_term: bool = False
    evidence: tuple[str, ...] = field(default_factory=tuple)


def _extract_amounts(raw: str) -> list[float]:
    vals: list[float] = []
    if not raw:
        return vals
    pat = re.compile(r"(?i)(?:€|eur|usd|\$|chf|gbp)\s*([0-9][0-9\.,\s]{1,})")
    for m in pat.finditer(str(raw)):
        token = str(m.group(1) or "").strip().replace(" ", "")
        if not token:
            continue
        normalized = token
        if "," in normalized and "." in normalized:
            if normalized.rfind(",") > normalized.rfind("."):
                normalized = normalized.replace(".", "").replace(",", ".")
            else:
                normalized = normalized.replace(",", "")
        elif "," in normalized:
            parts = normalized.split(",")
            if len(parts[-1]) == 2 and len(parts) > 1:
                normalized = "".join(parts[:-1]).replace(".", "") + "." + parts[-1]
            else:
                normalized = normalized.replace(",", "")
        elif "." in normalized:
            parts = normalized.split(".")
            if len(parts[-1]) == 2 and len(parts) > 1:
                normalized = "".join(parts[:-1]).replace(",", "") + "." + parts[-1]
            else:
                normalized = normalized.replace(".", "")
        try:
            v = float(normalized)
            if v > 0:
                vals.append(v)
        except Exception:
            continue
    return vals


def _event_start_ts(ev: dict) -> datetime | None:
    start_val = ev.get("start", {})
    dt_str = ""
    if isinstance(start_val, dict):
        dt_str = str(start_val.get("dateTime") or start_val.get("date") or "").strip()
    else:
        dt_str = str(start_val or "").strip()
    if not dt_str:
        return None
    try:
        if "T" in dt_str:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(dt_str + "T00:00:00+00:00")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def build_trip_dossier(
    *,
    mails: list[dict],
    calendar_events: list[dict],
    risk_keywords: list[str] | None = None,
    near_term_hours: int | None = None,
) -> Dossier:
    travel_kws = [
        "flight",
        "airline",
        "booking",
        "reservation",
        "itinerary",
        "layover",
        "stopover",
        "check-in",
        "airport",
        "hotel",
        "vacation",
        "holiday",
        "trip",
        "reise",
        "flug",
    ]
    default_risk = [
        "iran",
        "israel",
        "tel aviv",
        "tel-aviv",
        "tehran",
        "gaza",
        "lebanon",
        "ukraine",
        "russia",
        "war",
        "conflict",
        "unrest",
        "advisory",
    ]
    rk = list(risk_keywords or default_risk)
    extra_risk = [x.strip().lower() for x in str(os.getenv("EA_TRAVEL_RISK_KEYWORDS", "")).split(",") if x.strip()]
    if extra_risk:
        rk = list(dict.fromkeys([x.lower() for x in rk] + extra_risk))
    hours = max(12, int(near_term_hours or int(os.getenv("EA_CRITICAL_TRAVEL_WINDOW_HOURS", "72"))))
    now_utc = datetime.now(timezone.utc)

    signal_count = 0
    max_amount = 0.0
    risk_hits: set[str] = set()
    near_term = False
    evidence: list[str] = []

    def _track(raw_text: str) -> bool:
        nonlocal max_amount
        lower = str(raw_text or "").lower()
        hit = any(k in lower for k in travel_kws)
        if hit:
            amts = _extract_amounts(raw_text)
            if amts:
                max_amount = max(max_amount, max(amts))
            for r in rk:
                if r in lower:
                    risk_hits.add(r)
        return hit

    for m in mails or []:
        subject = str(m.get("subject") or m.get("title") or "").strip()
        snippet = str(m.get("snippet") or m.get("body") or m.get("text") or "").strip()
        sender = str(m.get("from") or m.get("sender") or "").strip()
        raw = f"{subject}\n{snippet}\n{sender}"
        if _track(raw):
            signal_count += 1
            if subject and len(evidence) < 3:
                evidence.append(subject[:110])

    for ev in calendar_events or []:
        title = str(ev.get("summary") or ev.get("title") or "").strip()
        location = str(ev.get("location") or "").strip()
        cal = str(ev.get("_calendar") or "").strip()
        raw = f"{title}\n{location}\n{cal}"
        if _track(raw):
            signal_count += 1
            if title and len(evidence) < 3:
                evidence.append(title[:110])
            ts = _event_start_ts(ev)
            if ts and now_utc - timedelta(hours=6) <= ts <= now_utc + timedelta(hours=hours):
                near_term = True

    return Dossier(
        kind="trip",
        title="Trip Dossier",
        signal_count=int(signal_count),
        exposure_eur=float(max_amount),
        risk_hits=tuple(sorted(risk_hits)),
        near_term=bool(near_term),
        evidence=tuple(evidence),
    )
