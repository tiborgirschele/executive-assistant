from __future__ import annotations

from app.intelligence.critical_lane import CriticalLaneResult
from app.intelligence.dossiers import Dossier
from app.intelligence.profile import PersonProfileContext


def select_briefing_mode(
    profile: PersonProfileContext,
    dossiers: list[Dossier],
    critical: CriticalLaneResult,
) -> str:
    if profile.confidence.state == "degraded":
        return "low_confidence"
    if critical.exposure_score >= 70 or critical.decision_window_score >= 70:
        return "risk_mode"
    if any(d.kind == "trip" and d.signal_count > 0 for d in dossiers or []):
        return "travel_mode"
    return "standard"


def mode_label(mode: str) -> str:
    m = str(mode or "").strip().lower()
    if m == "risk_mode":
        return "Risk Mode"
    if m == "travel_mode":
        return "Travel Mode"
    if m == "low_confidence":
        return "Low-Confidence Mode"
    return "Standard Mode"

