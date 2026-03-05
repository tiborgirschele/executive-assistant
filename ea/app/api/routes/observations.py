from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.dependencies import get_container
from app.container import AppContainer

router = APIRouter(prefix="/v1/observations", tags=["observations"])


class ObservationIn(BaseModel):
    principal_id: str = Field(min_length=1, max_length=200)
    channel: str = Field(min_length=1, max_length=100)
    event_type: str = Field(min_length=1, max_length=120)
    payload: dict[str, object] = Field(default_factory=dict)
    source_id: str = Field(default="", max_length=200)
    external_id: str = Field(default="", max_length=200)
    dedupe_key: str = Field(default="", max_length=200)
    auth_context_json: dict[str, object] = Field(default_factory=dict)
    raw_payload_uri: str = Field(default="", max_length=1000)


class ObservationOut(BaseModel):
    observation_id: str
    principal_id: str
    channel: str
    event_type: str
    payload: dict[str, object]
    created_at: str
    source_id: str
    external_id: str
    dedupe_key: str
    auth_context_json: dict[str, object]
    raw_payload_uri: str


@router.post("/ingest")
def ingest_observation(
    body: ObservationIn,
    container: AppContainer = Depends(get_container),
) -> ObservationOut:
    row = container.channel_runtime.ingest_observation(
        principal_id=body.principal_id,
        channel=body.channel,
        event_type=body.event_type,
        payload=body.payload,
        source_id=body.source_id,
        external_id=body.external_id,
        dedupe_key=body.dedupe_key,
        auth_context_json=body.auth_context_json,
        raw_payload_uri=body.raw_payload_uri,
    )
    return ObservationOut(
        observation_id=row.observation_id,
        principal_id=row.principal_id,
        channel=row.channel,
        event_type=row.event_type,
        payload=row.payload,
        created_at=row.created_at,
        source_id=row.source_id,
        external_id=row.external_id,
        dedupe_key=row.dedupe_key,
        auth_context_json=row.auth_context_json,
        raw_payload_uri=row.raw_payload_uri,
    )


@router.get("/recent")
def list_recent_observations(
    limit: int = Query(default=50, ge=1, le=500),
    container: AppContainer = Depends(get_container),
) -> list[ObservationOut]:
    rows = container.channel_runtime.list_recent_observations(limit=limit)
    return [
        ObservationOut(
            observation_id=r.observation_id,
            principal_id=r.principal_id,
            channel=r.channel,
            event_type=r.event_type,
            payload=r.payload,
            created_at=r.created_at,
            source_id=r.source_id,
            external_id=r.external_id,
            dedupe_key=r.dedupe_key,
            auth_context_json=r.auth_context_json,
            raw_payload_uri=r.raw_payload_uri,
        )
        for r in rows
    ]
