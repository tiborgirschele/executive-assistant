from __future__ import annotations

from app.integrations.avomap.specs import TravelVideoSpec
from app.integrations.routing.service import build_gpx_xml
from app.settings import settings


def build_browseract_payload(
    spec: TravelVideoSpec,
    workflow_name: str,
    *,
    spec_id: str,
    cache_key: str,
    job_id: str = "",
    job_token: str = "",
) -> dict:
    route_stops = []
    if isinstance(spec.route_json, dict):
        route_stops = [s for s in (spec.route_json.get("stops") or []) if isinstance(s, dict)]
    gpx_xml = build_gpx_xml(route_stops)
    data = {
        "spec_id": spec_id,
        "cache_key": cache_key,
        "tenant": spec.tenant,
        "person_id": spec.person_id,
        "date_key": spec.date_key,
        "mode": spec.mode,
        "orientation": spec.orientation,
        "duration_target_sec": spec.duration_target_sec,
        "route_json": spec.route_json,
        "markers_json": spec.markers_json,
        # Preferred path: GPX/KML import mode for deterministic route setup.
        "import_mode": "gpx_kml_preferred",
        "gpx_payload": gpx_xml,
        "max_runtime_sec": int(settings.avomap_browseract_timeout_sec),
    }
    if job_id:
        data["job_id"] = job_id
    if job_token:
        data["job_token"] = job_token
    return {
        "platform": "avomap",
        "task": "render_trip_video",
        "workflow": workflow_name,
        "headless": True,
        "data": data,
    }
