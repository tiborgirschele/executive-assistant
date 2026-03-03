from __future__ import annotations

import hashlib
import math
from typing import Any


HOME_KEYWORDS = ("home", "residence", "private", "villa", "apartment")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _is_home_stop(stop: dict[str, Any], home_base: dict[str, Any] | None) -> bool:
    text = " ".join(
        str(stop.get(k) or "")
        for k in ("label", "place_key", "city", "country")
    ).lower()
    if any(k in text for k in HOME_KEYWORDS):
        return True
    if not isinstance(home_base, dict):
        return False
    try:
        hb_lat = float(home_base.get("lat"))
        hb_lon = float(home_base.get("lon"))
        st_lat = float(stop.get("lat"))
        st_lon = float(stop.get("lon"))
        return _haversine_km(hb_lat, hb_lon, st_lat, st_lon) <= 2.0
    except Exception:
        return False


def _fuzz_coords(lat: float, lon: float, *, seed: str) -> tuple[float, float]:
    # Deterministic ~2-4km shift away from exact private location.
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    lat_jitter = ((int(digest[:4], 16) / 65535.0) - 0.5) * 0.045
    lon_jitter = ((int(digest[4:8], 16) / 65535.0) - 0.5) * 0.045
    return round(lat + lat_jitter, 5), round(lon + lon_jitter, 5)


def sanitize_route_for_export(
    route_stops: list[dict[str, Any]],
    *,
    home_base: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    stops = [s for s in route_stops if isinstance(s, dict)]
    n = len(stops)
    for idx, stop in enumerate(stops):
        label = "Stop"
        if n == 1:
            label = "Destination"
        elif idx == 0:
            label = "Origin"
        elif idx == n - 1:
            label = "Destination"
        else:
            label = f"Stop {idx}"

        item = {
            "label": label,
            "city": str(stop.get("city") or "").strip(),
            "country": str(stop.get("country") or "").strip(),
            "place_key": str(stop.get("place_key") or "").strip(),
        }

        lat = stop.get("lat")
        lon = stop.get("lon")
        try:
            if lat is not None and lon is not None:
                lat_f = float(lat)
                lon_f = float(lon)
                if _is_home_stop(stop, home_base):
                    seed = f"{item['city']}|{item['country']}|{idx}"
                    lat_f, lon_f = _fuzz_coords(lat_f, lon_f, seed=seed)
                item["lat"] = round(lat_f, 5)
                item["lon"] = round(lon_f, 5)
        except Exception:
            pass

        sanitized.append(item)
    return sanitized

