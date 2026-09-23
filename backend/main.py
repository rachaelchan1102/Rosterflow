"""FastAPI backend — wraps the optimizer package behind HTTP endpoints. Nothing in
optimizer/data.py through optimizer/metrics.py changes for this; every endpoint here just calls
those functions and shapes the result as JSON for the React frontend.

Runs against the playground's synthetic CSVs for now; swapping load_from_csv for load_from_db
(optimizer/data.py) is how a real deployment would read from Neon instead — nothing else here
would need to change.
"""
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from optimizer.assignment import solve_assignment
from optimizer.backups import assign_backups
from optimizer.carpool import build_carpools
from optimizer.data import Data, RecordConflictError, delete_musician
from optimizer.metrics import compute_kpis, exceptions_queue
from optimizer.playground import PlaygroundStore
from optimizer.simulate import DEFAULT_CANCEL_P, estimate_new_show_feasibility, simulate_fill_rate, suggest_alternative_dates

SAMPLE_DATA_DIR = Path(__file__).resolve().parent.parent / "sample_data"

app = FastAPI(title="Multi-Site Staffing & Routing Optimizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],   # the Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

# One in-memory store for the whole demo session — every endpoint reads/writes this same
# PlaygroundStore, so an edit in the working-tools screen is what the control tower and
# scenario planner actually see on their next request. Real deployment would swap this for a
# Data object loaded from Neon (optimizer/data.py's load_from_db) — nothing else here changes.
store = PlaygroundStore.fresh(SAMPLE_DATA_DIR)

_cache: dict = {}


def _invalidate_cache() -> None:
    """Called after any CRUD write succeeds — the next control-tower/scenario request re-solves
    against the store's new state instead of serving a stale cached schedule."""
    _cache.clear()


def _run_pipeline(data: Data) -> dict:
    """Solve + carpool + backups + metrics for a given Data — the one thing every endpoint
    that needs a fresh schedule (control tower, a what-if scenario) goes through."""
    result = solve_assignment(data, time_limit_s=20)
    cars, solo_transit = build_carpools(data, result.assignments)
    backup_result = assign_backups(data, result.assignments)
    kpis = compute_kpis(data, result, cars, solo_transit, backup_result)
    queue = exceptions_queue(result, backup_result)
    return dict(data=data, assignments=result.assignments, backups=backup_result.backups,
               kpis=kpis, queue=queue)


def _load_and_solve() -> dict:
    """Computed once and cached in memory — a CP-SAT solve takes ~15-20s, so this shouldn't run
    on every request. Cleared by _invalidate_cache() after any CRUD write succeeds, so an edit is
    reflected on the next request instead of serving a stale schedule."""
    if "result" not in _cache:
        _cache["result"] = _run_pipeline(store.data)
    return _cache["result"]


def _weekly_capacity(data: Data) -> list[dict]:
    shows = data.shows[data.shows.period == "upcoming"].copy()
    shows["week"] = pd.to_datetime(shows["date"]).dt.to_period("W").astype(str)

    needed = shows.join(data.facilities[["target_musicians"]], on="facility_id") \
                 .groupby("week")["target_musicians"].sum()
    avail_counts = data.availability[data.availability.available == 1].groupby("show_id").size()
    shows["avail_count"] = shows.index.map(avail_counts).fillna(0)
    available = shows.groupby("week")["avail_count"].sum()

    weekly = pd.DataFrame({"needed": needed, "available": available}).fillna(0)
    return [dict(week=week, needed=int(row.needed), available=int(row.available))
            for week, row in weekly.iterrows()]


@app.get("/api/health")
def health():
    return {"status": "ok"}


def _kpis_to_dict(kpis) -> dict:
    return {
        "fill_rate": kpis.fill_rate,
        "backup_coverage": kpis.backup_coverage,
        "capacity_utilization_mean": kpis.capacity_utilization_mean,
        "capacity_utilization_spread": kpis.capacity_utilization_spread,
        "total_cars": kpis.total_cars,
        "total_car_km": kpis.total_car_km,
        "guardian_car_km": kpis.guardian_car_km,
        "peer_car_km": kpis.peer_car_km,
        "car_km_savings": kpis.car_km_savings,
        "solo_transit_count": kpis.solo_transit_count,
        "rotation_repeat_rate": kpis.rotation_repeat_rate,
    }


@app.get("/api/control-tower")
def control_tower():
    computed = _load_and_solve()
    queue, data = computed["queue"], computed["data"]

    return {
        "kpis": _kpis_to_dict(computed["kpis"]),
        "exceptions": [
            {
                "show_id": row.show_id,
                "musician_count": int(row.musician_count),
                "backup_count": int(row.backup_count),
                "fully_staffed": bool(row.fully_staffed),
                "backup_ready": bool(row.backup_ready),
            }
            for row in queue.itertuples()
        ],
        "weekly_capacity": _weekly_capacity(data),
    }


class ScenarioRequest(BaseModel):
    cancellation_p: float = DEFAULT_CANCEL_P
    remove_musicians: int = 0


@app.post("/api/scenario")
def scenario(req: ScenarioRequest):
    """SPEC.md 12.2's what-if screen: re-run under changed conditions, compare against the
    baseline. `remove_musicians` triggers a real re-solve (a smaller pool changes who's
    available to play at all); `cancellation_p` alone just re-runs the fast Monte Carlo
    simulator against whichever schedule resulted — no need to re-solve for that alone."""
    baseline = _load_and_solve()

    if req.remove_musicians > 0:
        rng = np.random.default_rng(42)   # same N always removes the same people, for repeatable comparisons
        ids_to_remove = rng.choice(baseline["data"].musicians.index, size=min(req.remove_musicians, 55), replace=False)
        scenario_data = baseline["data"]
        for musician_id in ids_to_remove:
            scenario_data = delete_musician(scenario_data, musician_id)
        computed = _run_pipeline(scenario_data)
    else:
        computed = baseline

    baseline_fill = simulate_fill_rate(baseline["data"], baseline["assignments"], baseline["backups"],
                                       cancellation_p=req.cancellation_p, n_runs=3000, seed=1)
    scenario_fill = simulate_fill_rate(computed["data"], computed["assignments"], computed["backups"],
                                       cancellation_p=req.cancellation_p, n_runs=3000, seed=1)

    baseline_kpis = _kpis_to_dict(baseline["kpis"])
    baseline_kpis["fill_rate"] = float(baseline_fill.fill_rate.mean())
    scenario_kpis = _kpis_to_dict(computed["kpis"])
    scenario_kpis["fill_rate"] = float(scenario_fill.fill_rate.mean())

    return {"baseline": baseline_kpis, "scenario": scenario_kpis}


class FeasibilityRequest(BaseModel):
    facility_id: str
    date: str


def _feasibility_to_dict(feas) -> dict:
    return {
        "date": feas.date,
        "probability_fully_staffed": feas.probability_fully_staffed,
        "eligible_pool_size": feas.eligible_pool_size,
        "excluded_day_conflict": feas.excluded_day_conflict,
        "excluded_over_cap": feas.excluded_over_cap,
        "excluded_guardian_range": feas.excluded_guardian_range,
        "mean_available_count": feas.mean_available_count,
        "mean_available_songs": feas.mean_available_songs,
    }


@app.post("/api/feasibility")
def feasibility(req: FeasibilityRequest):
    """"If a care home asks for this date, how likely is it we could staff it?" (SPEC.md's
    pre-commitment question — see simulate.py). Uses the CURRENT store state, so it correctly
    accounts for whatever's already been added/edited in the working tools screen."""
    baseline = _load_and_solve()
    requested = estimate_new_show_feasibility(baseline["data"], baseline["assignments"],
                                              req.facility_id, req.date, n_runs=3000, seed=1)
    alternatives = suggest_alternative_dates(baseline["data"], baseline["assignments"], req.facility_id,
                                             req.date, window_days=14, n_runs=1500, top_n=3, seed=1)
    return {
        "requested": _feasibility_to_dict(requested),
        "alternatives": [_feasibility_to_dict(a) for a in alternatives],
    }


# ---------------------------------------------------------------------------
# Working tools: add/edit/delete musicians and shows. Every write goes through
# optimizer.playground.PlaygroundStore, which itself goes through data.py's CRUD functions —
# the exact same validation a full CSV load is checked with. A rejected write here becomes a
# plain-language 400, not a raw stack trace (SPEC.md 12.3's "usable by a non-coder").
# ---------------------------------------------------------------------------

class MusicianIn(BaseModel):
    musician_id: str
    display_name: str
    age: int
    instrument: str
    home_region: str
    home_lat: float
    home_lng: float
    transport: str
    can_drive: bool
    years_with_org: float
    max_shows_per_month: int
    min_songs: int
    typical_songs: int
    max_songs: int


class ShowIn(BaseModel):
    show_id: str
    facility_id: str
    date: str
    start_time: str
    duration_min: int
    period: str = "upcoming"


def _records(df: pd.DataFrame) -> list[dict]:
    return df.reset_index(drop=True).to_dict(orient="records")


@app.get("/api/musicians")
def list_musicians():
    return _records(store.data.musicians)


@app.post("/api/musicians")
def create_musician(musician: MusicianIn):
    try:
        store.add_musician(musician.model_dump())
    except RecordConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _invalidate_cache()
    return {"status": "ok"}


@app.get("/api/musicians/{musician_id}/availability")
def get_musician_availability(musician_id: str):
    wa = store.data.weekly_availability
    return _records(wa[wa.musician_id == musician_id][["weekday", "start_time", "end_time"]])


@app.put("/api/musicians/{musician_id}/availability")
def set_musician_availability(musician_id: str, windows: list[dict[str, Any]] = Body(...)):
    try:
        store.set_weekly_availability(musician_id, windows)
    except RecordConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _invalidate_cache()
    return {"status": "ok"}


@app.put("/api/musicians/{musician_id}")
def update_musician_endpoint(musician_id: str, changes: dict[str, Any] = Body(...)):
    try:
        store.update_musician(musician_id, changes)
    except RecordConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _invalidate_cache()
    return {"status": "ok"}


@app.delete("/api/musicians/{musician_id}")
def delete_musician_endpoint(musician_id: str):
    try:
        store.delete_musician(musician_id)
    except RecordConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _invalidate_cache()
    return {"status": "ok"}


@app.get("/api/shows")
def list_shows():
    return _records(store.data.shows)


@app.get("/api/facilities")
def list_facilities():
    return _records(store.data.facilities)


@app.post("/api/shows")
def create_show(show: ShowIn):
    try:
        store.add_show(show.model_dump())
    except RecordConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _invalidate_cache()
    return {"status": "ok"}


@app.put("/api/shows/{show_id}")
def update_show_endpoint(show_id: str, changes: dict[str, Any] = Body(...)):
    try:
        store.update_show(show_id, changes)
    except RecordConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _invalidate_cache()
    return {"status": "ok"}


@app.delete("/api/shows/{show_id}")
def delete_show_endpoint(show_id: str):
    try:
        store.delete_show(show_id)
    except RecordConflictError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _invalidate_cache()
    return {"status": "ok"}
