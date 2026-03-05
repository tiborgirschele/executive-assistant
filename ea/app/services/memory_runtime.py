from __future__ import annotations

import logging

from app.domain.models import MemoryCandidate, MemoryItem, now_utc_iso
from app.repositories.memory_candidates import InMemoryMemoryCandidateRepository, MemoryCandidateRepository
from app.repositories.memory_candidates_postgres import PostgresMemoryCandidateRepository
from app.repositories.memory_items import InMemoryMemoryItemRepository, MemoryItemRepository
from app.repositories.memory_items_postgres import PostgresMemoryItemRepository
from app.settings import Settings, get_settings


class MemoryRuntimeService:
    def __init__(
        self,
        candidates: MemoryCandidateRepository,
        items: MemoryItemRepository,
    ) -> None:
        self._candidates = candidates
        self._items = items

    def stage_candidate(
        self,
        *,
        principal_id: str,
        category: str,
        summary: str,
        fact_json: dict[str, object] | None = None,
        source_session_id: str = "",
        source_event_id: str = "",
        source_step_id: str = "",
        confidence: float = 0.5,
        sensitivity: str = "internal",
    ) -> MemoryCandidate:
        return self._candidates.create_candidate(
            principal_id=principal_id,
            category=category,
            summary=summary,
            fact_json=fact_json,
            source_session_id=source_session_id,
            source_event_id=source_event_id,
            source_step_id=source_step_id,
            confidence=confidence,
            sensitivity=sensitivity,
        )

    def list_candidates(
        self,
        *,
        limit: int = 100,
        status: str | None = None,
        principal_id: str | None = None,
    ) -> list[MemoryCandidate]:
        return self._candidates.list_candidates(limit=limit, status=status, principal_id=principal_id)

    def promote_candidate(
        self,
        candidate_id: str,
        *,
        reviewer: str,
        sharing_policy: str = "private",
        confidence_override: float | None = None,
    ) -> tuple[MemoryCandidate, MemoryItem] | None:
        candidate = self._candidates.get(candidate_id)
        if not candidate:
            return None

        if candidate.status == "promoted" and candidate.promoted_item_id:
            existing = self._items.get(candidate.promoted_item_id)
            if existing:
                refreshed = self._candidates.review(
                    candidate.candidate_id,
                    status="promoted",
                    reviewer=reviewer,
                    promoted_item_id=existing.item_id,
                )
                return (refreshed or candidate, existing)

        confidence_value = candidate.confidence if confidence_override is None else float(confidence_override)
        provenance_json = {
            "candidate_id": candidate.candidate_id,
            "source_session_id": candidate.source_session_id,
            "source_event_id": candidate.source_event_id,
            "source_step_id": candidate.source_step_id,
        }
        item = self._items.create_item(
            principal_id=candidate.principal_id,
            category=candidate.category,
            summary=candidate.summary,
            fact_json=candidate.fact_json,
            provenance_json=provenance_json,
            confidence=confidence_value,
            sensitivity=candidate.sensitivity,
            sharing_policy=sharing_policy,
            reviewer=reviewer,
            last_verified_at=now_utc_iso(),
        )
        updated = self._candidates.review(
            candidate.candidate_id,
            status="promoted",
            reviewer=reviewer,
            promoted_item_id=item.item_id,
        )
        return (updated or candidate, item)

    def reject_candidate(self, candidate_id: str, *, reviewer: str) -> MemoryCandidate | None:
        return self._candidates.review(
            candidate_id,
            status="rejected",
            reviewer=reviewer,
            promoted_item_id="",
        )

    def list_items(self, *, limit: int = 100, principal_id: str | None = None) -> list[MemoryItem]:
        return self._items.list_items(limit=limit, principal_id=principal_id)

    def get_item(self, item_id: str) -> MemoryItem | None:
        return self._items.get(item_id)


def _backend_mode(settings: Settings) -> str:
    return str(settings.storage.backend or "auto").strip().lower()


def _build_candidate_repo(settings: Settings) -> MemoryCandidateRepository:
    backend = _backend_mode(settings)
    log = logging.getLogger("ea.memory_candidates")
    if backend == "memory":
        return InMemoryMemoryCandidateRepository()
    if backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("EA_STORAGE_BACKEND=postgres requires DATABASE_URL")
        return PostgresMemoryCandidateRepository(settings.database_url)
    if settings.database_url:
        try:
            return PostgresMemoryCandidateRepository(settings.database_url)
        except Exception as exc:
            log.warning("postgres memory-candidate backend unavailable in auto mode; falling back to memory: %s", exc)
    return InMemoryMemoryCandidateRepository()


def _build_item_repo(settings: Settings) -> MemoryItemRepository:
    backend = _backend_mode(settings)
    log = logging.getLogger("ea.memory_items")
    if backend == "memory":
        return InMemoryMemoryItemRepository()
    if backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("EA_STORAGE_BACKEND=postgres requires DATABASE_URL")
        return PostgresMemoryItemRepository(settings.database_url)
    if settings.database_url:
        try:
            return PostgresMemoryItemRepository(settings.database_url)
        except Exception as exc:
            log.warning("postgres memory-item backend unavailable in auto mode; falling back to memory: %s", exc)
    return InMemoryMemoryItemRepository()


def build_memory_runtime(settings: Settings | None = None) -> MemoryRuntimeService:
    resolved = settings or get_settings()
    return MemoryRuntimeService(
        candidates=_build_candidate_repo(resolved),
        items=_build_item_repo(resolved),
    )
