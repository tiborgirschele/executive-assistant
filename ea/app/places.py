from __future__ import annotations
from dataclasses import dataclass
from typing import List
import math, yaml, os
from app.settings import settings

@dataclass(frozen=True)
class Suggestion:
    key: str
    notify_tenant: str
    message: str
    match_shopping_keywords: List[str]
    cooldown_minutes: int

@dataclass(frozen=True)
class Place:
    id: str
    name: str
    lat: float
    lon: float
    radius_m: float
    suggestions: List[Suggestion]

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

def load_places() -> List[Place]:
    data = {}
    if os.path.exists(settings.places_yaml):
        try:
            with open(settings.places_yaml, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                data = {}
        except:
            data = {}
    
    out: List[Place] = []
    for pd in (data.get("places") or []):
        if not isinstance(pd, dict): continue
        suggs: List[Suggestion] = []
        for sd in (pd.get("suggestions") or []):
            if not isinstance(sd, dict): continue
            suggs.append(Suggestion(
                key=str(sd.get("key") or "suggest"),
                notify_tenant=str(sd.get("notify_tenant") or "tibor"),
                message=str(sd.get("message") or ""),
                match_shopping_keywords=[str(x).lower() for x in (sd.get("match_shopping_keywords") or [])],
                cooldown_minutes=int(sd.get("cooldown_minutes") or settings.default_location_cooldown_min),
            ))
        out.append(Place(
            id=str(pd.get("id") or pd.get("name") or "place"),
            name=str(pd.get("name") or pd.get("id") or "place"),
            lat=float(pd.get("lat") or 0.0),
            lon=float(pd.get("lon") or 0.0),
            radius_m=float(pd.get("radius_m") or 250.0),
            suggestions=suggs,
        ))
    return out
