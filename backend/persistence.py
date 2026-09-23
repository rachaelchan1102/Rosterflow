"""Postgres (Neon) persistence for the coordinator workspace's scheduling state — the draft and
published schedules, locks, bans, and whether the draft is stale. The roster itself (musicians,
shows, availability, ...) goes through optimizer/data.py's load_from_db / save_to_db.

Every save is a full rewrite of these small tables inside one transaction, same approach as
save_to_db: at tens of musicians and ~30 shows, rewriting is instant and far harder to get wrong
than tracking row-level diffs.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import psycopg

from backend.workspace import ASSIGNMENT_COLS, BACKUP_COLS, Schedule, Workspace

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "optimizer" / "schema.sql"


def apply_schema(dsn: str) -> None:
    with psycopg.connect(dsn) as conn:
        conn.execute(SCHEMA_PATH.read_text())
        conn.commit()


def roster_is_empty(dsn: str) -> bool:
    with psycopg.connect(dsn) as conn:
        return conn.execute("SELECT count(*) FROM musicians").fetchone()[0] == 0


STATE_TABLES = ("schedule_assignments", "schedule_backups", "schedule_locks", "schedule_bans", "schedule_meta")


def clear_state(dsn: str) -> None:
    with psycopg.connect(dsn) as conn:
        for table in STATE_TABLES:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()


def save_state(dsn: str, ws: Workspace) -> None:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for table in STATE_TABLES:
            cur.execute(f"DELETE FROM {table}")
        for kind, schedule in (("draft", ws.draft), ("published", ws.published)):
            if schedule is None:
                continue
            cur.executemany(
                "INSERT INTO schedule_assignments (kind, show_id, musician_id, songs) VALUES (%s, %s, %s, %s)",
                [(kind, r.show_id, r.musician_id, int(r.songs)) for r in schedule.assignments.itertuples()])
            cur.executemany(
                "INSERT INTO schedule_backups (kind, show_id, musician_id, rank) VALUES (%s, %s, %s, %s)",
                [(kind, r.show_id, r.musician_id, int(r.rank)) for r in schedule.backups.itertuples()])
        cur.executemany("INSERT INTO schedule_locks (musician_id, show_id) VALUES (%s, %s)", list(ws.locks))
        cur.executemany("INSERT INTO schedule_bans (musician_id, scope, target_id) VALUES (%s, %s, %s)", list(ws.bans))
        if ws.needs_resolve:
            cur.execute("INSERT INTO schedule_meta (key, value) VALUES ('needs_resolve', %s)", (ws.needs_resolve,))
        conn.commit()


def load_state(dsn: str, ws: Workspace) -> None:
    """Restore a coordinator workspace's scheduling state onto `ws` (whose roster is already loaded)."""
    pianist_ids = set(ws.data.musicians[ws.data.musicians.instrument == "piano"].musician_id)
    with psycopg.connect(dsn) as conn:
        assignments = conn.execute("SELECT kind, show_id, musician_id, songs FROM schedule_assignments").fetchall()
        backups = conn.execute("SELECT kind, show_id, musician_id, rank FROM schedule_backups").fetchall()
        ws.locks = {(m, s) for m, s in conn.execute("SELECT musician_id, show_id FROM schedule_locks").fetchall()}
        ws.bans = {tuple(r) for r in conn.execute("SELECT musician_id, scope, target_id FROM schedule_bans").fetchall()}
        meta = dict(conn.execute("SELECT key, value FROM schedule_meta").fetchall())

    for kind in ("draft", "published"):
        a_rows = [dict(show_id=s, musician_id=m, songs=n) for k, s, m, n in assignments if k == kind]
        b_rows = [dict(show_id=s, musician_id=m, rank=r, is_pianist=m in pianist_ids)
                  for k, s, m, r in backups if k == kind]
        if not a_rows:
            continue
        schedule = Schedule(pd.DataFrame(a_rows, columns=ASSIGNMENT_COLS),
                            pd.DataFrame(b_rows, columns=BACKUP_COLS).sort_values(["show_id", "rank"],
                                                                                  ignore_index=True))
        setattr(ws, kind, schedule)
    ws.needs_resolve = meta.get("needs_resolve")
