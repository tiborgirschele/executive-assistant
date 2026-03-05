from __future__ import annotations

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


class DeliveryOut(BaseModel):
    delivery_id: str
    channel: str
    recipient: str
    content: str
    status: str
    metadata: dict[str, object]
    created_at: str
    sent_at: str | None


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
        )
        for r in rows
    ]
