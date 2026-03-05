from __future__ import annotations

import logging

from app.domain.models import DeliveryOutboxItem, ObservationEvent
from app.repositories.delivery_outbox import DeliveryOutboxRepository, InMemoryDeliveryOutboxRepository
from app.repositories.delivery_outbox_postgres import PostgresDeliveryOutboxRepository
from app.repositories.observation import ObservationEventRepository, InMemoryObservationEventRepository
from app.repositories.observation_postgres import PostgresObservationEventRepository
from app.settings import Settings, get_settings


class ChannelRuntimeService:
    def __init__(
        self,
        observations: ObservationEventRepository,
        outbox: DeliveryOutboxRepository,
    ) -> None:
        self._observations = observations
        self._outbox = outbox

    def ingest_observation(
        self,
        principal_id: str,
        channel: str,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> ObservationEvent:
        return self._observations.append(
            principal_id=principal_id,
            channel=channel,
            event_type=event_type,
            payload=payload,
        )

    def list_recent_observations(self, limit: int = 50) -> list[ObservationEvent]:
        return self._observations.list_recent(limit=limit)

    def queue_delivery(
        self,
        channel: str,
        recipient: str,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> DeliveryOutboxItem:
        return self._outbox.enqueue(channel=channel, recipient=recipient, content=content, metadata=metadata)

    def mark_delivery_sent(self, delivery_id: str) -> DeliveryOutboxItem | None:
        return self._outbox.mark_sent(delivery_id=delivery_id)

    def list_pending_delivery(self, limit: int = 50) -> list[DeliveryOutboxItem]:
        return self._outbox.list_pending(limit=limit)


def _build_observation_repo(settings: Settings) -> ObservationEventRepository:
    backend = str(settings.ledger_backend or "auto").strip().lower()
    log = logging.getLogger("ea.observations")
    if backend == "memory":
        return InMemoryObservationEventRepository()
    if backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("EA_LEDGER_BACKEND=postgres requires DATABASE_URL")
        return PostgresObservationEventRepository(settings.database_url)
    if settings.database_url:
        try:
            return PostgresObservationEventRepository(settings.database_url)
        except Exception as exc:
            log.warning("postgres observation backend unavailable in auto mode; falling back to memory: %s", exc)
    return InMemoryObservationEventRepository()


def _build_outbox_repo(settings: Settings) -> DeliveryOutboxRepository:
    backend = str(settings.ledger_backend or "auto").strip().lower()
    log = logging.getLogger("ea.outbox")
    if backend == "memory":
        return InMemoryDeliveryOutboxRepository()
    if backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("EA_LEDGER_BACKEND=postgres requires DATABASE_URL")
        return PostgresDeliveryOutboxRepository(settings.database_url)
    if settings.database_url:
        try:
            return PostgresDeliveryOutboxRepository(settings.database_url)
        except Exception as exc:
            log.warning("postgres outbox backend unavailable in auto mode; falling back to memory: %s", exc)
    return InMemoryDeliveryOutboxRepository()


def build_channel_runtime() -> ChannelRuntimeService:
    settings = get_settings()
    return ChannelRuntimeService(
        observations=_build_observation_repo(settings),
        outbox=_build_outbox_repo(settings),
    )
