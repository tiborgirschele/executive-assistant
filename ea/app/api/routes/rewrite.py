from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_container
from app.container import AppContainer
from app.domain.models import RewriteRequest
from app.services.policy import PolicyDeniedError

router = APIRouter(prefix="/v1/rewrite", tags=["rewrite"])


class RewriteIn(BaseModel):
    text: str


class RewriteOut(BaseModel):
    artifact_id: str
    kind: str
    content: str
    execution_session_id: str


class SessionEventOut(BaseModel):
    event_id: str
    name: str
    payload: dict[str, object]
    created_at: str


class SessionOut(BaseModel):
    session_id: str
    status: str
    created_at: str
    updated_at: str
    intent_task_type: str
    intent_risk_class: str
    events: list[SessionEventOut]


@router.post("/artifact")
def create_artifact(
    payload: RewriteIn,
    container: AppContainer = Depends(get_container),
) -> RewriteOut:
    text = str(payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    try:
        artifact = container.orchestrator.build_artifact(RewriteRequest(text=text))
    except PolicyDeniedError as exc:
        reason = str(exc or "policy_denied")
        status_code = 409 if reason == "approval_required" else 403
        raise HTTPException(status_code=status_code, detail=f"policy_denied:{reason}") from exc
    return RewriteOut(
        artifact_id=artifact.artifact_id,
        kind=artifact.kind,
        content=artifact.content,
        execution_session_id=artifact.execution_session_id,
    )


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    container: AppContainer = Depends(get_container),
) -> SessionOut:
    found = container.orchestrator.fetch_session(session_id)
    if not found:
        raise HTTPException(status_code=404, detail="session not found")
    session, events = found
    return SessionOut(
        session_id=session.session_id,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        intent_task_type=session.intent.task_type,
        intent_risk_class=session.intent.risk_class,
        events=[
            SessionEventOut(
                event_id=e.event_id,
                name=e.name,
                payload=e.payload,
                created_at=e.created_at,
            )
            for e in events
        ],
    )
