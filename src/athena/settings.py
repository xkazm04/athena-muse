"""Daemon-held settings both windows agree on (ADR 0012).

One key/value row each in the `settings` table. A row that is missing or holds a value the contract
does not know reads as its default, so an old or hand-edited database never fails a window's start.
"""

from __future__ import annotations

import typing
from typing import Any, cast

from athena.contracts import EngineId, Look, MotionChoice, ThemeChoice, TypeScale
from athena.errors import ApiError
from athena.store import Store

ACTIVE_SPACE_KEY = "active_space_id"
ENGINE_KEY = "engine"
THEME_KEY = "theme"
TYPE_SCALE_KEY = "type_scale"
MOTION_KEY = "motion"

DEFAULT_LOOK: Look = {"theme": "auto", "type_scale": "standard", "motion": "system"}

# The look's three rows: the wire key, the stored key and the values the contract allows.
LOOK_ROWS: dict[str, tuple[str, tuple[str, ...]]] = {
    "theme": (THEME_KEY, typing.get_args(ThemeChoice)),
    "type_scale": (TYPE_SCALE_KEY, typing.get_args(TypeScale)),
    "motion": (MOTION_KEY, typing.get_args(MotionChoice)),
}
ENGINE_IDS: tuple[str, ...] = typing.get_args(EngineId)


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

    def look(self) -> Look:
        """The stored look; each unknown or missing row reads as its default."""

        def row(wire: str) -> str:
            key, allowed = LOOK_ROWS[wire]
            value = self.get(key)
            return value if value in allowed else str(DEFAULT_LOOK[wire])  # type: ignore[literal-required]

        return {
            "theme": cast("ThemeChoice", row("theme")),
            "type_scale": cast("TypeScale", row("type_scale")),
            "motion": cast("MotionChoice", row("motion")),
        }

    def set_look(self, body: dict[str, Any]) -> Look:
        """Writes the rows the body names, all or none: one bad value refuses the whole body."""
        unknown = sorted(set(body) - set(LOOK_ROWS))
        if unknown:
            raise ApiError("bad_request", f"Settings has no look called {unknown[0]}")
        if not body:
            raise ApiError("bad_request", "send theme, type_scale or motion")
        for wire, value in body.items():
            allowed = LOOK_ROWS[wire][1]
            if value not in allowed:
                raise ApiError("bad_request", f"{wire} must be one of {', '.join(allowed)}")
        with self._store.tx():
            for wire, value in body.items():
                self.set(LOOK_ROWS[wire][0], cast("str", value))
        return self.look()

    def engine_choice(self) -> str:
        """The engine chosen in Settings, or "" when none was (or the row is not an engine)."""
        value = self.get(ENGINE_KEY)
        return value if value in ENGINE_IDS else ""
