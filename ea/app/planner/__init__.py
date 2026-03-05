from __future__ import annotations

from .task_registry import TaskContract, list_task_contracts, task_or_none, task_or_raise

__all__ = [
    "ProactivePlanner",
    "TaskContract",
    "task_or_none",
    "task_or_raise",
    "list_task_contracts",
]


def __getattr__(name: str):
    if name == "ProactivePlanner":
        from .proactive import ProactivePlanner

        return ProactivePlanner
    raise AttributeError(f"module 'app.planner' has no attribute {name!r}")
