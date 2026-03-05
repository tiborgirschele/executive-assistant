from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.channel_runtime import build_channel_runtime

router = APIRouter(prefix="/v1/observations", tags=["observations"])
_runtime = build_channel_runtime()


class ObservationIn(BaseModel):
    principal_id: str = Field(min_length=1, max_length=200)
    channel: str = Field(min_length=1, max_length=100)
    event_type: str = Field(min_length=1, max_length=120)
    payload: dict[str, object] = Field(default_factory=dict)


class ObservationOut(BaseModel):
    observation_id: str
    principal_id: str
    channel: str
    event_type: str
    payload: dict[str, object]
    created_at: str


@router.post("/ingest")
def ingest_observation(body: ObservationIn) -> ObservationOut:
    row = _runtime.ingest_observation(
        principal_id=body.principal_id,
        channel=body.channel,
        event_type=body.event_type,
        payload=body.payload,
    )
    return ObservationOut(
        observation_id=row.observation_id,
        principal_id=row.principal_id,
        channel=row.channel,
        event_type=row.event_type,
        payload=row.payload,
        created_at=row.created_at,
    )


@router.get("/recent")
def list_recent_observations(limit: int = Query(default=50, ge=1, le=500)) -> list[ObservationOut]:
    rows = _runtime.list_recent_observations(limit=limit)
    return [
        ObservationOut(
            observation_id=r.observation_id,
            principal_id=r.principal_id,
            channel=r.channel,
            event_type=r.event_type,
            payload=r.payload,
            created_at=r.created_at,
        )
        for r in rows
    ]
