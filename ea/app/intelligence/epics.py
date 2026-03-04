from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field

from app.intelligence.dossiers import Dossier
from app.intelligence.profile import PersonProfileContext


@dataclass(frozen=True)
class Epic:
    epic_id: str
    kind: str
    title: str
    status: str = "watch"  # watch | active | resolved
    salience: int = 0
    unresolved_count: int = 0
    summary: str = ""
    evidence: tuple[str, ...] = field(default_factory=tuple)


def _stable_epic_id(*, tenant: str, person_id: str, kind: str, title: str) -> str:
    seed = f"{tenant}:{person_id}:{kind}:{title}".encode("utf-8")
    digest = hashlib.sha1(seed).hexdigest()[:16]
    return f"epic_{digest}"


def _trip_epic(profile: PersonProfileContext, dossier: Dossier) -> Epic | None:
    if dossier.kind != "trip" or dossier.signal_count <= 0:
        return None

    threshold = max(500.0, float(os.getenv("EA_CRITICAL_TRAVEL_EUR_THRESHOLD", "5000")))
    salience = min(30, dossier.signal_count * 10)
    unresolved = 0
    summary_parts: list[str] = []

    if dossier.exposure_eur >= threshold:
        salience += 30
        unresolved += 1
        summary_parts.append(f"High spend signal (about EUR {int(round(dossier.exposure_eur)):,}).")
    if dossier.risk_hits:
        salience += min(25, 8 * len(dossier.risk_hits))
        unresolved += 1
        hits = ", ".join(dossier.risk_hits[:3])
        summary_parts.append(f"Route risk keywords present ({hits}).")
    if dossier.near_term:
        salience += 18
        unresolved += 1
        summary_parts.append("Departure window is near-term.")
    if profile.confidence.state == "degraded":
        salience += 8
        summary_parts.append("Runtime confidence degraded; verify key assumptions.")

    status = "active" if unresolved > 0 else "watch"
    if not summary_parts:
        summary_parts.append("Travel commitment has low urgency right now.")

    return Epic(
        epic_id=_stable_epic_id(
            tenant=str(profile.tenant),
            person_id=str(profile.person_id),
            kind="trip",
            title="Trip Commitment",
        ),
        kind="trip",
        title="Trip Commitment",
        status=status,
        salience=min(100, int(salience)),
        unresolved_count=int(unresolved),
        summary=" ".join(summary_parts),
        evidence=tuple(str(x) for x in dossier.evidence if str(x).strip())[:3],
    )


def build_epics_from_dossiers(profile: PersonProfileContext, dossiers: list[Dossier]) -> tuple[Epic, ...]:
    epics: list[Epic] = []
    for d in dossiers or []:
        if d.kind == "trip":
            e = _trip_epic(profile, d)
            if e is not None:
                epics.append(e)
    return tuple(epics)


def rank_epics(epics: tuple[Epic, ...] | list[Epic]) -> tuple[Epic, ...]:
    ordered = sorted(
        tuple(epics or ()),
        key=lambda e: (int(e.salience), int(e.unresolved_count), str(e.title).lower()),
        reverse=True,
    )
    return tuple(ordered)


def summarize_epic_deltas(previous: tuple[Epic, ...], current: tuple[Epic, ...]) -> tuple[str, ...]:
    prev_by_id = {e.epic_id: e for e in (previous or ())}
    cur_by_id = {e.epic_id: e for e in (current or ())}
    out: list[str] = []

    for epic_id, cur in cur_by_id.items():
        prev = prev_by_id.get(epic_id)
        if prev is None:
            out.append(f"New epic: {cur.title} entered {cur.status} state.")
            continue
        if cur.status != prev.status:
            out.append(f"{cur.title}: status changed {prev.status} -> {cur.status}.")
        if cur.unresolved_count != prev.unresolved_count:
            out.append(
                f"{cur.title}: open issues changed {prev.unresolved_count} -> {cur.unresolved_count}."
            )
        salience_delta = int(cur.salience) - int(prev.salience)
        if abs(salience_delta) >= 15:
            direction = "up" if salience_delta > 0 else "down"
            out.append(f"{cur.title}: salience moved {direction} by {abs(salience_delta)} points.")

    for epic_id, prev in prev_by_id.items():
        if epic_id not in cur_by_id:
            out.append(f"Resolved/hidden epic: {prev.title}.")

    return tuple(out[:5])


def total_epic_salience(epics: tuple[Epic, ...] | list[Epic]) -> int:
    return max((int(e.salience) for e in (epics or ())), default=0)


def load_epic_snapshot(path: str) -> tuple[Epic, ...]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = json.load(f)
        if not isinstance(rows, list):
            return tuple()
    except Exception:
        return tuple()

    out: list[Epic] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            evidence = row.get("evidence") or []
            if not isinstance(evidence, (list, tuple)):
                evidence = []
            out.append(
                Epic(
                    epic_id=str(row.get("epic_id") or "").strip(),
                    kind=str(row.get("kind") or "").strip(),
                    title=str(row.get("title") or "").strip(),
                    status=str(row.get("status") or "watch").strip(),
                    salience=int(row.get("salience") or 0),
                    unresolved_count=int(row.get("unresolved_count") or 0),
                    summary=str(row.get("summary") or "").strip(),
                    evidence=tuple(str(x).strip() for x in evidence if str(x).strip()),
                )
            )
        except Exception:
            continue
    return tuple(out)


def save_epic_snapshot(path: str, epics: tuple[Epic, ...] | list[Epic]) -> None:
    try:
        base = os.path.dirname(str(path))
        if base:
            os.makedirs(base, exist_ok=True)
        rows = []
        for epic in epics or ():
            rows.append(asdict(epic))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False)
    except Exception:
        return
