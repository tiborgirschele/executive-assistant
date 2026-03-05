from __future__ import annotations

from .plan_builder import build_task_plan_steps
from .provider_broker import rank_task_capabilities
from .task_registry import TaskContract, list_task_contracts, task_or_none, task_or_raise

__all__ = [
    "ProactivePlanner",
    "TaskContract",
    "build_task_plan_steps",
    "rank_task_capabilities",
    "task_or_none",
    "task_or_raise",
    "list_task_contracts",
]


def __getattr__(name: str):
    if name == "ProactivePlanner":
        from .proactive import ProactivePlanner

        return ProactivePlanner
    raise AttributeError(f"module 'app.planner' has no attribute {name!r}")
