"""Daemon-held settings both windows agree on. Owned by WP1. Stub: final signatures."""

from __future__ import annotations

from athena.store import Store


class Settings:
    def __init__(self, store: Store) -> None:
        raise NotImplementedError

    def get(self, key: str, default: str = "") -> str:
        raise NotImplementedError

    def set(self, key: str, value: str) -> None:
        raise NotImplementedError

    def active_space(self) -> str:
        """`active_space_id`; "" (core) when unset. The caller checks the space still exists."""
        raise NotImplementedError
