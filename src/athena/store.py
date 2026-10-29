"""One SQLite file (WAL) is the truth for spaces, memory, conversations, ledger, cards, settings, drafts
and twins."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

_TABLES = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS spaces (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, brief TEXT NOT NULL, apps TEXT NOT NULL,
  hue INTEGER NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memory (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, text TEXT NOT NULL, space_id TEXT NOT NULL, created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS memory_space ON memory (space_id, kind);
CREATE TABLE IF NOT EXISTS turns (
  id TEXT PRIMARY KEY, space_id TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL,
  created TEXT NOT NULL, cost_usd REAL, card_id TEXT);
CREATE INDEX IF NOT EXISTS turns_space ON turns (space_id);
CREATE TABLE IF NOT EXISTS cards (
  id TEXT PRIMARY KEY, space_id TEXT NOT NULL, action TEXT NOT NULL, label TEXT NOT NULL,
  args TEXT NOT NULL, state TEXT NOT NULL, created TEXT NOT NULL, resolved TEXT);
CREATE INDEX IF NOT EXISTS cards_space ON cards (space_id);
CREATE TABLE IF NOT EXISTS ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, surface TEXT NOT NULL, space_id TEXT NOT NULL,
  engine TEXT NOT NULL, model TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER, cost_usd REAL,
  cost_estimated INTEGER NOT NULL, latency_ms INTEGER NOT NULL, ok INTEGER NOT NULL, error TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS page_reads (
  id INTEGER PRIMARY KEY AUTOINCREMENT, space_id TEXT NOT NULL, created TEXT NOT NULL,
  app TEXT NOT NULL, tool TEXT NOT NULL, args TEXT NOT NULL, answer TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS page_reads_space ON page_reads (space_id);
CREATE TABLE IF NOT EXISTS drafts (
  id TEXT PRIMARY KEY, space_id TEXT NOT NULL, step TEXT NOT NULL, need TEXT NOT NULL, sketch TEXT NOT NULL,
  coverage TEXT NOT NULL, skipped TEXT NOT NULL DEFAULT '[]', asked TEXT NOT NULL DEFAULT '{}', chore_id TEXT,
  key TEXT, bench TEXT, verdict TEXT, note TEXT, created TEXT NOT NULL, updated TEXT NOT NULL, expected TEXT,
  views TEXT, ask TEXT, practice TEXT);
CREATE INDEX IF NOT EXISTS drafts_space ON drafts (space_id);
CREATE TABLE IF NOT EXISTS twins (
  id TEXT PRIMARY KEY, space_id TEXT NOT NULL, state TEXT NOT NULL, need TEXT NOT NULL,
  sketch TEXT NOT NULL, asked TEXT NOT NULL, ask TEXT, since TEXT, paused_because TEXT,
  created TEXT NOT NULL, updated TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS twins_space ON twins (space_id);
""" + "".join(
    # A twin's parts, one table each: `owner` is the twin (a turn's is its mission), `body` the row's JSON.
    f"""CREATE TABLE IF NOT EXISTS {t} (
  owner TEXT NOT NULL, space_id TEXT NOT NULL, id TEXT NOT NULL, position INTEGER NOT NULL,
  body TEXT NOT NULL, PRIMARY KEY (owner, id));
CREATE INDEX IF NOT EXISTS {t}_space ON {t} (space_id);
"""
    for t in (
        "twin_channels",
        "twin_dials",
        "twin_samples",
        "twin_pages",
        "twin_chores",
        "twin_memory",
        "twin_examples",
        "twin_missions",
        "twin_turns",
    )
)

#: Every table a twin keeps, each with `space_id`: erasing a space empties them (spaces.erase).
TWIN_TABLES = (
    "twins",
    "twin_channels",
    "twin_dials",
    "twin_samples",
    "twin_pages",
    "twin_chores",
    "twin_memory",
    "twin_examples",
    "twin_missions",
    "twin_turns",
)

# Columns added after a table first shipped: (table, column, type). `CREATE TABLE IF NOT EXISTS` leaves
# an older table as it was, so migrate() adds each one that is missing.
_ADDED = (
    ("drafts", "expected", "TEXT"),
    ("drafts", "views", "TEXT"),
    ("drafts", "ask", "TEXT"),
    ("drafts", "practice", "TEXT"),
)

# External-content index over memory.text, kept current by triggers so a delete anywhere stays honest.
_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(text, content='memory', content_rowid='rowid');
CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory BEGIN
  INSERT INTO memory_fts(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory BEGIN
  INSERT INTO memory_fts(memory_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
END;
CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE OF text ON memory BEGIN
  INSERT INTO memory_fts(memory_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
  INSERT INTO memory_fts(rowid, text) VALUES (new.rowid, new.text);
END;
"""


class Store:
    """One connection, serialised by a lock; the daemon is the only writer."""

    def __init__(self, path: Path | str) -> None:
        self._lock = threading.RLock()
        self._depth = 0
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        if str(path) != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self.fts = False  # set by migrate(): whether FTS5 is compiled in
        self.migrate()

    @property
    def db(self) -> sqlite3.Connection:
        return self._db

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """Holds the lock and one transaction; a nested `tx` joins the outer one."""
        with self._lock:
            outer = self._depth == 0
            if outer:
                self._db.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield self._db
            except BaseException:
                self._depth -= 1
                if outer:
                    self._db.execute("ROLLBACK")
                raise
            self._depth -= 1
            if outer:
                self._db.execute("COMMIT")

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, params).fetchall()

    def run(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        """One write statement in its own transaction (or the open one); answers rowcount."""
        with self.tx() as db:
            return db.execute(sql, params).rowcount

    def migrate(self) -> None:
        with self._lock:
            for stmt in _TABLES.split(";"):
                if stmt.strip():
                    self._db.execute(stmt)
            for table, column, kind in _ADDED:
                have = {r["name"] for r in self._db.execute(f"PRAGMA table_info({table})")}
                if column not in have:
                    self._db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
            try:
                self._db.executescript(_FTS)
                self.fts = True
            except sqlite3.OperationalError:  # FTS5 not compiled in: recall falls back to LIKE
                self.fts = False
            self._db.execute(
                "INSERT INTO meta(key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(SCHEMA_VERSION),),
            )

    def close(self) -> None:
        with self._lock:
            self._db.close()
