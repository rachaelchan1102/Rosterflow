"""Shared geography helpers — kept out of data.py/distances.py so the haversine formula lives
in exactly one place instead of being copy-pasted across every module that needs a distance."""
import numpy as np

STRAIGHT_LINE_ROAD_FACTOR = 1.3   # roads aren't straight lines; a cheap correction for the fallback


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p = np.pi / 180
    a = (np.sin((lat2 - lat1) * p / 2) ** 2
        + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lng2 - lng1) * p / 2) ** 2)
    return 12742 * np.arcsin(np.sqrt(a))


def fallback_road_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return haversine_km(lat1, lng1, lat2, lng2) * STRAIGHT_LINE_ROAD_FACTOR
