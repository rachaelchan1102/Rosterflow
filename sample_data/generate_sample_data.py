"""Synthetic, anonymized sample data matching spec v0.9. No real people or facilities.
No reliability/attendance history is generated — the tool doesn't score anyone on attendance.
history_assignments.csv records what a manual/simulated process did in the past; it's optional
input, only used later for a rough before/after baseline, never for scoring musicians.
Run: python sample_data/generate_sample_data.py
"""
from datetime import date, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path(__file__).parent
rng = np.random.default_rng(42)
N_MUSICIANS = 60
HISTORY_MONTHS = [(2026, 3), (2026, 4), (2026, 5), (2026, 6), (2026, 7), (2026, 8)]
UPCOMING_MONTHS = [(2026, 10), (2026, 11)]   # two months so the scenario planner has room to work

REGIONS = {
    "Toronto-Downtown": (43.65, -79.38), "North York": (43.76, -79.41), "Scarborough": (43.77, -79.26),
    "Etobicoke": (43.65, -79.52), "Mississauga": (43.59, -79.64), "Vaughan": (43.84, -79.51),
    "Markham": (43.86, -79.33), "Richmond Hill": (43.88, -79.44), "Oakville": (43.45, -79.68),
    "Pickering": (43.84, -79.09), "Brampton": (43.73, -79.76),
}
FAC_REGIONS = ["Toronto-Downtown", "North York", "Scarborough", "Etobicoke", "Mississauga", "Markham", "Vaughan"]

WEEKDAY_NUM = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
MAX_SHOWS_PER_DAY = 3   # a real org-wide limit — no more than 3 facilities' shows can share one date
# Not every show is a weekend matinee — some facilities run weekday evening slots instead.
WEEKDAY_TIME_OPTIONS = {"Sat": ["14:00", "11:00"], "Sun": ["15:00", "14:00"],
                        "Wed": ["18:30"], "Thu": ["18:30"], "Tue": ["18:30"]}
# A pool with each weekday repeated MAX_SHOWS_PER_DAY times: sampling without replacement means
# no weekday can be handed to more than MAX_SHOWS_PER_DAY facilities, so no calendar date they
# generate shows on can ever end up with more than that many shows.
_weekday_pool = [wd for wd in WEEKDAY_TIME_OPTIONS for _ in range(MAX_SHOWS_PER_DAY)]


def jitter(ll, s):
    return round(ll[0] + rng.normal(0, s), 4), round(ll[1] + rng.normal(0, s), 4)


def hav(lat1, lng1, lat2, lng2):
    p = np.pi / 180
    a = np.sin((lat2 - lat1) * p / 2) ** 2 + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lng2 - lng1) * p / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


# ---------------- facilities ----------------
weekday_assignment = list(rng.choice(_weekday_pool, size=len(FAC_REGIONS), replace=False))
fac = []
for i, (r, wd) in enumerate(zip(FAC_REGIONS, weekday_assignment), 1):
    lat, lng = jitter(REGIONS[r], 0.015)
    dur = int(rng.choice([45, 60, 60, 60]))
    songs = dur // 3
    base_target = round(songs / 2)                     # ~2 songs/musician -> ~10 musicians at 60 min
    # target_musicians filled in below, once musician homes exist and we know how far this
    # facility actually is from the volunteer pool — a remote facility realistically draws fewer.
    time = str(rng.choice(WEEKDAY_TIME_OPTIONS[wd]))
    fac.append(dict(facility_id=f"SH{i:02d}", display_name=f"SH {i}", region=r, lat=lat, lng=lng,
                    show_duration_min=dur, songs_per_show=songs, base_target_musicians=base_target,
                    min_musicians=3, max_musicians=songs,      # everyone plays >=1 song -> can't exceed songs
                    has_piano_onsite=bool(rng.random() < 0.7),
                    preferred_slot=f"{wd} {time}"))
fac = pd.DataFrame(fac)

# ---------------- musicians ----------------
# Most musicians live clustered near one of the 7 facility regions (tight jitter -> real 5km
# carpool clusters exist), with a minority scattered across other GTA regions as the far-flung
# outliers you'd expect in a real volunteer network (no carpool partner nearby, drives in alone).
FAR_REGIONS = [r for r in REGIONS if r not in FAC_REGIONS]
ages = np.clip(np.round(rng.normal(17.5, 3.6, N_MUSICIANS)), 11, 23).astype(int)
instr = rng.choice(["piano", "violin", "guitar", "cello"], N_MUSICIANS, p=[0.83, 0.06, 0.06, 0.05])
mus = []
for i in range(N_MUSICIANS):
    if rng.random() < 0.85:
        region = str(rng.choice(FAC_REGIONS))
        lat, lng = jitter(REGIONS[region], 0.02)
    else:
        region = str(rng.choice(FAR_REGIONS))
        lat, lng = jitter(REGIONS[region], 0.03)
    a = int(ages[i])
    can_drive = bool(a >= 17 and rng.random() < 0.6)    # some 17+ don't have a car; irrelevant under 17
    transport = "guardian" if a < 17 else ("car" if can_drive else "transit")
    typ = int(rng.choice([2, 3, 3]))
    ext = int(rng.choice([0, 1, 2, 3]))                 # most can learn extra songs, some can't (0)
    mus.append(dict(musician_id=f"M{i+1:02d}", display_name=f"Musician {i+1}", age=a, instrument=str(instr[i]),
                    home_region=region, home_lat=lat, home_lng=lng, transport=transport, can_drive=can_drive,
                    years_with_org=float(np.round(rng.uniform(0, 4.0), 1)),
                    max_shows_per_month=int(rng.choice([1, 2, 3, 4], p=[.1, .3, .35, .25])),
                    min_songs=1, typical_songs=typ, max_songs=typ + ext))
