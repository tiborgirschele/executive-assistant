from __future__ import annotations

import logging
import uuid

from app.domain.models import Artifact, ExecutionEvent, ExecutionSession, IntentSpecV3, RewriteRequest
from app.repositories.memory import InMemoryArtifactRepository
from app.repositories.ledger import ExecutionLedgerRepository, InMemoryExecutionLedgerRepository
from app.repositories.ledger_postgres import PostgresExecutionLedgerRepository
from app.settings import Settings, get_settings
from app.services.policy import PolicyDecisionService, PolicyDeniedError


class RewriteOrchestrator:
    def __init__(
        self,
        repo: InMemoryArtifactRepository | None = None,
        ledger: ExecutionLedgerRepository | None = None,
        policy: PolicyDecisionService | None = None,
    ) -> None:
        self._repo = repo or InMemoryArtifactRepository()
        self._ledger = ledger or InMemoryExecutionLedgerRepository()
        self._policy = policy or PolicyDecisionService()

    def build_artifact(self, req: RewriteRequest) -> Artifact:
        intent = IntentSpecV3(
            principal_id="local-user",
            goal="rewrite supplied text into an artifact",
            task_type="rewrite",
            deliverable_type="rewrite_note",
            risk_class="low",
            approval_class="none",
            budget_class="low",
            allowed_tools=("rewrite_store",),
            desired_artifact="rewrite_note",
            memory_write_policy="reviewed_only",
        )
        session = self._ledger.start_session(intent)
        self._ledger.append_event(
            session.session_id,
            "intent_compiled",
            {"task_type": intent.task_type, "risk_class": intent.risk_class},
        )
        normalized_text = str(req.text or "").strip()
        policy_decision = self._policy.evaluate_rewrite(intent, normalized_text)
        self._ledger.append_event(
            session.session_id,
            "policy_decision",
            {
                "allow": policy_decision.allow,
                "requires_approval": policy_decision.requires_approval,
                "reason": policy_decision.reason,
                "retention_policy": policy_decision.retention_policy,
            },
        )
        if not policy_decision.allow:
            self._ledger.complete_session(session.session_id, status="blocked")
            self._ledger.append_event(
                session.session_id,
                "session_blocked",
                {"reason": policy_decision.reason},
            )
            raise PolicyDeniedError(policy_decision.reason)
        if policy_decision.requires_approval:
            self._ledger.complete_session(session.session_id, status="awaiting_approval")
            self._ledger.append_event(
                session.session_id,
                "session_paused_for_approval",
                {"reason": "approval_required"},
            )
            raise PolicyDeniedError("approval_required")
        self._ledger.append_event(
            session.session_id,
            "input_validated",
            {"text_length": len(normalized_text)},
        )
        artifact = Artifact(
            artifact_id=str(uuid.uuid4()),
            kind="rewrite_note",
            content=normalized_text,
            execution_session_id=session.session_id,
        )
        self._repo.save(artifact)
        self._ledger.append_event(
            session.session_id,
            "artifact_persisted",
            {"artifact_id": artifact.artifact_id, "artifact_kind": artifact.kind},
        )
        self._ledger.complete_session(session.session_id, status="completed")
        self._ledger.append_event(session.session_id, "session_completed", {"status": "completed"})
        return artifact

    def fetch_artifact(self, artifact_id: str) -> Artifact | None:
        return self._repo.get(artifact_id)

    def fetch_session(self, session_id: str) -> tuple[ExecutionSession, list[ExecutionEvent]] | None:
        session = self._ledger.get_session(session_id)
        if not session:
            return None
        return session, self._ledger.events_for(session_id)


def build_execution_ledger(settings: Settings) -> ExecutionLedgerRepository:
    backend = str(settings.ledger_backend or "auto").strip().lower()
    log = logging.getLogger("ea.ledger")
    if backend == "memory":
        return InMemoryExecutionLedgerRepository()
    if backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("EA_LEDGER_BACKEND=postgres requires DATABASE_URL")
        return PostgresExecutionLedgerRepository(settings.database_url)

    # auto mode: prefer postgres if available, otherwise memory
    if settings.database_url:
        try:
            return PostgresExecutionLedgerRepository(settings.database_url)
        except Exception as exc:
            log.warning("postgres ledger unavailable in auto mode; falling back to memory: %s", exc)
    return InMemoryExecutionLedgerRepository()


def build_default_orchestrator() -> RewriteOrchestrator:
    settings = get_settings()
    ledger = build_execution_ledger(settings)
    return RewriteOrchestrator(ledger=ledger, policy=PolicyDecisionService())
