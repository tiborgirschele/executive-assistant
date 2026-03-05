from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.channels.telegram.adapter import TelegramObservationAdapter
from app.services.channel_runtime import build_channel_runtime

router = APIRouter(prefix="/v1/channels", tags=["channels"])
_runtime = build_channel_runtime()
_telegram = TelegramObservationAdapter()


class TelegramUpdateIn(BaseModel):
    update: dict[str, object] = Field(default_factory=dict)


class TelegramIngestOut(BaseModel):
    observation_id: str
    principal_id: str
    channel: str
    event_type: str
    created_at: str


@router.post("/telegram/ingest")
def ingest_telegram(body: TelegramUpdateIn) -> TelegramIngestOut:
    fields = _telegram.to_observation_fields(body.update)
    event = _runtime.ingest_observation(
        principal_id=str(fields.get("principal_id") or "unknown"),
        channel=_telegram.channel,
        event_type=str(fields.get("event_type") or "telegram.update"),
        payload=dict(fields.get("payload") or {}),
    )
    return TelegramIngestOut(
        observation_id=event.observation_id,
        principal_id=event.principal_id,
        channel=event.channel,
        event_type=event.event_type,
        created_at=event.created_at,
    )
