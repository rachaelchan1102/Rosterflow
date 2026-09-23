"""Phase 6: the Monte Carlo scenario engine — SPEC.md section 7 ("Scenario planner").

Uniform cancellation probability across every scheduled musician, by explicit design (see
SPEC.md's "no reliability scoring" decision). Nobody is more or less likely to cancel than
anyone else in this model — a per-person reliability score would contradict that outright.

Performance note (PROJECT_PLAN.md's "watch out for" list): 5,000 runs x ~28 shows needs to avoid
pandas .loc/.merge calls inside the hot loop, or it's far too slow to be interactive. So every
show's roster/backup data is pulled out of pandas ONCE into plain numpy arrays before the run
loop starts, and the "who cancels" draws are vectorized across all n_runs at once with numpy
rather than looped in Python.

Recursion note (also from that same list): `backups_needed_for_target` answers "how many
backups would it take to hit a target fill rate?" by calling `simulate_fill_rate` — the plain,
single-scenario simulator — in a loop over candidate backup counts. It never calls itself, and
`simulate_fill_rate` never calls `backups_needed_for_target` either, so there's no risk of the
recursive blowup an earlier version of this project ran into.

Simplifications kept explicit rather than silent:
- Backups activate in rank order (1, 2, 3, ...) rather than re-deriving cancellation.py's live
  pianist-priority reordering per cancellation. backups.py already guarantees a pianist is one
  of the ranked backups whenever one exists, so rank-order activation gets there in the vast
  majority of cases anyway, and re-deriving that logic 5,000 times per show isn't worth the cost
  for a statistical estimate.
- The shortfall ladder's step 4 ("one more backup beyond the named few") isn't modeled — only
  the named backups plus the existing roster's own extra-song room are. That's a rare edge case
  even in the live cancellation flow, and modeling it here would reintroduce exactly the
  pandas-per-event cost this module exists to avoid.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from optimizer.backups import assign_backups
from optimizer.data import MAX_SHOWS_PER_DAY, Data

DEFAULT_CANCEL_P = 1 / 8
DEFAULT_N_RUNS = 5000


@dataclass
class _ShowSimData:
    songs_target: int
    min_musicians: int
    roster_songs: np.ndarray
    roster_max_songs: np.ndarray
    roster_is_pianist: np.ndarray
    backup_typical_songs: np.ndarray
    backup_max_songs: np.ndarray
    backup_is_pianist: np.ndarray


def _build_show_sim_data(data: Data, assignments: pd.DataFrame, backups: pd.DataFrame, show_id: str) -> _ShowSimData:
    s = data.shows.loc[show_id]
    fac = data.facilities.loc[s.facility_id]
    pianist_ids = set(data.musicians[data.musicians.instrument == "piano"].musician_id)

    roster = assignments.loc[assignments.show_id == show_id]
    roster_ids = roster.musician_id.to_numpy()
    roster_max = data.musicians.loc[roster_ids, "max_songs"].to_numpy(dtype=float) if len(roster_ids) else np.array([])

    backup_here = backups.loc[backups.show_id == show_id].sort_values("rank")
    backup_ids = backup_here.musician_id.to_numpy()
    if len(backup_ids):
        backup_typical = data.musicians.loc[backup_ids, "typical_songs"].to_numpy(dtype=float)
        backup_max = data.musicians.loc[backup_ids, "max_songs"].to_numpy(dtype=float)
        backup_is_pianist = np.array([bid in pianist_ids for bid in backup_ids])
    else:
        backup_typical = backup_max = np.array([])
        backup_is_pianist = np.array([], dtype=bool)

    return _ShowSimData(
        songs_target=int(fac.songs_per_show),
        min_musicians=int(fac.min_musicians),
        roster_songs=roster.songs.to_numpy(dtype=float),
        roster_max_songs=roster_max,
        roster_is_pianist=np.array([mid in pianist_ids for mid in roster_ids]),
        backup_typical_songs=backup_typical,
        backup_max_songs=backup_max,
        backup_is_pianist=backup_is_pianist,
    )


def _simulate_show(sim: _ShowSimData, cancellation_p: float, n_runs: int, rng: np.random.Generator) -> float:
    """Vectorized across all n_runs for this one show — no pandas, no per-run Python loop."""
    n_roster = len(sim.roster_songs)
    if n_roster == 0:
        return 0.0

    cancel = rng.random((n_runs, n_roster)) < cancellation_p    # shape (n_runs, n_roster)
    present = ~cancel

    covered_songs = (present * sim.roster_songs).sum(axis=1)
    covered_count = present.sum(axis=1).astype(float)
    pianist_covered = (present & sim.roster_is_pianist).any(axis=1)
    roster_room = (present * (sim.roster_max_songs - sim.roster_songs)).sum(axis=1)

    n_cancelled = cancel.sum(axis=1).astype(float)
    backup_room = np.zeros(n_runs)
    backups_activated = np.zeros(n_runs)

    for rank in range(len(sim.backup_typical_songs)):
        activate = backups_activated < n_cancelled
        covered_songs = covered_songs + activate * sim.backup_typical_songs[rank]
        covered_count = covered_count + activate
        pianist_covered = pianist_covered | (activate & sim.backup_is_pianist[rank])
        backup_room = backup_room + activate * (sim.backup_max_songs[rank] - sim.backup_typical_songs[rank])
        backups_activated = backups_activated + activate

    gap = np.maximum(sim.songs_target - covered_songs, 0)
    covered_songs = covered_songs + np.minimum(gap, roster_room + backup_room)

    filled = (covered_songs >= sim.songs_target) & (covered_count >= sim.min_musicians) & pianist_covered
    return float(filled.mean())


def simulate_fill_rate(data: Data, assignments: pd.DataFrame, backups: pd.DataFrame,
                       show_ids: list[str] | None = None, cancellation_p: float = DEFAULT_CANCEL_P,
                       n_runs: int = DEFAULT_N_RUNS, seed: int | None = None) -> pd.DataFrame:
    """One fill_rate per show, each estimated over n_runs independent Monte Carlo draws."""
    ids = show_ids if show_ids is not None else list(assignments.show_id.unique())
    rng = np.random.default_rng(seed)
    rows = [dict(show_id=show_id,
                 fill_rate=_simulate_show(_build_show_sim_data(data, assignments, backups, show_id),
                                          cancellation_p, n_runs, rng))
            for show_id in ids]
    return pd.DataFrame(rows, columns=["show_id", "fill_rate"])


@dataclass
class NewShowFeasibility:
    """Answers a DIFFERENT question from everything else in this module: not "will an already-
    confirmed show survive cancellations" but "if a care home asks for this date, is it likely
    we could staff it at all" — before any musician has been asked about that specific date."""
    date: str
    probability_fully_staffed: float
    eligible_pool_size: int
    excluded_day_conflict: int    # already committed to another show that exact date
    excluded_over_cap: int        # already at their monthly cap for that month
    excluded_guardian_range: int  # under-17s outside the guardian-distance limit for this facility
    mean_available_count: float
    mean_available_songs: float


