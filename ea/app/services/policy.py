from __future__ import annotations

from app.domain.models import IntentSpecV3, PolicyDecision


class PolicyDeniedError(RuntimeError):
    pass


class PolicyDecisionService:
    def __init__(self, max_rewrite_chars: int = 20000, approval_required_chars: int = 5000) -> None:
        self._max_rewrite_chars = max(1, int(max_rewrite_chars))
        self._approval_required_chars = max(1, int(approval_required_chars))

    def evaluate_rewrite(
        self,
        intent: IntentSpecV3,
        text: str,
        *,
        tool_name: str = "",
        action_kind: str = "artifact.save",
        channel: str = "",
    ) -> PolicyDecision:
        normalized = str(text or "")
        if not normalized.strip():
            return PolicyDecision(
                allow=False,
                requires_approval=False,
                reason="empty_input",
                retention_policy="none",
                memory_write_allowed=False,
            )
        if len(normalized) > self._max_rewrite_chars:
            return PolicyDecision(
                allow=False,
                requires_approval=False,
                reason="input_too_large",
                retention_policy="none",
                memory_write_allowed=False,
            )
        normalized_tool = str(tool_name or "").strip().lower()
        allowed_tools = {str(value or "").strip().lower() for value in intent.allowed_tools if str(value or "").strip()}
        if normalized_tool and allowed_tools and normalized_tool not in allowed_tools:
            return PolicyDecision(
                allow=False,
                requires_approval=False,
                reason="tool_not_allowed",
                retention_policy="none",
                memory_write_allowed=False,
            )
        requires_approval = intent.approval_class not in ("none", "")
        if len(normalized) >= self._approval_required_chars:
            requires_approval = True
        if str(intent.risk_class or "").strip().lower() in {"high", "critical"}:
            requires_approval = True
        if str(intent.budget_class or "").strip().lower() in {"high", "critical"}:
            requires_approval = True
        normalized_action = str(action_kind or "").strip().lower()
        normalized_channel = str(channel or "").strip().lower()
        if normalized_action in {"delivery.send", "message.send", "connector.dispatch"}:
            requires_approval = True
        if normalized_channel in {"email", "slack", "telegram"} and (
            normalized_action.endswith(".send")
            or normalized_action.startswith("delivery.")
            or normalized_action.startswith("message.")
            or normalized_action.startswith("connector.")
        ):
            requires_approval = True
        return PolicyDecision(
            allow=True,
            requires_approval=requires_approval,
            reason="allowed",
            retention_policy="standard",
            memory_write_allowed=intent.memory_write_policy != "none",
        )
