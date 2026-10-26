"""Daemon-held settings both windows agree on."""

from __future__ import annotations

from athena.store import Store

ACTIVE_SPACE_KEY = "active_space_id"


class Settings:
    def __init__(self, store: Store) -> None:
        self._store = store

    def get(self, key: str, default: str = "") -> str:
        rows = self._store.query("SELECT value FROM settings WHERE key = ?", (key,))
        return str(rows[0]["value"]) if rows else default

    def set(self, key: str, value: str) -> None:
        self._store.run(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def active_space(self) -> str:
        """`active_space_id`; "" (core) when unset. The caller checks the space still exists."""
        return self.get(ACTIVE_SPACE_KEY, "")
