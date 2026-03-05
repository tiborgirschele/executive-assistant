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
                SELECT provider_key, COALESCE(score_delta, 0) AS score_delta, source
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
        source = str((row or {}).get("source") or "").strip().lower()
        if not provider:
            continue
        if source == "synthetic_preview":
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


def recent_provider_performance(
    *,
    task_type: str,
    lookback_hours: int = 48,
    limit: int = 200,
) -> dict[str, dict[str, Any]]:
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
                SELECT provider_key,
                       COALESCE(score_delta, 0) AS score_delta,
                       outcome_status,
                       latency_ms,
                       source
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

    aggregate: dict[str, dict[str, Any]] = {}
    for row in rows:
        provider = str((row or {}).get("provider_key") or "").strip().lower()
        source = str((row or {}).get("source") or "").strip().lower()
        if not provider:
            continue
        if source == "synthetic_preview":
            continue
        bucket = aggregate.setdefault(
            provider,
            {
                "sample_count": 0,
                "score_delta_sum": 0,
                "success_count": 0,
                "failure_count": 0,
                "latency_sum": 0,
                "latency_samples": 0,
            },
        )
        bucket["sample_count"] = int(bucket["sample_count"]) + 1
        try:
            bucket["score_delta_sum"] = int(bucket["score_delta_sum"]) + int((row or {}).get("score_delta") or 0)
        except Exception:
            pass
        status = str((row or {}).get("outcome_status") or "").strip().lower()
        if status in {"success", "completed", "executed", "ok"}:
            bucket["success_count"] = int(bucket["success_count"]) + 1
        elif status in {"failed", "error", "timeout", "cancelled", "rejected"}:
            bucket["failure_count"] = int(bucket["failure_count"]) + 1
        latency_raw = (row or {}).get("latency_ms")
        try:
            latency = int(latency_raw)
        except Exception:
            latency = None
        if latency is not None and latency >= 0:
            bucket["latency_sum"] = int(bucket["latency_sum"]) + latency
            bucket["latency_samples"] = int(bucket["latency_samples"]) + 1

    out: dict[str, dict[str, Any]] = {}
    for provider, raw in aggregate.items():
        sample_count = max(0, int(raw.get("sample_count") or 0))
        if sample_count <= 0:
            continue
        score_adjustment = max(-40, min(40, int(raw.get("score_delta_sum") or 0)))
        success_count = max(0, int(raw.get("success_count") or 0))
        failure_count = max(0, int(raw.get("failure_count") or 0))
        success_adj = 0
        if sample_count >= 3:
            success_rate = float(success_count) / float(sample_count)
            if success_rate >= 0.80:
                success_adj = 6
            elif success_rate >= 0.60:
                success_adj = 2
            elif success_rate <= 0.30:
                success_adj = -8
            elif success_rate <= 0.50:
                success_adj = -3
        latency_adj = 0
        avg_latency_ms: int | None = None
        latency_samples = max(0, int(raw.get("latency_samples") or 0))
        if latency_samples > 0:
            avg_latency_ms = int(int(raw.get("latency_sum") or 0) / latency_samples)
            if avg_latency_ms > 120_000:
                latency_adj = -6
            elif avg_latency_ms > 60_000:
                latency_adj = -3
            elif avg_latency_ms < 8_000:
                latency_adj = 2
        out[provider] = {
            "sample_count": sample_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_adjustment": int(success_adj),
            "latency_adjustment": int(latency_adj),
            "score_adjustment": int(score_adjustment),
            "avg_latency_ms": avg_latency_ms,
        }
    return out


__all__ = ["record_provider_outcome", "recent_provider_adjustments", "recent_provider_performance"]
