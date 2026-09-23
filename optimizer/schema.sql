-- Schema for the real deployment's Neon (Postgres) database. Mirrors the sample_data/ CSVs
-- exactly, column for column, so load_from_db and load_from_csv build identical Data objects.
-- Foreign keys use the default NO ACTION (no ON DELETE CASCADE) on purpose — optimizer/data.py's
-- delete_musician/delete_show already do the cascading explicitly and validate the result before
-- committing anything; the database enforcing the same constraint again is a backstop against a
-- write that bypasses that Python layer, not something meant to silently cascade on its own.

CREATE TABLE IF NOT EXISTS facilities (
    facility_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    region TEXT NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    show_duration_min INTEGER NOT NULL,
    songs_per_show INTEGER NOT NULL,
    target_musicians INTEGER NOT NULL,
    min_musicians INTEGER NOT NULL,
    max_musicians INTEGER NOT NULL,
    has_piano_onsite BOOLEAN NOT NULL,
    preferred_slot TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS musicians (
    musician_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    instrument TEXT NOT NULL,
    home_region TEXT NOT NULL,
    home_lat DOUBLE PRECISION NOT NULL,
    home_lng DOUBLE PRECISION NOT NULL,
    transport TEXT NOT NULL,
    can_drive BOOLEAN NOT NULL,
    years_with_org DOUBLE PRECISION NOT NULL,
    max_shows_per_month INTEGER NOT NULL,
    min_songs INTEGER NOT NULL,
    typical_songs INTEGER NOT NULL,
    max_songs INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS shows (
    show_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    date DATE NOT NULL,
    start_time TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    period TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS availability (
    musician_id TEXT NOT NULL REFERENCES musicians(musician_id),
    show_id TEXT NOT NULL REFERENCES shows(show_id),
    available SMALLINT NOT NULL CHECK (available IN (0, 1)),
    PRIMARY KEY (musician_id, show_id)
);

CREATE TABLE IF NOT EXISTS weekly_availability (
    id SERIAL PRIMARY KEY,
    musician_id TEXT NOT NULL REFERENCES musicians(musician_id),
    weekday TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS distances (
    musician_id TEXT NOT NULL REFERENCES musicians(musician_id),
    facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    distance_km DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (musician_id, facility_id)
);

CREATE TABLE IF NOT EXISTS musician_distances (
    m1 TEXT NOT NULL REFERENCES musicians(musician_id),
    m2 TEXT NOT NULL REFERENCES musicians(musician_id),
    km DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (m1, m2)
);

CREATE TABLE IF NOT EXISTS history_assignments (
    show_id TEXT NOT NULL REFERENCES shows(show_id),
    musician_id TEXT NOT NULL REFERENCES musicians(musician_id),
    planned_set_min INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('attended', 'late_cancel', 'no_show')),
    actual_set_min INTEGER NOT NULL,
    PRIMARY KEY (show_id, musician_id)
);

-- Workspace state for the real deployment: the draft and published schedules, plus the
-- coordinator's locks and bans. No foreign keys here on purpose — these reference musicians and
-- shows that a coordinator can delete, and the backend prunes stale rows itself rather than
-- letting a delete of a musician fail because an old published schedule still mentions them.

CREATE TABLE IF NOT EXISTS schedule_assignments (
    kind TEXT NOT NULL CHECK (kind IN ('draft', 'published')),
    show_id TEXT NOT NULL,
    musician_id TEXT NOT NULL,
    songs INTEGER NOT NULL,
    PRIMARY KEY (kind, show_id, musician_id)
);

CREATE TABLE IF NOT EXISTS schedule_backups (
    kind TEXT NOT NULL CHECK (kind IN ('draft', 'published')),
    show_id TEXT NOT NULL,
    musician_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    PRIMARY KEY (kind, show_id, musician_id)
);

CREATE TABLE IF NOT EXISTS schedule_locks (
    musician_id TEXT NOT NULL,
    show_id TEXT NOT NULL,
    PRIMARY KEY (musician_id, show_id)
);

CREATE TABLE IF NOT EXISTS schedule_bans (
    musician_id TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('show', 'facility')),
    target_id TEXT NOT NULL,
    PRIMARY KEY (musician_id, scope, target_id)
);

CREATE TABLE IF NOT EXISTS schedule_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
