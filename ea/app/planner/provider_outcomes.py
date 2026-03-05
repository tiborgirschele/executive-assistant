from __future__ import annotations

from typing import Any

def _get_db():
    from app.db import get_db

    return get_db()


def record_provider_outcome(
    *,
    tenant_key: str = "",
    provider_key: str,
    task_type: str,
    outcome_status: str,
    score_delta: int = 0,
    latency_ms: int | None = None,
    error_class: str = "",
    source: str = "runtime",
) -> None:
    provider = str(provider_key or "").strip().lower()
    task = str(task_type or "").strip().lower()
    if not provider or not task:
        return
    status = str(outcome_status or "").strip().lower() or "unknown"
    delta = max(-20, min(20, int(score_delta)))
    try:
        db = _get_db()
        db.execute(
            """
            INSERT INTO provider_outcomes (
                tenant_key,
                provider_key,
                task_type,
                outcome_status,
                score_delta,
                latency_ms,
                error_class,
                source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(tenant_key or ""),
                provider,
                task,
                status,
                delta,
                int(latency_ms) if latency_ms is not None else None,
                str(error_class or "")[:200] if error_class else None,
                str(source or "runtime")[:60],
            ),
        )
    except Exception:
        return


def recent_provider_adjustments(
    *,
    task_type: str,
    lookback_hours: int = 48,
    limit: int = 200,
) -> dict[str, int]:
    task = str(task_type or "").strip().lower()
    if not task:
        return {}
    hours = max(1, min(168, int(lookback_hours)))
    cap = max(10, min(2000, int(limit)))
    try:
        db = _get_db()
        rows = list(
            db.fetchall(
                """
                SELECT provider_key, COALESCE(score_delta, 0) AS score_delta
                FROM provider_outcomes
                WHERE task_type = %s
                  AND occurred_at >= NOW() - (%s || ' hours')::interval
                ORDER BY occurred_at DESC
                LIMIT %s
                """,
                (task, str(hours), int(cap)),
            )
            or []
        )
    except Exception:
        return {}
    aggregate: dict[str, int] = {}
    for row in rows:
        provider = str((row or {}).get("provider_key") or "").strip().lower()
        if not provider:
            continue
        try:
            delta = int((row or {}).get("score_delta") or 0)
        except Exception:
            delta = 0
        aggregate[provider] = int(aggregate.get(provider, 0) + delta)
    # Keep adjustments bounded so runtime metadata cannot fully override contract priority.
    for provider, delta in list(aggregate.items()):
        aggregate[provider] = max(-40, min(40, int(delta)))
    return aggregate


__all__ = ["record_provider_outcome", "recent_provider_adjustments"]
