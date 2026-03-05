from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.skills.capability_registry import (
    capability_or_raise,
    capabilities_for_task,
    list_capabilities,
)


@dataclass(frozen=True)
class ProviderContract:
    key: str
    display_name: str
    invocation_method: str
    task_types: tuple[str, ...]
    data_classes: tuple[str, ...]
    user_visible: bool
    blocking: bool
    fallback_policy: str
    budget_policy: str


def _as_provider(row: dict[str, Any]) -> ProviderContract:
    return ProviderContract(
        key=str(row.get("key") or "").strip().lower(),
        display_name=str(row.get("display_name") or "").strip(),
        invocation_method=str(row.get("invocation_method") or "").strip().lower(),
        task_types=tuple(str(x or "").strip().lower() for x in list(row.get("task_types") or [])),
        data_classes=tuple(str(x or "").strip().lower() for x in list(row.get("data_classes") or [])),
        user_visible=bool(row.get("user_visible")),
        blocking=bool(row.get("blocking")),
        fallback_policy=str(row.get("fallback_policy") or "").strip().lower(),
        budget_policy=str(row.get("budget_policy") or "").strip().lower(),
    )


def list_provider_contracts() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in list_capabilities():
        provider = _as_provider(row)
        out.append(
            {
                "key": provider.key,
                "display_name": provider.display_name,
                "invocation_method": provider.invocation_method,
                "task_types": list(provider.task_types),
                "data_classes": list(provider.data_classes),
                "user_visible": provider.user_visible,
                "blocking": provider.blocking,
                "fallback_policy": provider.fallback_policy,
                "budget_policy": provider.budget_policy,
            }
        )
    return out


def provider_or_raise(provider_key: str) -> ProviderContract:
    cap = capability_or_raise(provider_key)
    return ProviderContract(
        key=cap.key,
        display_name=cap.display_name,
        invocation_method=cap.invocation_method,
        task_types=tuple(str(x or "").strip().lower() for x in cap.task_types),
        data_classes=tuple(str(x or "").strip().lower() for x in cap.data_classes),
        user_visible=bool(cap.user_visible),
        blocking=bool(cap.blocking),
        fallback_policy=str(cap.fallback_policy or "").strip().lower(),
        budget_policy=str(cap.budget_policy or "").strip().lower(),
    )


def providers_for_task(task_type: str) -> list[str]:
    return [str(x or "").strip().lower() for x in capabilities_for_task(task_type)]


__all__ = [
    "ProviderContract",
    "list_provider_contracts",
    "provider_or_raise",
    "providers_for_task",
]