mus = pd.DataFrame(mus)

dist = pd.DataFrame([dict(musician_id=m.musician_id, facility_id=f.facility_id,
                          distance_km=round(float(hav(m.home_lat, m.home_lng, f.lat, f.lng)) * 1.3, 1))
                     for m in mus.itertuples() for f in fac.itertuples()])

# A facility far from where the volunteer pool actually lives realistically draws fewer people
# than one that's central, even with the same songs_per_show. Scale each facility's target down
# from its base (songs/2) once its actual average distance to the pool is known: facilities at or
# below a 20km average keep the full base target; every km beyond that shaves the target down,
# floored so it never drops below the min_musicians floor.
avg_dist_by_fac = dist.groupby("facility_id").distance_km.mean()
BASELINE_KM, KM_PER_TARGET_POINT = 20, 4
fac["target_musicians"] = fac.apply(
    lambda f: max(f.min_musicians, round(f.base_target_musicians
                                         - max(avg_dist_by_fac[f.facility_id] - BASELINE_KM, 0) / KM_PER_TARGET_POINT)),
    axis=1)
fac = fac.drop(columns="base_target_musicians")

ms = list(mus[["musician_id", "home_lat", "home_lng"]].itertuples())
mdist_rows = []
for i, a in enumerate(ms):
    for b in ms[i + 1:]:
        km = round(float(hav(a.home_lat, a.home_lng, b.home_lat, b.home_lng)) * 1.3, 1)
        mdist_rows.append(dict(m1=a.musician_id, m2=b.musician_id, km=km))
        mdist_rows.append(dict(m1=b.musician_id, m2=a.musician_id, km=km))
mdist = pd.DataFrame(mdist_rows)


# ---------------- shows (history + upcoming; not weekend-only — see SLOT_POOL) ----------------
def month_shows(y, mo, idx, period):
    days_in_month, d = [], date(y, mo, 1)
    while d.month == mo:
        days_in_month.append(d)
        d += timedelta(days=1)
    rows = []
    for f in fac.itertuples():
        wd = WEEKDAY_NUM[f.preferred_slot.split()[0]]
        cand = [x for x in days_in_month if x.weekday() == wd]
        # 2 shows/month, spread apart; fall back to whatever occurrences exist if the month is short on them
        picks = [cand[0], cand[min(2, len(cand) - 1)]] if len(cand) >= 2 else cand
        for x in picks:
            rows.append(dict(show_id=f"S{idx:04d}", facility_id=f.facility_id, date=x.isoformat(),
                             start_time=f.preferred_slot.split()[1], duration_min=f.show_duration_min, period=period))
            idx += 1
    return rows, idx


shows, idx = [], 1
for y, m in HISTORY_MONTHS:
    r, idx = month_shows(y, m, idx, "history"); shows += r
for y, m in UPCOMING_MONTHS:
    r, idx = month_shows(y, m, idx, "upcoming"); shows += r
shows = pd.DataFrame(shows)
shows["weekday"] = pd.to_datetime(shows["date"]).dt.weekday

# ---------------- availability ----------------
# Real source of truth is one coordinator-editable table: weekly_availability, a recurring
# pattern (which days, which hours each day). availability.csv (the flat musician x show table
# the optimizer reads) is *resolved* from it as a default — a coordinator can then directly
# override individual show checkboxes in that flat table (no separate "exceptions" concept
# needed; a one-off deviation from someone's usual pattern is just a direct edit to their row
# for that show). If a schedule already got built around a bad assumption, that's what the
# lock/ban-then-re-solve tool is for later, reusing the same backup-ranking logic.
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WINDOWS = {"all_day": ("09:00", "21:00"), "morning": ("09:00", "12:30"),
          "afternoon": ("12:30", "17:00"), "evening": ("17:00", "21:00")}
WINDOW_KEYS, WINDOW_P = list(WINDOWS), [0.5, 0.15, 0.2, 0.15]

overall_busy = rng.uniform(0.3, 0.85, N_MUSICIANS)                       # how free this person generally is
weekday_mult = rng.uniform(0.4, 1.3, (N_MUSICIANS, 7))                    # which days of the week suit them
hard_no_day = rng.integers(0, 7, N_MUSICIANS)                             # a day they're essentially never free
has_hard_no = rng.random(N_MUSICIANS) < 0.4                              # not everyone has one
weekday_prob = np.clip(overall_busy[:, None] * weekday_mult, 0.03, 0.95)
for i in range(N_MUSICIANS):
    if has_hard_no[i]:
        weekday_prob[i, hard_no_day[i]] = 0.03

