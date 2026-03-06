from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies import get_container
from app.container import AppContainer
from app.domain.models import IntentSpecV3
from app.services.policy import PolicyDecisionService

router = APIRouter(prefix="/v1/policy", tags=["policy"])


class PolicyDecisionOut(BaseModel):
    decision_id: str
    session_id: str
    allow: bool
    requires_approval: bool
    reason: str
    retention_policy: str
    memory_write_allowed: bool
    created_at: str


class ApprovalRequestOut(BaseModel):
    approval_id: str
    session_id: str
    step_id: str
    reason: str
    requested_action_json: dict[str, object]
    status: str
    expires_at: str | None
    created_at: str
    updated_at: str


class ApprovalDecisionOut(BaseModel):
    decision_id: str
    approval_id: str
    session_id: str
    step_id: str
    decision: str
    decided_by: str
    reason: str
    created_at: str


class ApprovalDecisionIn(BaseModel):
    decided_by: str = Field(min_length=1, max_length=200)
    reason: str = Field(default="", max_length=1000)


class PolicyEvaluateIn(BaseModel):
    content: str = Field(default="", max_length=50000)
    tool_name: str = Field(default="connector.dispatch", min_length=1, max_length=200)
    action_kind: str = Field(default="delivery.send", min_length=1, max_length=200)
    channel: str = Field(default="email", max_length=100)
    principal_id: str = Field(default="local-user", min_length=1, max_length=200)
    goal: str = Field(default="evaluate outbound action policy", max_length=2000)
    task_type: str = Field(default="external_action", min_length=1, max_length=200)
    deliverable_type: str = Field(default="external_message", max_length=200)
    risk_class: str = Field(default="low", max_length=100)
    approval_class: str = Field(default="none", max_length=100)
    budget_class: str = Field(default="low", max_length=100)
    allowed_tools: list[str] = Field(default_factory=list)
    memory_write_policy: str = Field(default="none", max_length=100)


class PolicyEvaluateOut(BaseModel):
    allow: bool
    requires_approval: bool
    reason: str
    retention_policy: str
    memory_write_allowed: bool
    task_type: str
    tool_name: str
    action_kind: str
    channel: str
    allowed_tools: list[str]


def _policy_service(container: AppContainer) -> PolicyDecisionService:
    return PolicyDecisionService(
        max_rewrite_chars=container.settings.policy.max_rewrite_chars,
        approval_required_chars=container.settings.policy.approval_required_chars,
    )


