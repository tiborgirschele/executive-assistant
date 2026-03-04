from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class StableProfile:
    tone: str = "concise"
    urgency_tolerance: str = "normal"
    noise_suppression_mode: str = "aggressive"
    spending_sensitivity: str = "high"
    quiet_hours: str = ""


@dataclass(frozen=True)
class SituationalProfile:
    timestamp_utc: datetime
    mode: str = "standard"
    timezone: str = "UTC"
    location_hint: str = ""


@dataclass(frozen=True)
class LearnedProfile:
    preferred_sources: tuple[str, ...] = field(default_factory=tuple)
    sticky_dislikes: tuple[str, ...] = field(default_factory=tuple)
    top_domains: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ConfidenceProfile:
    state: str = "healthy"  # healthy | degraded
    score: float = 1.0
    note: str = ""


@dataclass(frozen=True)
class PersonProfileContext:
    tenant: str
    person_id: str
    stable: StableProfile
    situational: SituationalProfile
    learned: LearnedProfile
    confidence: ConfidenceProfile


def build_profile_context(
    *,
    tenant: str,
    person_id: str,
    timezone_name: str = "UTC",
    runtime_confidence_note: str | None = None,
    mode: str = "standard",
    location_hint: str = "",
) -> PersonProfileContext:
    degraded = bool(str(runtime_confidence_note or "").strip())
    confidence = ConfidenceProfile(
        state="degraded" if degraded else "healthy",
        score=0.55 if degraded else 0.98,
        note=str(runtime_confidence_note or "").strip(),
    )
    situational = SituationalProfile(
        timestamp_utc=datetime.now(timezone.utc),
        mode=str(mode or "standard"),
        timezone=str(timezone_name or "UTC"),
        location_hint=str(location_hint or ""),
    )
    return PersonProfileContext(
        tenant=str(tenant or ""),
        person_id=str(person_id or ""),
        stable=StableProfile(),
        situational=situational,
        learned=LearnedProfile(),
        confidence=confidence,
    )

