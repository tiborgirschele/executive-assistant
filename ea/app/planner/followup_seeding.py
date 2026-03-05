from __future__ import annotations

from typing import Any

from app.planner.world_model import create_artifact, create_followup, upsert_commitment

DEFERRED_ARTIFACT_TYPES = {
    "decision_pack",
    "strategy_pack",
    "evidence_pack",
    "travel_decision_pack",
}


def seed_followups_for_deferred_artifacts(
    *,
    tenant_key: str,
    session_id: str | None,
    commitment_key: str,
    domain: str,
    title: str,
    artifacts: list[dict[str, Any]] | None = None,
    source: str = "runtime",
) -> dict[str, Any]:
    tenant = str(tenant_key or "").strip()
    commit_key = str(commitment_key or "").strip()
    if not tenant or not commit_key:
        return {"followup_ids": [], "output_refs": [], "commitment_key": commit_key}

    safe_domain = str(domain or "general").strip().lower() or "general"
    safe_title = str(title or "Follow-up commitment").strip() or "Follow-up commitment"
    try:
        upsert_commitment(
            tenant_key=tenant,
            commitment_key=commit_key,
            domain=safe_domain,
            title=safe_title,
            status="open",
            metadata={"source": str(source or "runtime"), "session_id": str(session_id or "")},
        )
    except Exception:
        pass

    followup_ids: list[str] = []
    output_refs: list[str] = []
    for raw in list(artifacts or []):
        artifact = dict(raw or {})
        artifact_type = str(artifact.get("artifact_type") or "").strip().lower()
        if artifact_type not in DEFERRED_ARTIFACT_TYPES:
            continue

        artifact_id = str(artifact.get("artifact_id") or "").strip()
        if not artifact_id:
            summary = str(artifact.get("summary") or "").strip()
            content = artifact.get("content") if isinstance(artifact.get("content"), dict) else {}
            try:
                artifact_id = str(
                    create_artifact(
                        tenant_key=tenant,
                        session_id=str(session_id or "") or None,
                        commitment_key=commit_key,
                        artifact_type=artifact_type,
                        summary=summary,
                        content=dict(content or {}),
                    )
                    or ""
                )
            except Exception:
                artifact_id = ""

        note = str(artifact.get("note") or "").strip()
        if not note:
            note = f"Review {artifact_type.replace('_', ' ')} output and decide next action."
        try:
            followup_id = str(
                create_followup(
                    tenant_key=tenant,
                    commitment_key=commit_key,
                    artifact_id=artifact_id or None,
                    notes=note,
                )
                or ""
            )
        except Exception:
            followup_id = ""

        if artifact_id:
            output_refs.append(f"artifact:{artifact_id}")
        if followup_id:
            followup_ids.append(followup_id)
            output_refs.append(f"followup:{followup_id}")

    # Keep deterministic order while removing accidental duplicates.
    dedup_refs: list[str] = []
    for ref in output_refs:
        if ref not in dedup_refs:
            dedup_refs.append(ref)

    return {
        "followup_ids": followup_ids,
        "output_refs": dedup_refs,
        "commitment_key": commit_key,
    }


__all__ = ["DEFERRED_ARTIFACT_TYPES", "seed_followups_for_deferred_artifacts"]
