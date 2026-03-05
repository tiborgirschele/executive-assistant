from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies import get_container
from app.container import AppContainer

router = APIRouter(prefix="/v1/delivery/outbox", tags=["delivery"])


class DeliveryIn(BaseModel):
    channel: str = Field(min_length=1, max_length=100)
    recipient: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    metadata: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str = Field(default="", max_length=200)


class DeliveryFailedIn(BaseModel):
    error: str = Field(min_length=1, max_length=1000)
    retry_in_seconds: int = Field(default=60, ge=0, le=86400)
    dead_letter: bool = Field(default=False)


class DeliveryOut(BaseModel):
    delivery_id: str
    channel: str
    recipient: str
    content: str
    status: str
    metadata: dict[str, object]
    created_at: str
    sent_at: str | None
    idempotency_key: str
    attempt_count: int
    next_attempt_at: str | None
    last_error: str
    receipt_json: dict[str, object]
    dead_lettered_at: str | None


@router.post("")
def enqueue_delivery(
    body: DeliveryIn,
    container: AppContainer = Depends(get_container),
) -> DeliveryOut:
    row = container.channel_runtime.queue_delivery(
        channel=body.channel,
        recipient=body.recipient,
        content=body.content,
        metadata=body.metadata,
        idempotency_key=body.idempotency_key,
    )
    return DeliveryOut(
        delivery_id=row.delivery_id,
        channel=row.channel,
        recipient=row.recipient,
        content=row.content,
        status=row.status,
        metadata=row.metadata,
        created_at=row.created_at,
        sent_at=row.sent_at,
        idempotency_key=row.idempotency_key,
        attempt_count=row.attempt_count,
        next_attempt_at=row.next_attempt_at,
        last_error=row.last_error,
        receipt_json=row.receipt_json,
        dead_lettered_at=row.dead_lettered_at,
    )


@router.post("/{delivery_id}/sent")
def mark_sent(
    delivery_id: str,
    container: AppContainer = Depends(get_container),
) -> DeliveryOut:
    row = container.channel_runtime.mark_delivery_sent(delivery_id)
    if not row:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    return DeliveryOut(
        delivery_id=row.delivery_id,
        channel=row.channel,
        recipient=row.recipient,
        content=row.content,
        status=row.status,
        metadata=row.metadata,
        created_at=row.created_at,
        sent_at=row.sent_at,
        idempotency_key=row.idempotency_key,
        attempt_count=row.attempt_count,
        next_attempt_at=row.next_attempt_at,
        last_error=row.last_error,
        receipt_json=row.receipt_json,
        dead_lettered_at=row.dead_lettered_at,
    )


@router.post("/{delivery_id}/failed")
def mark_failed(
    delivery_id: str,
    body: DeliveryFailedIn,
    container: AppContainer = Depends(get_container),
) -> DeliveryOut:
    next_attempt_at = None
    if not body.dead_letter:
        next_attempt_at = (datetime.now(timezone.utc) + timedelta(seconds=max(0, body.retry_in_seconds))).isoformat()
    row = container.channel_runtime.mark_delivery_failed(
        delivery_id,
        error=body.error,
        next_attempt_at=next_attempt_at,
        dead_letter=body.dead_letter,
    )
    if not row:
        raise HTTPException(status_code=404, detail="delivery_not_found")
    return DeliveryOut(
        delivery_id=row.delivery_id,
        channel=row.channel,
        recipient=row.recipient,
        content=row.content,
        status=row.status,
        metadata=row.metadata,
        created_at=row.created_at,
        sent_at=row.sent_at,
        idempotency_key=row.idempotency_key,
        attempt_count=row.attempt_count,
        next_attempt_at=row.next_attempt_at,
        last_error=row.last_error,
        receipt_json=row.receipt_json,
        dead_lettered_at=row.dead_lettered_at,
    )


@router.get("/pending")
def list_pending(
    limit: int = Query(default=50, ge=1, le=500),
    container: AppContainer = Depends(get_container),
) -> list[DeliveryOut]:
    rows = container.channel_runtime.list_pending_delivery(limit=limit)
    return [
        DeliveryOut(
            delivery_id=r.delivery_id,
            channel=r.channel,
            recipient=r.recipient,
            content=r.content,
            status=r.status,
            metadata=r.metadata,
            created_at=r.created_at,
            sent_at=r.sent_at,
            idempotency_key=r.idempotency_key,
            attempt_count=r.attempt_count,
            next_attempt_at=r.next_attempt_at,
            last_error=r.last_error,
            receipt_json=r.receipt_json,
            dead_lettered_at=r.dead_lettered_at,
        )
        for r in rows
    ]
