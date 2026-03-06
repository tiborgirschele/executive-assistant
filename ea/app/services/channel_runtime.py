from __future__ import annotations

import logging

from app.domain.models import DeliveryOutboxItem, ObservationEvent
from app.repositories.delivery_outbox import DeliveryOutboxRepository, InMemoryDeliveryOutboxRepository
from app.repositories.delivery_outbox_postgres import PostgresDeliveryOutboxRepository
from app.repositories.observation import ObservationEventRepository, InMemoryObservationEventRepository
from app.repositories.observation_postgres import PostgresObservationEventRepository
from app.settings import Settings, ensure_storage_fallback_allowed, get_settings


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
        *,
        source_id: str = "",
        external_id: str = "",
        dedupe_key: str = "",
        auth_context_json: dict[str, object] | None = None,
        raw_payload_uri: str = "",
    ) -> ObservationEvent:
        return self._observations.append(
            principal_id=principal_id,
            channel=channel,
            event_type=event_type,
            payload=payload,
            source_id=source_id,
            external_id=external_id,
            dedupe_key=dedupe_key,
            auth_context_json=auth_context_json,
            raw_payload_uri=raw_payload_uri,
        )

    def list_recent_observations(self, limit: int = 50) -> list[ObservationEvent]:
        return self._observations.list_recent(limit=limit)

    def queue_delivery(
        self,
        channel: str,
        recipient: str,
        content: str,
        metadata: dict[str, object] | None = None,
        *,
        idempotency_key: str = "",
    ) -> DeliveryOutboxItem:
        return self._outbox.enqueue(
            channel=channel,
            recipient=recipient,
            content=content,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )

    def mark_delivery_sent(
        self,
        delivery_id: str,
        *,
        receipt_json: dict[str, object] | None = None,
    ) -> DeliveryOutboxItem | None:
        return self._outbox.mark_sent(delivery_id=delivery_id, receipt_json=receipt_json)

    def mark_delivery_failed(
        self,
        delivery_id: str,
        *,
        error: str,
        next_attempt_at: str | None = None,
        dead_letter: bool = False,
    ) -> DeliveryOutboxItem | None:
        return self._outbox.mark_failed(
            delivery_id=delivery_id,
            error=error,
            next_attempt_at=next_attempt_at,
            dead_letter=dead_letter,
        )

    def list_pending_delivery(self, limit: int = 50) -> list[DeliveryOutboxItem]:
        return self._outbox.list_pending(limit=limit)


def _build_observation_repo(settings: Settings) -> ObservationEventRepository:
    backend = str(settings.storage.backend or "auto").strip().lower()
    log = logging.getLogger("ea.observations")
    if backend == "memory":
        ensure_storage_fallback_allowed(settings, "observation repo configured for memory")
        return InMemoryObservationEventRepository()
    if backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("EA_STORAGE_BACKEND=postgres requires DATABASE_URL")
        return PostgresObservationEventRepository(settings.database_url)
    if settings.database_url:
        try:
            return PostgresObservationEventRepository(settings.database_url)
        except Exception as exc:
            ensure_storage_fallback_allowed(settings, "observation repo auto fallback", exc)
            log.warning("postgres observation backend unavailable in auto mode; falling back to memory: %s", exc)
    ensure_storage_fallback_allowed(settings, "observation repo auto backend without DATABASE_URL")
    return InMemoryObservationEventRepository()


def _build_outbox_repo(settings: Settings) -> DeliveryOutboxRepository:
    backend = str(settings.storage.backend or "auto").strip().lower()
    log = logging.getLogger("ea.outbox")
    if backend == "memory":
        ensure_storage_fallback_allowed(settings, "delivery outbox configured for memory")
        return InMemoryDeliveryOutboxRepository()
    if backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("EA_STORAGE_BACKEND=postgres requires DATABASE_URL")
        return PostgresDeliveryOutboxRepository(settings.database_url)
    if settings.database_url:
        try:
            return PostgresDeliveryOutboxRepository(settings.database_url)
        except Exception as exc:
            ensure_storage_fallback_allowed(settings, "delivery outbox auto fallback", exc)
            log.warning("postgres outbox backend unavailable in auto mode; falling back to memory: %s", exc)
    ensure_storage_fallback_allowed(settings, "delivery outbox auto backend without DATABASE_URL")
    return InMemoryDeliveryOutboxRepository()


def build_channel_runtime(settings: Settings | None = None) -> ChannelRuntimeService:
    resolved = settings or get_settings()
    return ChannelRuntimeService(
        observations=_build_observation_repo(resolved),
        outbox=_build_outbox_repo(resolved),
    )
