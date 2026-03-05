from __future__ import annotations

from app.repositories.memory_candidates import InMemoryMemoryCandidateRepository
from app.repositories.memory_items import InMemoryMemoryItemRepository
from app.services.memory_runtime import MemoryRuntimeService


def test_inmemory_memory_candidate_review_and_filtering() -> None:
    repo = InMemoryMemoryCandidateRepository()
    first = repo.create_candidate(
        principal_id="exec-1",
        category="stakeholder_pref",
        summary="CEO prefers concise updates",
        fact_json={"tone": "concise"},
        confidence=0.7,
    )
    _second = repo.create_candidate(
        principal_id="exec-2",
        category="commitment",
        summary="Follow-up due Friday",
        fact_json={"deadline": "friday"},
        confidence=0.9,
    )

    reviewed = repo.review(first.candidate_id, status="promoted", reviewer="qa-user", promoted_item_id="item-1")
    assert reviewed is not None
    assert reviewed.status == "promoted"
    assert reviewed.reviewer == "qa-user"
    assert reviewed.promoted_item_id == "item-1"

    promoted = repo.list_candidates(limit=10, status="promoted", principal_id="exec-1")
    assert len(promoted) == 1
    assert promoted[0].candidate_id == first.candidate_id



def test_inmemory_memory_runtime_promote_and_reject_paths() -> None:
    runtime = MemoryRuntimeService(
        candidates=InMemoryMemoryCandidateRepository(),
        items=InMemoryMemoryItemRepository(),
    )

    candidate = runtime.stage_candidate(
        principal_id="exec-1",
        category="preference",
        summary="Prefers agenda before meeting",
        fact_json={"lead_time_minutes": 30},
        source_session_id="session-1",
        source_event_id="event-1",
        source_step_id="step-1",
        confidence=0.65,
        sensitivity="internal",
    )

    promoted = runtime.promote_candidate(
        candidate.candidate_id,
        reviewer="operator-1",
        sharing_policy="private",
    )
    assert promoted is not None
    promoted_candidate, item = promoted
    assert promoted_candidate.status == "promoted"
    assert promoted_candidate.promoted_item_id == item.item_id
    assert item.provenance_json["candidate_id"] == candidate.candidate_id

    listed_items = runtime.list_items(limit=10, principal_id="exec-1")
    assert len(listed_items) == 1
    assert listed_items[0].item_id == item.item_id

    rejected_candidate = runtime.stage_candidate(
        principal_id="exec-1",
        category="noise",
        summary="Low-value transcript fragment",
        fact_json={"raw": "..."},
    )
    rejected = runtime.reject_candidate(rejected_candidate.candidate_id, reviewer="operator-1")
    assert rejected is not None
    assert rejected.status == "rejected"

    pending = runtime.list_candidates(limit=10, status="pending", principal_id="exec-1")
    assert all(row.status == "pending" for row in pending)
