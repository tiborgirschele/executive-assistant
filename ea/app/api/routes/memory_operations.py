from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies import RequestContext, get_container, get_request_context, resolve_principal_id
from app.container import AppContainer

router = APIRouter(tags=["memory"])


class CommitmentIn(BaseModel):
    principal_id: str | None = Field(default=None, min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=400)
    details: str = Field(default="", max_length=5000)
    status: str = Field(default="open", max_length=80)
    priority: str = Field(default="medium", max_length=80)
    due_at: str | None = Field(default=None, max_length=80)
    source_json: dict[str, object] = Field(default_factory=dict)
    commitment_id: str | None = Field(default=None, max_length=200)


class CommitmentOut(BaseModel):
    commitment_id: str
    principal_id: str
    title: str
    details: str
    status: str
    priority: str
    due_at: str | None
    source_json: dict[str, object]
    created_at: str
    updated_at: str


class DecisionWindowIn(BaseModel):
    principal_id: str | None = Field(default=None, min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=400)
    context: str = Field(default="", max_length=5000)
    opens_at: str | None = Field(default=None, max_length=80)
    closes_at: str | None = Field(default=None, max_length=80)
    urgency: str = Field(default="medium", max_length=80)
    authority_required: str = Field(default="manager", max_length=120)
    status: str = Field(default="open", max_length=80)
    notes: str = Field(default="", max_length=5000)
    source_json: dict[str, object] = Field(default_factory=dict)
    decision_window_id: str | None = Field(default=None, max_length=200)


class DecisionWindowOut(BaseModel):
    decision_window_id: str
    principal_id: str
    title: str
    context: str
    opens_at: str | None
    closes_at: str | None
    urgency: str
    authority_required: str
    status: str
    notes: str
    source_json: dict[str, object]
    created_at: str
    updated_at: str


class DeadlineWindowIn(BaseModel):
    principal_id: str | None = Field(default=None, min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=400)
    start_at: str | None = Field(default=None, max_length=80)
    end_at: str | None = Field(default=None, max_length=80)
    status: str = Field(default="open", max_length=80)
    priority: str = Field(default="medium", max_length=80)
    notes: str = Field(default="", max_length=5000)
    source_json: dict[str, object] = Field(default_factory=dict)
    window_id: str | None = Field(default=None, max_length=200)


class DeadlineWindowOut(BaseModel):
    window_id: str
    principal_id: str
    title: str
    start_at: str | None
    end_at: str | None
    status: str
    priority: str
    notes: str
    source_json: dict[str, object]
    created_at: str
    updated_at: str


class FollowUpIn(BaseModel):
    principal_id: str | None = Field(default=None, min_length=1, max_length=200)
    stakeholder_ref: str = Field(min_length=1, max_length=200)
    topic: str = Field(min_length=1, max_length=500)
    status: str = Field(default="open", max_length=80)
    due_at: str | None = Field(default=None, max_length=80)
    channel_hint: str = Field(default="", max_length=120)
    notes: str = Field(default="", max_length=5000)
    source_json: dict[str, object] = Field(default_factory=dict)
    follow_up_id: str | None = Field(default=None, max_length=200)


class FollowUpOut(BaseModel):
    follow_up_id: str
    principal_id: str
    stakeholder_ref: str
    topic: str
    status: str
    due_at: str | None
    channel_hint: str
    notes: str
    source_json: dict[str, object]
    created_at: str
    updated_at: str