@router.get("/decisions/recent")
def list_recent_policy_decisions(
    limit: int = Query(default=50, ge=1, le=500),
    session_id: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
) -> list[PolicyDecisionOut]:
    rows = container.orchestrator.list_policy_decisions(limit=limit, session_id=session_id)
    return [
        PolicyDecisionOut(
            decision_id=r.decision_id,
            session_id=r.session_id,
            allow=r.allow,
            requires_approval=r.requires_approval,
            reason=r.reason,
            retention_policy=r.retention_policy,
            memory_write_allowed=r.memory_write_allowed,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/evaluate")
def evaluate_policy(
    body: PolicyEvaluateIn,
    container: AppContainer = Depends(get_container),
) -> PolicyEvaluateOut:
    tool_name = str(body.tool_name or "").strip()
    action_kind = str(body.action_kind or "").strip()
    channel = str(body.channel or "").strip()
    allowed_tools = tuple(str(value or "").strip() for value in body.allowed_tools if str(value or "").strip())
    if not allowed_tools and tool_name:
        allowed_tools = (tool_name,)
    intent = IntentSpecV3(
        principal_id=str(body.principal_id or "local-user").strip() or "local-user",
        goal=str(body.goal or ""),
        task_type=str(body.task_type or "external_action").strip() or "external_action",
        deliverable_type=str(body.deliverable_type or "external_message").strip() or "external_message",
        risk_class=str(body.risk_class or "low").strip() or "low",
        approval_class=str(body.approval_class or "none").strip() or "none",
        budget_class=str(body.budget_class or "low").strip() or "low",
        allowed_tools=allowed_tools,
        memory_write_policy=str(body.memory_write_policy or "none").strip() or "none",
    )
    decision = _policy_service(container).evaluate_rewrite(
        intent,
        str(body.content or ""),
        tool_name=tool_name,
        action_kind=action_kind,
        channel=channel,
    )
    return PolicyEvaluateOut(
        allow=decision.allow,
        requires_approval=decision.requires_approval,
        reason=decision.reason,
        retention_policy=decision.retention_policy,
        memory_write_allowed=decision.memory_write_allowed,
        task_type=intent.task_type,
        tool_name=tool_name,
        action_kind=action_kind,
        channel=channel,
        allowed_tools=list(intent.allowed_tools),
    )


@router.get("/approvals/pending")
def list_pending_approvals(
    limit: int = Query(default=50, ge=1, le=500),
    container: AppContainer = Depends(get_container),
) -> list[ApprovalRequestOut]:
    rows = container.orchestrator.list_pending_approvals(limit=limit)
    return [
        ApprovalRequestOut(
            approval_id=r.approval_id,
            session_id=r.session_id,
            step_id=r.step_id,
            reason=r.reason,
            requested_action_json=r.requested_action_json,
            status=r.status,
            expires_at=r.expires_at,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.get("/approvals/history")
def list_approval_history(
    limit: int = Query(default=50, ge=1, le=500),
    session_id: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
) -> list[ApprovalDecisionOut]:
    rows = container.orchestrator.list_approval_history(limit=limit, session_id=session_id)
    return [
        ApprovalDecisionOut(
            decision_id=r.decision_id,
            approval_id=r.approval_id,
            session_id=r.session_id,
            step_id=r.step_id,
            decision=r.decision,
            decided_by=r.decided_by,
            reason=r.reason,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/approvals/{approval_id}/approve")
def approve_request(
    approval_id: str,
    body: ApprovalDecisionIn,
    container: AppContainer = Depends(get_container),
) -> ApprovalDecisionOut:
    found = container.orchestrator.decide_approval(
        approval_id,
        decision="approve",
        decided_by=body.decided_by,
        reason=body.reason,
    )
    if not found:
        raise HTTPException(status_code=404, detail="approval_not_found")
    _request, decision = found
    return ApprovalDecisionOut(
        decision_id=decision.decision_id,
        approval_id=decision.approval_id,
        session_id=decision.session_id,
        step_id=decision.step_id,
        decision=decision.decision,
        decided_by=decision.decided_by,
        reason=decision.reason,
        created_at=decision.created_at,
    )


@router.post("/approvals/{approval_id}/deny")
def deny_request(
    approval_id: str,
    body: ApprovalDecisionIn,
    container: AppContainer = Depends(get_container),
) -> ApprovalDecisionOut:
    found = container.orchestrator.decide_approval(
        approval_id,
        decision="deny",
        decided_by=body.decided_by,
        reason=body.reason,
    )
    if not found:
        raise HTTPException(status_code=404, detail="approval_not_found")
    _request, decision = found
    return ApprovalDecisionOut(
        decision_id=decision.decision_id,
        approval_id=decision.approval_id,
        session_id=decision.session_id,
        step_id=decision.step_id,
        decision=decision.decision,
        decided_by=decision.decided_by,
        reason=decision.reason,
        created_at=decision.created_at,
    )


@router.post("/approvals/{approval_id}/expire")
def expire_request(
    approval_id: str,
    body: ApprovalDecisionIn,
    container: AppContainer = Depends(get_container),
) -> ApprovalDecisionOut:
    found = container.orchestrator.expire_approval(
        approval_id,
        decided_by=body.decided_by,
        reason=body.reason,
    )
    if not found:
        raise HTTPException(status_code=404, detail="approval_not_found")
    _request, decision = found
    return ApprovalDecisionOut(
        decision_id=decision.decision_id,
        approval_id=decision.approval_id,
        session_id=decision.session_id,
        step_id=decision.step_id,
        decision=decision.decision,
        decided_by=decision.decided_by,
        reason=decision.reason,
        created_at=decision.created_at,
    )