pattern_rows = []
for i, m in enumerate(mus.itertuples()):
    for wd_idx, wd_name in enumerate(DAYS):
        if rng.random() < weekday_prob[i, wd_idx]:          # "generally free this day of the week"
            key = str(rng.choice(WINDOW_KEYS, p=WINDOW_P))   # but not necessarily all day
            start, end = WINDOWS[key]
            pattern_rows.append(dict(musician_id=m.musician_id, weekday=wd_name, start_time=start, end_time=end))
weekly_availability = pd.DataFrame(pattern_rows)


def resolve_available(musician_id, weekday_name, show_start, show_end):
    pat = weekly_availability[(weekly_availability.musician_id == musician_id)
                              & (weekly_availability.weekday == weekday_name)]
    return int(((pat.start_time <= show_start) & (pat.end_time >= show_end)).any())


shows["end_time"] = (pd.to_datetime(shows.start_time, format="%H:%M")
                     + pd.to_timedelta(shows.duration_min, unit="m")).dt.strftime("%H:%M")
av_rows = []
for s in shows.itertuples():
    for m in mus.itertuples():
        avail = resolve_available(m.musician_id, DAYS[s.weekday], s.start_time, s.end_time)
        if rng.random() < 0.05:            # a one-off deviation from the usual pattern, folded
            avail = not avail              # straight into the flat table — nothing to look up later
        av_rows.append(dict(musician_id=m.musician_id, show_id=s.show_id, available=int(avail)))
av = pd.DataFrame(av_rows)

# ---------------- history_assignments (what the manual/simulated process actually did) ----------------
avail_lookup = {(r.musician_id, r.show_id) for r in av.itertuples() if r.available == 1}
dist_lookup = {(r.musician_id, r.facility_id): r.distance_km for r in dist.itertuples()}
GUARDIAN_MAX_KM = 35
history_rows = []
for s in shows[shows.period == "history"].itertuples():
    eligible = [
        m for m in mus.itertuples()
        if (m.musician_id, s.show_id) in avail_lookup
        and not (m.age < 17 and dist_lookup[(m.musician_id, s.facility_id)] > GUARDIAN_MAX_KM)
    ]
    rng.shuffle(eligible)
    fac_row = fac[fac.facility_id == s.facility_id].iloc[0]
    target = int(fac_row.target_musicians)

    pianists = [m for m in eligible if m.instrument == "piano"]
    others = [m for m in eligible if m.instrument != "piano"]
    roster = (pianists[:1] + others + pianists[1:])[:target] if pianists else eligible[:target]
    if len(roster) < fac_row.min_musicians:
        roster = eligible[: fac_row.min_musicians]

    for m in roster:
        planned = m.typical_songs * 3
        roll = rng.random()
        status = "no_show" if roll < 0.03 else ("late_cancel" if roll < 0.13 else "attended")
        actual = 0 if status != "attended" else planned
        history_rows.append(dict(show_id=s.show_id, musician_id=m.musician_id,
                                 planned_set_min=planned, status=status, actual_set_min=actual))
history = pd.DataFrame(history_rows)

fac.to_csv(OUT / "facilities.csv", index=False)
mus.to_csv(OUT / "musicians.csv", index=False)
shows.drop(columns=["weekday", "end_time"]).to_csv(OUT / "shows.csv", index=False)
av.to_csv(OUT / "availability.csv", index=False)
weekly_availability.to_csv(OUT / "weekly_availability.csv", index=False)
dist.to_csv(OUT / "distances.csv", index=False)
mdist.to_csv(OUT / "musician_distances.csv", index=False)
history.to_csv(OUT / "history_assignments.csv", index=False)

if __name__ == "__main__":
    print("instruments:", mus.instrument.value_counts().to_dict())
    print("age range:", mus.age.min(), "-", mus.age.max(), "| under 17 (guardian):", int((mus.age < 17).sum()))
    print("facilities:", len(fac), "| shows:", len(shows),
          "(history:", int((shows.period == 'history').sum()), "upcoming:", int((shows.period == 'upcoming').sum()), ")")
    print("show weekdays:", shows.assign(wd=pd.to_datetime(shows.date).dt.day_name()).wd.value_counts().to_dict())
    print("mean songs typical/max:", round(mus.typical_songs.mean(), 1), round(mus.max_songs.mean(), 1))
    cnt = av[av.available == 1].groupby("show_id").musician_id.nunique()
    print("avail per show: mean", round(cnt.mean(), 1), "min", cnt.min())
    print("capacity:", int(mus.max_shows_per_month.sum()), "slots/mo vs need", int(fac.target_musicians.sum() * 2))
    print("history status counts:", history.status.value_counts().to_dict())
    print("history rows:", len(history), "| avg musicians/show:", round(len(history) / (shows.period == "history").sum(), 1))
    print("weekly_availability rows:", len(weekly_availability), "| avg free days/musician:",
          round(len(weekly_availability) / N_MUSICIANS, 1))
