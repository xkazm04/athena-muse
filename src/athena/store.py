"""One SQLite file (WAL) is the truth for spaces, memory, conversations, ledger, cards and settings.

Owned by WP1. Stub: final signatures, bodies land with WP1.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class Store:
    """One connection, serialised by a lock; the daemon is the only writer."""

    def __init__(self, path: Path | str) -> None:
        """`path` may be ":memory:" in tests. Opens, sets WAL, runs `migrate()`."""
        raise NotImplementedError

    @property
    def db(self) -> sqlite3.Connection:
        raise NotImplementedError

    def migrate(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
