"""Phase 3: post-assignment carpool grouping. Takes assignment.py's roster for each show and
buckets people into cars of up to 3 mutually-within-5km musicians, plus each car's travel cost.

Design decisions carried over from discussion:
- A musician's `transport` tag (car/transit/guardian) is just their default mode absent
  carpooling. Grouping is decided purely by mutual 5km proximity and each adult's own
  `can_drive` flag, never by the tag itself — a "transit" musician can still end up riding in a
  nearby car if it's convenient, since that car is making the trip either way.
- A car carrying an under-17 is always driven by an external guardian, never one of the 60
  musicians — it doesn't consume one of the 3 seats, and under-17 cars are clustered separately
  from adult peer-driven cars.
- "Mutual proximity" is read literally from SPEC.md: every PAIR sharing a car must be within
  5km of each other, not just each within 5km of some single anchor point.
- An adult who can't drive and has nobody nearby who can just takes transit alone — that's not a
  car and isn't counted in car-km, since transit isn't part of the network-cost metric.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from optimizer.data import Data

CARPOOL_MAX_KM = 5.0
CAR_CAPACITY = 3


@dataclass
class Car:
    show_id: str
    musician_ids: list[str]
    driver_id: str | None      # None means an external guardian drives (an under-17 car)
    distance_km: float


@dataclass
class SoloTransit:
    """An adult with nobody nearby who can drive them — not a car, doesn't count toward car-km,
    but still a real trip someone has to make on their own."""
    show_id: str
    musician_id: str
    distance_km: float


def _mutually_close(data: Data, ids: list[str]) -> bool:
    return all(data.distance_between(a, b) <= CARPOOL_MAX_KM
               for i, a in enumerate(ids) for b in ids[i + 1:])


def _greedy_group(data: Data, seed: str, pool: set[str]) -> list[str]:
    """Grow a car starting from `seed`, pulling in the closest still-available candidates
    from `pool` that stay mutually within 5km of everyone already in the group."""
    group = [seed]
    candidates = sorted(pool, key=lambda m: data.distance_between(seed, m))
    for other in candidates:
        if len(group) >= CAR_CAPACITY:
            break
        if _mutually_close(data, group + [other]):
            group.append(other)
    return group


def _cluster_minors(data: Data, minor_ids: list[str], facility_id: str) -> list[Car]:
    remaining = set(minor_ids)
    cars = []
    for seed in sorted(minor_ids, key=lambda m: data.distance_to_facility(m, facility_id)):
        if seed not in remaining:
            continue
        group = _greedy_group(data, seed, remaining - {seed})
        remaining -= set(group)
        dist = sum(data.distance_to_facility(m, facility_id) for m in group) / len(group)
        cars.append(Car(show_id="", musician_ids=group, driver_id=None, distance_km=round(dist, 1)))
    return cars


def _cluster_adults(data: Data, adult_ids: list[str], facility_id: str) -> tuple[list[Car], list[SoloTransit]]:
    can_drive = {m for m in adult_ids if bool(data.musicians.at[m, "can_drive"])}
    remaining = set(adult_ids)
    cars = []
    for driver in sorted(can_drive, key=lambda m: data.distance_to_facility(m, facility_id)):
        if driver not in remaining:
            continue  # already swept up as someone else's passenger
        group = _greedy_group(data, driver, remaining - {driver})
        remaining -= set(group)
        dist = data.distance_to_facility(driver, facility_id)
        cars.append(Car(show_id="", musician_ids=group, driver_id=driver, distance_km=round(dist, 1)))
    solo = [SoloTransit(show_id="", musician_id=m, distance_km=round(data.distance_to_facility(m, facility_id), 1))
            for m in remaining]   # nobody nearby who can drive them
    return cars, solo


def build_carpools(data: Data, assignments: pd.DataFrame) -> tuple[list[Car], list[SoloTransit]]:
    """assignments needs at least show_id, musician_id columns — assignment.py's output shape.
    Returns (cars, solo_transit) — solo_transit is every adult with nobody nearby to drive them;
    not a car, not counted in car-km, but still tracked so nobody just silently disappears."""
    cars, solo_transit = [], []
    shows = data.shows.loc[assignments.show_id.unique()]
    for s in shows.itertuples():
        roster = assignments.loc[assignments.show_id == s.show_id, "musician_id"].tolist()
        ages = data.musicians.loc[roster, "age"]
        minors = [m for m in roster if ages[m] < 17]
        adults = [m for m in roster if ages[m] >= 17]

        minor_cars = _cluster_minors(data, minors, s.facility_id)
        adult_cars, adult_solo = _cluster_adults(data, adults, s.facility_id)

        for car in minor_cars + adult_cars:
            car.show_id = s.show_id
            cars.append(car)
        for solo in adult_solo:
            solo.show_id = s.show_id
            solo_transit.append(solo)
    return cars, solo_transit
