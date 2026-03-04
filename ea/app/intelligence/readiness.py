from __future__ import annotations

from dataclasses import dataclass, field

from app.intelligence.dossiers import Dossier
from app.intelligence.future_situations import FutureSituation
from app.intelligence.profile import PersonProfileContext
from app.intelligence.scores import readiness_score


@dataclass(frozen=True)
class ReadinessDossier:
    status: str  # ready | watch | critical
    score: int
    blockers: tuple[str, ...] = field(default_factory=tuple)
    watch_items: tuple[str, ...] = field(default_factory=tuple)
    suggested_actions: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[str, ...] = field(default_factory=tuple)


def build_readiness_dossier(
    *,
    profile: PersonProfileContext,
    dossiers: list[Dossier],
    future_situations: tuple[FutureSituation, ...] | list[FutureSituation],
) -> ReadinessDossier:
    blockers: list[str] = []
    watch: list[str] = []
    actions: list[str] = []
    evidence: list[str] = []

    for dossier in dossiers or []:
        if dossier.signal_count <= 0:
            continue
        if dossier.kind == "trip":
            if dossier.exposure_eur >= 5000:
                blockers.append("High-value trip exposure requires explicit review.")
                actions.append("Validate cancellation/rebooking terms and deadlines.")
            if dossier.risk_hits:
                blockers.append("Route/layover risk indicators detected.")
                actions.append("Check official advisories and prepare alternate routing.")
            if dossier.near_term:
                watch.append("Departure window is near-term.")
                actions.append("Confirm check-in, passport/visa, and route viability.")
        if dossier.kind == "project":
            if "blocker" in dossier.risk_hits or "overdue" in dossier.risk_hits:
                blockers.append("Project blockers detected in near-term timeline.")
                actions.append("Resolve project blockers and prepare meeting decisions.")
            if dossier.near_term:
                watch.append("Project prep window is near-term.")
                actions.append("Prepare project context pack and decision checklist.")
        if dossier.kind == "finance_commitment":
            if dossier.exposure_eur >= 1000:
                blockers.append("High-value finance commitment requires review.")
                actions.append("Confirm due date, amount, and available payment/refund options.")
            if "overdue" in dossier.risk_hits or "final_notice" in dossier.risk_hits:
                blockers.append("Finance urgency signals detected (overdue/final notice).")
                actions.append("Prioritize finance follow-up before deadline closes.")
            if dossier.near_term:
                watch.append("Finance deadline window is near-term.")
                actions.append("Prepare payment/approval path and required documents.")
        for item in dossier.evidence:
            if item and item not in evidence and len(evidence) < 3:
                evidence.append(item)

    has_risk_intersection = False
    for situation in future_situations or ():
        title = str(getattr(situation, "title", "")).strip()
        if title and title not in watch and len(watch) < 4:
            watch.append(title)
        if str(getattr(situation, "kind", "")).strip().lower() == "risk_intersection":
            has_risk_intersection = True

    score = readiness_score(
        profile=profile,
        dossiers=dossiers,
        has_future_risk_intersection=has_risk_intersection,
    )
    status = "ready"
    if blockers or score <= 45:
        status = "critical"
    elif watch or score <= 70:
        status = "watch"

    dedup_actions: list[str] = []
    seen = set()
    for action in actions:
        key = action.lower().strip()
        if key and key not in seen:
            seen.add(key)
            dedup_actions.append(action)

    return ReadinessDossier(
        status=status,
        score=int(score),
        blockers=tuple(blockers[:4]),
        watch_items=tuple(watch[:5]),
        suggested_actions=tuple(dedup_actions[:5]),
        evidence=tuple(evidence[:3]),
    )
