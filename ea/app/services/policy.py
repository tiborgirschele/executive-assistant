from __future__ import annotations

from app.domain.models import IntentSpecV3, PolicyDecision


class PolicyDeniedError(RuntimeError):
    pass


class PolicyDecisionService:
    def evaluate_rewrite(self, intent: IntentSpecV3, text: str) -> PolicyDecision:
        normalized = str(text or "")
        if not normalized.strip():
            return PolicyDecision(
                allow=False,
                requires_approval=False,
                reason="empty_input",
                retention_policy="none",
                memory_write_allowed=False,
            )
        if len(normalized) > 20000:
            return PolicyDecision(
                allow=False,
                requires_approval=False,
                reason="input_too_large",
                retention_policy="none",
                memory_write_allowed=False,
            )
        requires_approval = intent.approval_class not in ("none", "")
        return PolicyDecision(
            allow=True,
            requires_approval=requires_approval,
            reason="allowed",
            retention_policy="standard",
            memory_write_allowed=intent.memory_write_policy != "none",
        )
