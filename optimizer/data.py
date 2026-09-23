"""Data layer: load, validate, and serve the inputs every other layer needs.

Nothing above this file (assignment/carpool/backups/simulate/metrics, the UI) reads a CSV or a
SQL row directly — they all take a `Data` object and call its lookup methods. That's the whole
point of this layer: swapping CSVs for Neon later (phase 7.5) means changing `load_from_csv`
into a `load_from_db`, not touching anything downstream.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {
    "facilities": ["facility_id", "display_name", "region", "lat", "lng", "show_duration_min",
                   "songs_per_show", "target_musicians", "min_musicians", "max_musicians",
                   "has_piano_onsite", "preferred_slot"],
    "musicians": ["musician_id", "display_name", "age", "instrument", "home_region", "home_lat",
                  "home_lng", "transport", "can_drive", "years_with_org", "max_shows_per_month",
                  "min_songs", "typical_songs", "max_songs"],
    "shows": ["show_id", "facility_id", "date", "start_time", "duration_min", "period"],
    "availability": ["musician_id", "show_id", "available"],
    "weekly_availability": ["musician_id", "weekday", "start_time", "end_time"],
    "distances": ["musician_id", "facility_id", "distance_km"],
    "musician_distances": ["m1", "m2", "km"],
    "history_assignments": ["show_id", "musician_id", "planned_set_min", "status", "actual_set_min"],
}
GUARDIAN_MAX_KM_DEFAULT = 35
MAX_SHOWS_PER_DAY = 3   # org-wide limit — no more than 3 facilities can run a show on the same date


class DataValidationError(ValueError):
    """Raised with every problem found, not just the first, so a bad CSV can be fixed in one pass."""


def _hav_km(lat1, lng1, lat2, lng2):
    p = np.pi / 180
    a = (np.sin((lat2 - lat1) * p / 2) ** 2
         + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lng2 - lng1) * p / 2) ** 2)
    return 12742 * np.arcsin(np.sqrt(a))


def load_from_csv(csv_dir: str | Path) -> "Data":
    csv_dir = Path(csv_dir)
    raw = {name: pd.read_csv(csv_dir / f"{name}.csv") for name in REQUIRED_COLUMNS}
    problems = _validate(raw)
    if problems:
        raise DataValidationError("\n".join(problems))
    raw["distances"] = _fill_missing_musician_facility_distances(raw["musicians"], raw["facilities"], raw["distances"])
    raw["musician_distances"] = _fill_missing_musician_musician_distances(raw["musicians"], raw["musician_distances"])
    return Data(
        facilities=raw["facilities"].set_index("facility_id", drop=False),
        musicians=raw["musicians"].set_index("musician_id", drop=False),
        shows=raw["shows"].set_index("show_id", drop=False),
        availability=raw["availability"],
        weekly_availability=raw["weekly_availability"],
        musician_facility_km=raw["distances"],
        musician_musician_km=raw["musician_distances"],
        history_assignments=raw["history_assignments"],
    )


def _validate(raw: dict[str, pd.DataFrame]) -> list[str]:
    problems = []

    for name, cols in REQUIRED_COLUMNS.items():
        missing = [c for c in cols if c not in raw[name].columns]
        if missing:
            problems.append(f"{name}.csv is missing required columns: {missing}")
    if problems:
        return problems  # column checks must pass before anything below can safely run

    for name, key in [("facilities", "facility_id"), ("musicians", "musician_id"), ("shows", "show_id")]:
        dupes = raw[name][key][raw[name][key].duplicated()].unique().tolist()
        if dupes:
            problems.append(f"{name}.csv has duplicate {key}: {dupes}")

    dupe_av = raw["availability"][raw["availability"].duplicated(["musician_id", "show_id"])]
    if not dupe_av.empty:
        problems.append(f"availability.csv has duplicate (musician_id, show_id) rows: {len(dupe_av)} found")

    shows_per_day = raw["shows"].groupby("date").size()
    overloaded_days = shows_per_day[shows_per_day > MAX_SHOWS_PER_DAY]
    if not overloaded_days.empty:
        problems.append(f"shows.csv has more than {MAX_SHOWS_PER_DAY} shows on a single date "
                        f"(org-wide limit): {overloaded_days.to_dict()}")

    musician_ids = set(raw["musicians"]["musician_id"])
    facility_ids = set(raw["facilities"]["facility_id"])
    show_ids = set(raw["shows"]["show_id"])

    fk_checks = [
        ("shows", "facility_id", facility_ids, "facilities"),
        ("availability", "musician_id", musician_ids, "musicians"),
        ("availability", "show_id", show_ids, "shows"),
        ("weekly_availability", "musician_id", musician_ids, "musicians"),
        ("distances", "musician_id", musician_ids, "musicians"),
        ("distances", "facility_id", facility_ids, "facilities"),
        ("history_assignments", "musician_id", musician_ids, "musicians"),
        ("history_assignments", "show_id", show_ids, "shows"),
    ]
    for table, col, valid_ids, ref in fk_checks:
        bad = set(raw[table][col]) - valid_ids
        if bad:
            problems.append(f"{table}.csv has {col} values not found in {ref}.csv: {sorted(bad)[:10]}")

    bad_m1 = set(raw["musician_distances"]["m1"]) - musician_ids
    bad_m2 = set(raw["musician_distances"]["m2"]) - musician_ids
    if bad_m1 or bad_m2:
        problems.append(f"musician_distances.csv has musician_id values not found in musicians.csv: "
                        f"{sorted(bad_m1 | bad_m2)[:10]}")

    bad_available = set(raw["availability"]["available"].unique()) - {0, 1}
    if bad_available:
        problems.append(f"availability.csv 'available' column must be 0/1, found: {bad_available}")

    bad_status = set(raw["history_assignments"]["status"].unique()) - {"attended", "late_cancel", "no_show"}
    if bad_status:
        problems.append(f"history_assignments.csv 'status' must be attended/late_cancel/no_show, found: {bad_status}")

    return problems


def _fill_missing_musician_facility_distances(musicians: pd.DataFrame, facilities: pd.DataFrame,
                                               distances: pd.DataFrame) -> pd.DataFrame:
    have = set(zip(distances["musician_id"], distances["facility_id"]))
    missing_rows = []
    for m in musicians.itertuples():
        for f in facilities.itertuples():
            if (m.musician_id, f.facility_id) not in have:
                km = round(float(_hav_km(m.home_lat, m.home_lng, f.lat, f.lng)) * 1.3, 1)
                missing_rows.append(dict(musician_id=m.musician_id, facility_id=f.facility_id, distance_km=km))
    if not missing_rows:
        return distances
    return pd.concat([distances, pd.DataFrame(missing_rows)], ignore_index=True)


def _fill_missing_musician_musician_distances(musicians: pd.DataFrame, musician_distances: pd.DataFrame) -> pd.DataFrame:
    have = set(zip(musician_distances["m1"], musician_distances["m2"]))
    missing_rows = []
    ms = list(musicians.itertuples())
    for i, a in enumerate(ms):
        for b in ms[i + 1:]:
            if (a.musician_id, b.musician_id) not in have:
                km = round(float(_hav_km(a.home_lat, a.home_lng, b.home_lat, b.home_lng)) * 1.3, 1)
                missing_rows.append(dict(m1=a.musician_id, m2=b.musician_id, km=km))
                missing_rows.append(dict(m1=b.musician_id, m2=a.musician_id, km=km))
    if not missing_rows:
        return musician_distances
    return pd.concat([musician_distances, pd.DataFrame(missing_rows)], ignore_index=True)


@dataclass
class Data:
    facilities: pd.DataFrame
    musicians: pd.DataFrame
    shows: pd.DataFrame
    availability: pd.DataFrame
    weekly_availability: pd.DataFrame
    musician_facility_km: pd.DataFrame
    musician_musician_km: pd.DataFrame
    history_assignments: pd.DataFrame

    def __post_init__(self):
        self._available = {(r.musician_id, r.show_id): bool(r.available) for r in self.availability.itertuples()}
        self._m_to_f_km = {(r.musician_id, r.facility_id): r.distance_km for r in self.musician_facility_km.itertuples()}
        self._m_to_m_km = {(r.m1, r.m2): r.km for r in self.musician_musician_km.itertuples()}

    def is_available(self, musician_id: str, show_id: str) -> bool:
        return self._available.get((musician_id, show_id), False)

    def distance_to_facility(self, musician_id: str, facility_id: str) -> float:
        return self._m_to_f_km[(musician_id, facility_id)]

    def distance_between(self, musician_id_a: str, musician_id_b: str) -> float:
        if musician_id_a == musician_id_b:
            return 0.0
        return self._m_to_m_km[(musician_id_a, musician_id_b)]

    def within_guardian_range(self, musician_id: str, facility_id: str, max_km: float = GUARDIAN_MAX_KM_DEFAULT) -> bool:
        age = self.musicians.at[musician_id, "age"]
        if age >= 17:
            return True
        return self.distance_to_facility(musician_id, facility_id) <= max_km
