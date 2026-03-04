from __future__ import annotations

from typing import Any


def safe_llm_call(
    prompt: str,
    *,
    allow_list: list[str] | None = None,
    redact_pii: bool = True,
    system_prompt: str = "Du bist ein präziser Executive Assistant.",
    task_type: str = "briefing_compose",
    purpose: str = "user_assist",
    correlation_id: str = "",
    data_class: str = "derived_summary",
    tenant: str = "",
    person_id: str = "",
    allow_json: bool | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """
    Compatibility entrypoint that delegates to the hardened contract gateway.
    `allow_list`, `redact_pii`, and `extra` are accepted for older callsites.
    """
    _ = allow_list
    _ = redact_pii
    _ = extra
    # Lazy import avoids import cycles while preserving package-level access.
    from app.contracts.llm_gateway import ask_text

    return ask_text(
        prompt,
        system_prompt=system_prompt,
        task_type=task_type,
        purpose=purpose,
        correlation_id=correlation_id,
        data_class=data_class,
        tenant=tenant,
        person_id=person_id,
        allow_json=allow_json,
    )
