"""OSRM road-distance lookups, with a haversine fallback and a persistent cache — part of
phase 7.5's data layer rework (see PROJECT_PLAN.md).

Only the real deployment uses OSRM. The playground's synthetic coordinates don't sit on real
roads, so a live road-routing lookup for them wouldn't mean anything — playground mode always
takes the haversine fallback directly (`use_osrm=False`), never touches the network.

OSRM's public demo server is free but not something to hammer: every lookup is cached, and any
failure (network error, timeout, bad response) falls back to haversine x1.3 instead of raising —
a temporarily-unreachable distance server should never be the reason a solve fails.
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

from optimizer.geo import fallback_road_distance_km

OSRM_BASE_URL = "https://router.project-osrm.org"
OSRM_TIMEOUT_S = 5
CACHE_COORD_PRECISION = 4   # ~11m — coordinate pairs this close share one cache entry


class DistanceCache:
    """A small persistent cache so the same OSRM lookup is never paid for twice. Backed by a
    JSON file for now — this is exactly the kind of state that moves into a Neon table once that
    layer exists (phase 7.5's next piece), without changing anything that calls get_distance_km.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data: dict[str, float] = json.loads(self.path.read_text()) if self.path.exists() else {}

    @staticmethod
    def _key(lat1: float, lng1: float, lat2: float, lng2: float) -> str:
        r = CACHE_COORD_PRECISION
        a, b = (round(lat1, r), round(lng1, r)), (round(lat2, r), round(lng2, r))
        a, b = min(a, b), max(a, b)   # order-independent: A->B is the same trip as B->A
        return f"{a[0]},{a[1]}|{b[0]},{b[1]}"

    def get(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float | None:
        return self._data.get(self._key(lat1, lng1, lat2, lng2))

    def set(self, lat1: float, lng1: float, lat2: float, lng2: float, distance_km: float) -> None:
        self._data[self._key(lat1, lng1, lat2, lng2)] = distance_km

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data))


def _osrm_distance_km(lat1: float, lng1: float, lat2: float, lng2: float,
                      timeout: float = OSRM_TIMEOUT_S) -> float | None:
    """A single real-road distance from OSRM's public demo server. Returns None on any failure —
    the caller falls back to haversine, this never raises."""
    url = f"{OSRM_BASE_URL}/route/v1/driving/{lng1},{lat1};{lng2},{lat2}"
    try:
        resp = requests.get(url, params={"overview": "false"}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        return round(data["routes"][0]["distance"] / 1000, 1)   # meters -> km
    except (requests.RequestException, KeyError, ValueError, IndexError):
        return None


def get_distance_km(lat1: float, lng1: float, lat2: float, lng2: float,
                    use_osrm: bool = True, cache: DistanceCache | None = None) -> float:
    """The one entry point everything else should call — never queries OSRM directly."""
    if not use_osrm:
        return round(fallback_road_distance_km(lat1, lng1, lat2, lng2), 1)

    if cache is not None:
        cached = cache.get(lat1, lng1, lat2, lng2)
        if cached is not None:
            return cached

    km = _osrm_distance_km(lat1, lng1, lat2, lng2)
    if km is None:
        km = round(fallback_road_distance_km(lat1, lng1, lat2, lng2), 1)

    if cache is not None:
        cache.set(lat1, lng1, lat2, lng2, km)
    return km
