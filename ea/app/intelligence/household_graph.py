from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PersonNode:
    person_id: str
    tenant: str
    role: str = "member"


@dataclass(frozen=True)
class RelationshipEdge:
    source_person_id: str
    target_person_id: str
    relationship: str
    share_scope: str = "none"  # none | summaries | dossiers; never profile


@dataclass(frozen=True)
class SharedEpic:
    epic_id: str
    owner_person_id: str
    allowed_person_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HouseholdGraph:
    people: tuple[PersonNode, ...]
    relationships: tuple[RelationshipEdge, ...] = field(default_factory=tuple)
    shared_epics: tuple[SharedEpic, ...] = field(default_factory=tuple)


def build_household_graph(
    *,
    principals: list[dict],
    relationships: list[dict] | None = None,
    shared_epics: list[dict] | None = None,
) -> HouseholdGraph:
    people: list[PersonNode] = []
    seen_people: set[tuple[str, str]] = set()
    for p in principals or []:
        person_id = str((p or {}).get("person_id") or "").strip()
        tenant = str((p or {}).get("tenant") or "").strip()
        role = str((p or {}).get("role") or "member").strip() or "member"
        if not person_id:
            continue
        key = (tenant, person_id)
        if key in seen_people:
            continue
        seen_people.add(key)
        people.append(PersonNode(person_id=person_id, tenant=tenant, role=role))

    rels: list[RelationshipEdge] = []
    for r in relationships or []:
        rels.append(
            RelationshipEdge(
                source_person_id=str((r or {}).get("source_person_id") or "").strip(),
                target_person_id=str((r or {}).get("target_person_id") or "").strip(),
                relationship=str((r or {}).get("relationship") or "").strip() or "related",
                share_scope=str((r or {}).get("share_scope") or "none").strip().lower(),
            )
        )

    epics: list[SharedEpic] = []
    for e in shared_epics or []:
        allowed_raw = (e or {}).get("allowed_person_ids") or []
        if not isinstance(allowed_raw, (list, tuple)):
            allowed_raw = []
        allowed = tuple(str(x).strip() for x in allowed_raw if str(x).strip())
        epics.append(
            SharedEpic(
                epic_id=str((e or {}).get("epic_id") or "").strip(),
                owner_person_id=str((e or {}).get("owner_person_id") or "").strip(),
                allowed_person_ids=allowed,
            )
        )

    return HouseholdGraph(
        people=tuple(people),
        relationships=tuple(rels),
        shared_epics=tuple(epics),
    )


def ensure_profile_isolation(graph: HouseholdGraph) -> bool:
    """
    Hard invariant: profile state is person-scoped and cannot be shared by edge policy.
    """
    people_ids = {p.person_id for p in graph.people}
    if len(people_ids) != len(graph.people):
        return False
    for rel in graph.relationships:
        if rel.source_person_id and rel.source_person_id not in people_ids:
            return False
        if rel.target_person_id and rel.target_person_id not in people_ids:
            return False
        # Explicitly block any profile-level sharing semantics.
        if rel.share_scope in ("profile", "all", "identity"):
            return False
    for epic in graph.shared_epics:
        if epic.owner_person_id not in people_ids:
            return False
        for pid in epic.allowed_person_ids:
            if pid not in people_ids:
                return False
    return True