def _empirical_weekday_availability_rates(data: Data, weekday: int) -> dict[str, float]:
    """For each musician: of their historical shows that fell on this weekday, what fraction did
    they mark themselves available for? Falls back to their overall historical rate if they've
    never had a historical show on this specific weekday to respond to."""
    hist_shows = data.shows[data.shows.period == "history"]
    hist_shows = hist_shows.assign(weekday=pd.to_datetime(hist_shows["date"]).dt.weekday)
    hist_av = data.availability[data.availability.show_id.isin(hist_shows.index)].merge(
        hist_shows[["weekday"]], left_on="show_id", right_index=True)

    overall_rate = hist_av.groupby("musician_id").available.mean()
    weekday_rate = hist_av[hist_av.weekday == weekday].groupby("musician_id").available.mean()

    rates = {}
    for m in data.musicians.itertuples():
        if m.musician_id in weekday_rate.index:
            rates[m.musician_id] = float(weekday_rate[m.musician_id])
        elif m.musician_id in overall_rate.index:
            rates[m.musician_id] = float(overall_rate[m.musician_id])
        else:
            rates[m.musician_id] = 0.0   # no historical data at all for this musician
    return rates


def estimate_new_show_feasibility(data: Data, assignments: pd.DataFrame, facility_id: str, date: str,
                                  n_runs: int = DEFAULT_N_RUNS, seed: int | None = None) -> NewShowFeasibility:
    """"If a care home asks for `date` at `facility_id`, how likely is it we could staff it?" —
    used BEFORE the date is confirmed and BEFORE musicians have been asked about it, so there's
    no confirmed availability.csv row to read yet. Uses each eligible musician's empirical
    per-weekday availability rate from history instead of a real yes/no answer.

    Hard exclusions come from the schedule that's already confirmed (`assignments`), not from
    randomness: a day conflict or a maxed-out monthly cap makes someone unavailable for real,
    regardless of what their historical pattern says.
    """
    fac = data.facilities.loc[facility_id]
    weekday = pd.Timestamp(date).weekday()
    month = pd.Timestamp(date).to_period("M")
    pianist_ids = set(data.musicians[data.musicians.instrument == "piano"].musician_id)

    same_date_shows = data.shows[data.shows.date == date].index
    day_conflict_ids = set(assignments.loc[assignments.show_id.isin(same_date_shows), "musician_id"])

    assigned_months = pd.to_datetime(data.shows.loc[assignments.show_id, "date"].values).to_period("M")
    played_this_month = assignments.assign(month=assigned_months).groupby(["musician_id", "month"]).size()
    over_cap_ids = {
        m.musician_id for m in data.musicians.itertuples()
        if played_this_month.get((m.musician_id, month), 0) >= int(m.max_shows_per_month)
    }

    guardian_ineligible_ids = {
        m.musician_id for m in data.musicians.itertuples()
        if not data.within_guardian_range(m.musician_id, facility_id)
    }

    excluded = day_conflict_ids | over_cap_ids | guardian_ineligible_ids
    eligible = [m for m in data.musicians.itertuples() if m.musician_id not in excluded]

    rates_by_id = _empirical_weekday_availability_rates(data, weekday)
    rates = np.array([rates_by_id[m.musician_id] for m in eligible])
    typical_songs = np.array([m.typical_songs for m in eligible], dtype=float)
    is_pianist = np.array([m.musician_id in pianist_ids for m in eligible])

    if len(eligible) == 0:
        probability = 0.0
        mean_count = mean_songs = 0.0
    else:
        rng = np.random.default_rng(seed)
        available = rng.random((n_runs, len(eligible))) < rates    # shape (n_runs, len(eligible))
        available_count = available.sum(axis=1)
        available_songs = (available * typical_songs).sum(axis=1)
        has_pianist = (available & is_pianist).any(axis=1)

        fully_staffed = ((available_count >= fac.min_musicians)
                         & (available_songs >= fac.songs_per_show) & has_pianist)
        probability = float(fully_staffed.mean())
        mean_count = float(available_count.mean())
        mean_songs = float(available_songs.mean())

    return NewShowFeasibility(
        date=date, probability_fully_staffed=probability, eligible_pool_size=len(eligible),
        excluded_day_conflict=len(day_conflict_ids),
        excluded_over_cap=len(over_cap_ids), excluded_guardian_range=len(guardian_ineligible_ids),
        mean_available_count=mean_count, mean_available_songs=mean_songs,
    )


