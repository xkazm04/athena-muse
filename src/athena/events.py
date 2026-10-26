"""SSE broadcast to every open window. Owned by WP1. Stub: final signatures."""

from __future__ import annotations

from collections.abc import AsyncIterator

from athena.contracts import AppEvent


class Events:
    def publish(self, event: AppEvent) -> None:
        """Thread-safe; never blocks on a slow subscriber."""
        raise NotImplementedError

    def subscribe(self) -> AsyncIterator[AppEvent]:
        raise NotImplementedError
