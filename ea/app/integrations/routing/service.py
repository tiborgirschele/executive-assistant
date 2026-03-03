from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from typing import Any


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _extract_city(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return parts[0] if parts else raw[:64]


def _deterministic_coord(seed: str, *, base: float, span: float) -> float:
    v = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) / 4294967295.0
    return round(base + ((v - 0.5) * span), 5)


def resolve_route_stops(
    route_stops: list[dict[str, Any]],
    *,
    home_base: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, stop in enumerate([s for s in route_stops if isinstance(s, dict)]):
        label = str(stop.get("label") or stop.get("location") or "").strip()
        city = str(stop.get("city") or "").strip() or _extract_city(label)
        country = str(stop.get("country") or "").strip()
        lat = _coerce_float(stop.get("lat"))
        lon = _coerce_float(stop.get("lon"))

        if lat is None or lon is None:
            seed = f"{city}|{country}|{idx}|{label}".strip()
            hb_lat = _coerce_float((home_base or {}).get("lat")) if isinstance(home_base, dict) else None
            hb_lon = _coerce_float((home_base or {}).get("lon")) if isinstance(home_base, dict) else None
            # Deterministic fallback "geocoding": bounded around home base if available.
            base_lat = hb_lat if hb_lat is not None else 48.2082
            base_lon = hb_lon if hb_lon is not None else 16.3738
            lat = _deterministic_coord(seed + ":lat", base=base_lat, span=8.0)
            lon = _deterministic_coord(seed + ":lon", base=base_lon, span=8.0)

        out.append(
            {
                "label": label[:120],
                "city": city,
                "country": country,
                "lat": round(float(lat), 5),
                "lon": round(float(lon), 5),
                "place_key": str(stop.get("place_key") or f"{city.lower()}|{country.lower()}").strip(),
            }
        )
    return out


def build_gpx_xml(route_stops: list[dict[str, Any]]) -> str:
    gpx = ET.Element(
        "gpx",
        attrib={
            "version": "1.1",
            "creator": "ea-os",
            "xmlns": "http://www.topografix.com/GPX/1/1",
        },
    )
    trk = ET.SubElement(gpx, "trk")
    ET.SubElement(trk, "name").text = "EA OS Travel Route"
    trkseg = ET.SubElement(trk, "trkseg")
    for stop in [s for s in route_stops if isinstance(s, dict)]:
        lat = _coerce_float(stop.get("lat"))
        lon = _coerce_float(stop.get("lon"))
        if lat is None or lon is None:
            continue
        node = ET.SubElement(trkseg, "trkpt", attrib={"lat": str(lat), "lon": str(lon)})
        if stop.get("label"):
            ET.SubElement(node, "name").text = str(stop.get("label"))
    return ET.tostring(gpx, encoding="unicode")

