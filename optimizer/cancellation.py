"""Phase 5: cancellation handling — SPEC.md section 8 (the shortfall ladder) and section 9.

This does NOT re-run the CP-SAT solve. A cancellation usually comes ~2 days out, and the whole
point of planning shows at normal size with 3 named backups (rather than overstaffing everyone)
is that a single dropout is a fast, local fix — the same step-by-step ladder a coordinator would
work through by hand, not a from-scratch re-optimization:
  1. Drop the cancelled musician from the roster.
  2. Activate the show's named backups in rank order — but re-check eligibility live, since
     availability can genuinely shift in the days between planning and showtime — and override
     rank order if the cancelled musician was the show's only pianist and the top available
     backup isn't one, since losing pianist coverage is the one thing that must be fixed first.
  3. If songs are still short of target, ask musicians already on the show to add a song or two
     (spread toward whoever has the most learnable room left, tie-broken toward more experience —
     SPEC.md section 6 — never just the same people every time).
  4. If still short, look for one more backup beyond the original 3.
  5. If it's still short after all of that, flag it as needing attention. That's an expected,
     legitimate outcome of the ladder, not a failure state.

The activated backup always plays their OWN normal set (typical_songs) — never a clone of the
cancelled person's songs. That's a deliberate SPEC.md decision: with ~2 days' notice, nobody is
learning someone else's exact set, so the show's total song count can genuinely change.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from optimizer.data import Data


@dataclass
class CancellationPlan:
    show_id: str
    cancelled_musician_id: str
    activated_backup_id: str | None
    extra_song_requests: list[tuple[str, int]] = field(default_factory=list)   # (musician_id, extra songs)
    # A suggestion only — NOT counted in the totals below, since the coordinator has to opt in.
    additional_backup_id: str | None = None
    additional_backup_songs: int = 0
    additional_backup_is_pianist: bool = False
    # Totals after the backup (if any) and the extra-song requests — without the suggestion.
    songs_covered: int = 0
    songs_target: int = 0
    musician_count: int = 0
    has_pianist: bool = False
    needs_attention: bool = False


def handle_cancellation(data: Data, assignments: pd.DataFrame, backups: pd.DataFrame,
                        show_id: str, cancelled_musician_id: str,
                        backup_choice: str = "auto") -> CancellationPlan:
    """`backup_choice`: "auto" follows the ranked-backup rules below; "none" skips straight to
    extra songs; any other value is the musician_id the coordinator picked themselves, which
    must still be free that day (raises ValueError otherwise)."""
    s = data.shows.loc[show_id]
    fac = data.facilities.loc[s.facility_id]
    pianist_ids = set(data.musicians[data.musicians.instrument == "piano"].musician_id)
    songs_target = int(fac.songs_per_show)

    roster = assignments.loc[(assignments.show_id == show_id)
                             & (assignments.musician_id != cancelled_musician_id),
                             ["musician_id", "songs"]].copy()

    same_day_shows = data.shows[data.shows.date == s.date].index
    playing_today = set(assignments.loc[assignments.show_id.isin(same_day_shows), "musician_id"]) \
        - {cancelled_musician_id}

    still_has_pianist = bool(set(roster.musician_id) & pianist_ids)
    ranked_backups = backups.loc[backups.show_id == show_id].sort_values("rank")

    def eligible(musician_id: str) -> bool:
        return musician_id not in playing_today and data.is_available(musician_id, show_id)

    if backup_choice == "none":
        activated = None
    elif backup_choice != "auto":
        if backup_choice == cancelled_musician_id or backup_choice in set(roster.musician_id):
            raise ValueError(f"{backup_choice} is already on this show")
        if not eligible(backup_choice):
            raise ValueError(f"{backup_choice} isn't free for this show")
        activated = backup_choice
    else:
        # Prefer backups with room left under their monthly cap; only fall back to someone at
        # their cap when nobody else on the list is free (the cap is a release valve, not a wall).
        month = str(s.date)[:7]
        this_month = set(data.shows.index[data.shows.date.astype(str).str.startswith(month)])
        month_counts = assignments[assignments.show_id.isin(this_month)].groupby("musician_id").size()

        def under_cap(musician_id: str) -> bool:
            return int(month_counts.get(musician_id, 0)) < int(data.musicians.at[musician_id, "max_shows_per_month"])

        free = [b.musician_id for b in ranked_backups.itertuples() if eligible(b.musician_id)]
        candidates = [m for m in free if under_cap(m)] or free
        activated = candidates[0] if candidates else None
        if not still_has_pianist and activated is not None and activated not in pianist_ids:
            # Losing the only pianist outranks the cap: an at-cap pianist beats an under-cap non-pianist.
            activated = next((m for m in candidates + free if m in pianist_ids), activated)

    if activated is not None:
        typical = int(data.musicians.at[activated, "typical_songs"])
        roster = pd.concat([roster, pd.DataFrame([dict(musician_id=activated, songs=typical)])],
                           ignore_index=True)

    covered = int(roster.songs.sum())
    gap = songs_target - covered
    extra_requests: list[tuple[str, int]] = []
    additional_backup_id = None

    if gap > 0:
        candidates = roster.merge(data.musicians[["max_songs", "years_with_org"]],
                                  left_on="musician_id", right_index=True)
        candidates["room"] = candidates.max_songs - candidates.songs
        candidates = candidates[candidates.room > 0].sort_values(
            ["room", "years_with_org"], ascending=[False, False])
        for c in candidates.itertuples():
            if gap <= 0:
                break
            add = min(int(c.room), gap)
            extra_requests.append((c.musician_id, add))
            covered += add
            gap -= add

    if gap > 0:
        played_count = assignments.groupby("musician_id").size().to_dict()
        # the cancelled musician must never be re-suggested as their own replacement — availability
        # data has no idea they just cancelled, so this has to be excluded explicitly here.
        used_ids = set(roster.musician_id) | set(ranked_backups.musician_id) | {cancelled_musician_id}
        pool = [m for m in data.musicians.itertuples()
               if m.musician_id not in used_ids and eligible(m.musician_id)
               and data.within_guardian_range(m.musician_id, s.facility_id)]
        pool.sort(key=lambda m: (played_count.get(m.musician_id, 0),
                                 data.distance_to_facility(m.musician_id, s.facility_id)))
        if pool:
            additional_backup_id = pool[0].musician_id

    musician_count = len(roster)
    has_pianist = still_has_pianist or (activated in pianist_ids)

    return CancellationPlan(
        show_id=show_id, cancelled_musician_id=cancelled_musician_id, activated_backup_id=activated,
        extra_song_requests=extra_requests, additional_backup_id=additional_backup_id,
        additional_backup_songs=(int(data.musicians.at[additional_backup_id, "typical_songs"])
                                 if additional_backup_id else 0),
        additional_backup_is_pianist=additional_backup_id in pianist_ids,
        songs_covered=covered, songs_target=songs_target, musician_count=musician_count,
        has_pianist=has_pianist,
        needs_attention=(covered < songs_target or musician_count < int(fac.min_musicians) or not has_pianist),
    )
