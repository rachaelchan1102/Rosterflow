"""The public playground's in-memory store: a mutable wrapper around Data, holding no database
connection, no file handle, nothing that outlives the Python process holding it. That's the whole
design of the playground — every visitor gets a fresh copy of the synthetic dataset, edits it
freely for as long as their session lasts, and none of it survives once the session ends.

The UI is the only thing that decides WHERE an instance of this lives (one PlaygroundStore per
visitor, held in st.session_state) — nothing in here imports Streamlit, matching the rule that
the data/optimizer layers never know or care which deployment mode they're running in.
"""
from __future__ import annotations

from optimizer.data import Data, load_from_csv
from optimizer.data import add_musician as _add_musician
from optimizer.data import add_show as _add_show
from optimizer.data import delete_musician as _delete_musician
from optimizer.data import delete_show as _delete_show
from optimizer.data import update_musician as _update_musician
from optimizer.data import update_show as _update_show

DEFAULT_SAMPLE_DATA_DIR = "sample_data"


class PlaygroundStore:
    """Wraps a Data object so CRUD reads as ordinary mutating calls (store.add_musician(...))
    even though data.py's functions are pure — each call either replaces self.data with the new,
    already-validated state, or raises RecordConflictError and leaves self.data exactly as it
    was. A visitor's failed edit never corrupts their session."""

    def __init__(self, data: Data):
        self.data = data

    @classmethod
    def fresh(cls, sample_data_dir: str = DEFAULT_SAMPLE_DATA_DIR) -> "PlaygroundStore":
        """A brand-new visitor's starting point — the same synthetic baseline every time."""
        return cls(load_from_csv(sample_data_dir))

    def add_musician(self, musician: dict) -> None:
        self.data = _add_musician(self.data, musician)

    def update_musician(self, musician_id: str, changes: dict) -> None:
        self.data = _update_musician(self.data, musician_id, changes)

    def delete_musician(self, musician_id: str) -> None:
        self.data = _delete_musician(self.data, musician_id)

    def add_show(self, show: dict) -> None:
        self.data = _add_show(self.data, show)

    def update_show(self, show_id: str, changes: dict) -> None:
        self.data = _update_show(self.data, show_id, changes)

    def delete_show(self, show_id: str) -> None:
        self.data = _delete_show(self.data, show_id)