class FollowUpRuleIn(BaseModel):
    principal_id: str | None = Field(default=None, min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    trigger_kind: str = Field(min_length=1, max_length=120)
    channel_scope: list[str] = Field(default_factory=list)
    delay_minutes: int = Field(default=60, ge=0, le=10080)
    max_attempts: int = Field(default=3, ge=1, le=20)
    escalation_policy: str = Field(default="notify_exec", max_length=200)
    conditions_json: dict[str, object] = Field(default_factory=dict)
    action_json: dict[str, object] = Field(default_factory=dict)
    status: str = Field(default="active", max_length=80)
    notes: str = Field(default="", max_length=5000)
    rule_id: str | None = Field(default=None, max_length=200)


class FollowUpRuleOut(BaseModel):
    rule_id: str
    principal_id: str
    name: str
    trigger_kind: str
    channel_scope: list[str]
    delay_minutes: int
    max_attempts: int
    escalation_policy: str
    conditions_json: dict[str, object]
    action_json: dict[str, object]
    status: str
    notes: str
    created_at: str
    updated_at: str


def _commitment_out(row) -> CommitmentOut:  # type: ignore[no-untyped-def]
    return CommitmentOut(
        commitment_id=row.commitment_id,
        principal_id=row.principal_id,
        title=row.title,
        details=row.details,
        status=row.status,
        priority=row.priority,
        due_at=row.due_at,
        source_json=row.source_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _decision_window_out(row) -> DecisionWindowOut:  # type: ignore[no-untyped-def]
    return DecisionWindowOut(
        decision_window_id=row.decision_window_id,
        principal_id=row.principal_id,
        title=row.title,
        context=row.context,
        opens_at=row.opens_at,
        closes_at=row.closes_at,
        urgency=row.urgency,
        authority_required=row.authority_required,
        status=row.status,
        notes=row.notes,
        source_json=row.source_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _deadline_window_out(row) -> DeadlineWindowOut:  # type: ignore[no-untyped-def]
    return DeadlineWindowOut(
        window_id=row.window_id,
        principal_id=row.principal_id,
        title=row.title,
        start_at=row.start_at,
        end_at=row.end_at,
        status=row.status,
        priority=row.priority,
        notes=row.notes,
        source_json=row.source_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _follow_up_out(row) -> FollowUpOut:  # type: ignore[no-untyped-def]
    return FollowUpOut(
        follow_up_id=row.follow_up_id,
        principal_id=row.principal_id,
        stakeholder_ref=row.stakeholder_ref,
        topic=row.topic,
        status=row.status,
        due_at=row.due_at,
        channel_hint=row.channel_hint,
        notes=row.notes,
        source_json=row.source_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _follow_up_rule_out(row) -> FollowUpRuleOut:  # type: ignore[no-untyped-def]
    return FollowUpRuleOut(
        rule_id=row.rule_id,
        principal_id=row.principal_id,
        name=row.name,
        trigger_kind=row.trigger_kind,
        channel_scope=list(row.channel_scope),
        delay_minutes=row.delay_minutes,
        max_attempts=row.max_attempts,
        escalation_policy=row.escalation_policy,
        conditions_json=row.conditions_json,
        action_json=row.action_json,
        status=row.status,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/commitments")
def upsert_memory_commitment(
    body: CommitmentIn,
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> CommitmentOut:
    row = container.memory_runtime.upsert_commitment(
        principal_id=resolve_principal_id(body.principal_id, context),
        title=body.title,
        details=body.details,
        status=body.status,
        priority=body.priority,
        due_at=body.due_at,
        source_json=body.source_json,
        commitment_id=body.commitment_id,
    )
    return _commitment_out(row)


@router.get("/commitments")
def list_memory_commitments(
    principal_id: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> list[CommitmentOut]:
    rows = container.memory_runtime.list_commitments(
        principal_id=resolve_principal_id(principal_id, context),
        limit=limit,
        status=status,
    )
    return [_commitment_out(row) for row in rows]


@router.get("/commitments/{commitment_id}")
def get_memory_commitment(
    commitment_id: str,
    principal_id: str | None = Query(default=None, min_length=1, max_length=200),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> CommitmentOut:
    row = container.memory_runtime.get_commitment(
        commitment_id,
        principal_id=resolve_principal_id(principal_id, context),
    )
    if not row:
        raise HTTPException(status_code=404, detail="commitment_not_found")
    return _commitment_out(row)


@router.post("/decision-windows")
def upsert_memory_decision_window(
    body: DecisionWindowIn,
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> DecisionWindowOut:
    row = container.memory_runtime.upsert_decision_window(
        principal_id=resolve_principal_id(body.principal_id, context),
        title=body.title,
        context=body.context,
        opens_at=body.opens_at,
        closes_at=body.closes_at,
        urgency=body.urgency,
        authority_required=body.authority_required,
        status=body.status,
        notes=body.notes,
        source_json=body.source_json,
        decision_window_id=body.decision_window_id,
    )
    return _decision_window_out(row)


@router.get("/decision-windows")
def list_memory_decision_windows(
    principal_id: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> list[DecisionWindowOut]:
    rows = container.memory_runtime.list_decision_windows(
        principal_id=resolve_principal_id(principal_id, context),
        limit=limit,
        status=status,
    )
    return [_decision_window_out(row) for row in rows]


@router.get("/decision-windows/{decision_window_id}")
def get_memory_decision_window(
    decision_window_id: str,
    principal_id: str | None = Query(default=None, min_length=1, max_length=200),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> DecisionWindowOut:
    row = container.memory_runtime.get_decision_window(
        decision_window_id,
        principal_id=resolve_principal_id(principal_id, context),
    )
    if not row:
        raise HTTPException(status_code=404, detail="decision_window_not_found")
    return _decision_window_out(row)


@router.post("/deadline-windows")
def upsert_memory_deadline_window(
    body: DeadlineWindowIn,
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> DeadlineWindowOut:
    row = container.memory_runtime.upsert_deadline_window(
        principal_id=resolve_principal_id(body.principal_id, context),
        title=body.title,
        start_at=body.start_at,
        end_at=body.end_at,
        status=body.status,
        priority=body.priority,
        notes=body.notes,
        source_json=body.source_json,
        window_id=body.window_id,
    )
    return _deadline_window_out(row)


@router.get("/deadline-windows")
def list_memory_deadline_windows(
    principal_id: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> list[DeadlineWindowOut]:
    rows = container.memory_runtime.list_deadline_windows(
        principal_id=resolve_principal_id(principal_id, context),
        limit=limit,
        status=status,
    )
    return [_deadline_window_out(row) for row in rows]


@router.get("/deadline-windows/{window_id}")
def get_memory_deadline_window(
    window_id: str,
    principal_id: str | None = Query(default=None, min_length=1, max_length=200),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> DeadlineWindowOut:
    row = container.memory_runtime.get_deadline_window(
        window_id,
        principal_id=resolve_principal_id(principal_id, context),
    )
    if not row:
        raise HTTPException(status_code=404, detail="deadline_window_not_found")
    return _deadline_window_out(row)


@router.post("/follow-ups")
def upsert_memory_follow_up(
    body: FollowUpIn,
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> FollowUpOut:
    row = container.memory_runtime.upsert_follow_up(
        principal_id=resolve_principal_id(body.principal_id, context),
        stakeholder_ref=body.stakeholder_ref,
        topic=body.topic,
        status=body.status,
        due_at=body.due_at,
        channel_hint=body.channel_hint,
        notes=body.notes,
        source_json=body.source_json,
        follow_up_id=body.follow_up_id,
    )
    return _follow_up_out(row)


@router.get("/follow-ups")
def list_memory_follow_ups(
    principal_id: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> list[FollowUpOut]:
    rows = container.memory_runtime.list_follow_ups(
        principal_id=resolve_principal_id(principal_id, context),
        limit=limit,
        status=status,
    )
    return [_follow_up_out(row) for row in rows]


@router.get("/follow-ups/{follow_up_id}")
def get_memory_follow_up(
    follow_up_id: str,
    principal_id: str | None = Query(default=None, min_length=1, max_length=200),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> FollowUpOut:
    row = container.memory_runtime.get_follow_up(
        follow_up_id,
        principal_id=resolve_principal_id(principal_id, context),
    )
    if not row:
        raise HTTPException(status_code=404, detail="follow_up_not_found")
    return _follow_up_out(row)


@router.post("/follow-up-rules")
def upsert_memory_follow_up_rule(
    body: FollowUpRuleIn,
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> FollowUpRuleOut:
    row = container.memory_runtime.upsert_follow_up_rule(
        principal_id=resolve_principal_id(body.principal_id, context),
        name=body.name,
        trigger_kind=body.trigger_kind,
        channel_scope=tuple(body.channel_scope),
        delay_minutes=body.delay_minutes,
        max_attempts=body.max_attempts,
        escalation_policy=body.escalation_policy,
        conditions_json=body.conditions_json,
        action_json=body.action_json,
        status=body.status,
        notes=body.notes,
        rule_id=body.rule_id,
    )
    return _follow_up_rule_out(row)


@router.get("/follow-up-rules")
def list_memory_follow_up_rules(
    principal_id: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> list[FollowUpRuleOut]:
    rows = container.memory_runtime.list_follow_up_rules(
        principal_id=resolve_principal_id(principal_id, context),
        limit=limit,
        status=status,
    )
    return [_follow_up_rule_out(row) for row in rows]


@router.get("/follow-up-rules/{rule_id}")
def get_memory_follow_up_rule(
    rule_id: str,
    principal_id: str | None = Query(default=None, min_length=1, max_length=200),
    container: AppContainer = Depends(get_container),
    context: RequestContext = Depends(get_request_context),
) -> FollowUpRuleOut:
    row = container.memory_runtime.get_follow_up_rule(
        rule_id,
        principal_id=resolve_principal_id(principal_id, context),
    )
    if not row:
        raise HTTPException(status_code=404, detail="follow_up_rule_not_found")
    return _follow_up_rule_out(row)