def suggest_alternative_dates(data: Data, assignments: pd.DataFrame, facility_id: str, requested_date: str,
                              window_days: int = 14, n_runs: int = 2000, top_n: int = 3,
                              seed: int | None = None) -> list[NewShowFeasibility]:
    """If a care home's requested date looks weak, check nearby dates too (+/- window_days) and
    rank by feasibility. A date already at the org-wide MAX_SHOWS_PER_DAY cap (see data.py) is
    skipped outright, not just deprioritized — adding a 4th show there wouldn't be a valid
    schedule regardless of how good the staffing odds look. The requested date itself is always
    included (offset 0), so "your original date is actually fine" is a possible, valid answer.
    """
    base = pd.Timestamp(requested_date)
    results = []
    for offset in range(-window_days, window_days + 1):
        candidate_date = (base + pd.Timedelta(days=offset)).date().isoformat()
        if (data.shows["date"] == candidate_date).sum() >= MAX_SHOWS_PER_DAY:
            continue
        feas = estimate_new_show_feasibility(data, assignments, facility_id, candidate_date,
                                             n_runs=n_runs, seed=seed)
        results.append((abs(offset), feas))

    results.sort(key=lambda r: (-r[1].probability_fully_staffed, r[0]))
    return [feas for _, feas in results[:top_n]]


def backups_needed_for_target(data: Data, assignments: pd.DataFrame, show_id: str,
                              target_fill_rate: float = 0.95, cancellation_p: float = DEFAULT_CANCEL_P,
                              n_runs: int = 2000, max_backups: int = 8, seed: int | None = None) -> int | None:
    """How many named backups would this ONE show need to clear `target_fill_rate`? Tries 0, 1,
    2, ... backups (re-ranking with assign_backups each time) and calls the plain
    simulate-a-single-scenario helper below directly — never itself — stopping at the first
    count that clears the target. Returns None if even max_backups isn't enough (the honest
    answer, not a crash)."""
    rng = np.random.default_rng(seed)
    for n in range(0, max_backups + 1):
        backup_result = assign_backups(data, assignments, show_ids=[show_id], num_backups=n)
        sim = _build_show_sim_data(data, assignments, backup_result.backups, show_id)
        if _simulate_show(sim, cancellation_p, n_runs, rng) >= target_fill_rate:
            return n
    return None
