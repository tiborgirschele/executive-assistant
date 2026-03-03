from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1] / "ea"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import get_db
from app.intake.browseract import process_browseract_event
from app.integrations.avomap.service import AvoMapService
from app.settings import settings


def p(msg: str) -> None:
    print(msg, flush=True)


def _ctx(city: str) -> dict:
    return {
        "home_base": {"lat": 48.2082, "lon": 16.3738, "city": "Vienna"},
        "route_stops": [
            {"label": f"{city} Airport", "city": city, "country": "CH", "lat": 47.4582, "lon": 8.5555},
            {"label": f"{city} Hotel", "city": city, "country": "CH", "lat": 47.3769, "lon": 8.5417},
            {"label": f"{city} HQ", "city": city, "country": "CH", "lat": 47.3780, "lon": 8.5400},
        ],
        "travel_email_hints": [
            f"Flight booking to {city}",
            f"Hotel confirmation in {city}",
        ],
    }


def _browser_job_data(db, *, tenant: str) -> dict:
    row = db.fetchone(
        """
        SELECT script_payload_json
        FROM browser_jobs
        WHERE tenant=%s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (tenant,),
    ) or {}
    payload = row.get("script_payload_json") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    data = (payload or {}).get("data") or {}
    return dict(data) if isinstance(data, dict) else {}


def _enqueue_browseract_event(db, *, tenant: str, workflow: str, payload: dict) -> str:
    event_pk_col = "event_id"
    has_legacy_id = db.fetchone(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name='external_events' AND column_name='id'
        LIMIT 1
        """
    )
    if has_legacy_id:
        event_pk_col = "id"
    row = db.fetchone(
        f"""
        INSERT INTO external_events (tenant, source, event_type, dedupe_key, payload_json, status, next_attempt_at)
        VALUES (%s, 'browseract', %s, %s, %s::jsonb, 'new', NOW())
        RETURNING {event_pk_col}::text AS event_pk
        """,
        (tenant, workflow, str(uuid4()), json.dumps(payload)),
    ) or {}
    return str((row or {}).get("event_pk") or "")


def test_v126_avomap() -> None:
    db = get_db()
    svc = AvoMapService(db, enabled=True)

    tenant = f"e2e_v126_{uuid4().hex[:8]}"
    person = "p1"
    day = "2026-03-04"
    decision = svc.plan_for_briefing(tenant=tenant, person_id=person, day_context=_ctx("Zurich"), date_key=day)
    assert decision["status"] in {"dispatched", "existing_spec", "cache_hit"}, decision

    spec_row = db.fetchone(
        """
        SELECT spec_id, cache_key
        FROM travel_video_specs
        WHERE tenant=%s AND person_id=%s AND date_key=%s
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (tenant, person, day),
    )
    assert spec_row and spec_row.get("spec_id"), spec_row
    spec_id = str(spec_row["spec_id"])
    cache_key = str(spec_row.get("cache_key") or "")

    payload_ok = _browser_job_data(db, tenant=tenant)
    payload_ok.update(
        {
            "status": "completed",
            "spec_id": spec_id,
            "cache_key": cache_key,
            "object_ref": f"https://cdn.example.com/avomap/{uuid4().hex}.mp4",
            "render_id": f"render-{uuid4().hex[:10]}",
            "duration_sec": 21,
        }
    )
    event_id = _enqueue_browseract_event(
        db,
        tenant=tenant,
        workflow=settings.avomap_browseract_workflow,
        payload=payload_ok,
    )
    assert event_id, "browseract event id missing"
    asyncio.run(process_browseract_event(event_id))

    event_id_dup = _enqueue_browseract_event(
        db,
        tenant=tenant,
        workflow=settings.avomap_browseract_workflow,
        payload=payload_ok,
    )
    assert event_id_dup, "browseract duplicate event id missing"
    asyncio.run(process_browseract_event(event_id_dup))

    ready = svc.get_ready_asset(tenant=tenant, person_id=person, date_key=day)
    assert ready and str(ready.get("object_ref", "")).startswith("https://"), ready

    person2 = "p2"
    jobs_before = db.fetchone("SELECT COUNT(*) AS c FROM browser_jobs WHERE tenant=%s", (tenant,))
    decision_p2 = svc.plan_for_briefing(tenant=tenant, person_id=person2, day_context=_ctx("Zurich"), date_key=day)
    assert decision_p2["status"] in {"cache_hit", "existing_spec"}, decision_p2
    jobs_after = db.fetchone("SELECT COUNT(*) AS c FROM browser_jobs WHERE tenant=%s", (tenant,))
    assert int((jobs_after or {}).get("c") or 0) == int((jobs_before or {}).get("c") or 0), (jobs_before, jobs_after)
    ready_p2 = svc.get_ready_asset(tenant=tenant, person_id=person2, date_key=day)
    assert ready_p2 and str(ready_p2.get("object_ref") or "") == payload_ok["object_ref"], ready_p2

    place_hist_ok = db.fetchone(
        """
        SELECT COUNT(*) AS c
        FROM travel_place_history
        WHERE tenant=%s AND person_id=%s
        """,
        (tenant, person),
    )
    assert int((place_hist_ok or {}).get("c") or 0) > 0, place_hist_ok

    tenant_fail = f"e2e_v126_fail_{uuid4().hex[:8]}"
    day_fail = "2026-03-07"
    decision_fail = svc.plan_for_briefing(tenant=tenant_fail, person_id=person, day_context=_ctx("Geneva"), date_key=day_fail)
    assert decision_fail["status"] in {"dispatched", "existing_spec"}, decision_fail
    spec_fail = db.fetchone(
        """
        SELECT spec_id, cache_key
        FROM travel_video_specs
        WHERE tenant=%s AND person_id=%s AND date_key=%s
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (tenant_fail, person, day_fail),
    )
    assert spec_fail and spec_fail.get("spec_id"), spec_fail
    fail_payload = _browser_job_data(db, tenant=tenant_fail)
    fail_payload.update(
        {
            "status": "failed",
            "spec_id": str(spec_fail["spec_id"]),
            "cache_key": str(spec_fail.get("cache_key") or ""),
            "error": "simulated timeout",
        }
    )
    fail_event_id = _enqueue_browseract_event(
        db,
        tenant=tenant_fail,
        workflow=settings.avomap_browseract_workflow,
        payload=fail_payload,
    )
    assert fail_event_id, "browseract fail event id missing"
    asyncio.run(process_browseract_event(fail_event_id))

    failed_row = db.fetchone("SELECT status FROM travel_video_specs WHERE spec_id=%s", (str(spec_fail["spec_id"]),))
    assert (failed_row or {}).get("status") == "failed", failed_row
    fail_hist = db.fetchone(
        """
        SELECT COUNT(*) AS c
        FROM travel_place_history
        WHERE tenant=%s AND person_id=%s
        """,
        (tenant_fail, person),
    )
    assert int((fail_hist or {}).get("c") or 0) == 0, fail_hist
    p("[E2E][PASS] v1.12.6 avomap webhook->event-worker->finalize/idempotence")


if __name__ == "__main__":
    test_v126_avomap()
