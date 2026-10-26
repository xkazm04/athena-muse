"""SSE broadcast to every open window.

`publish` is called from sync threads (the turn stream runs in a threadpool), so each subscriber's
queue is fed through its own loop with `call_soon_threadsafe`.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import AsyncIterator

from athena.contracts import AppEvent

QUEUE_MAX = 256


def _offer(queue: asyncio.Queue[AppEvent], event: AppEvent) -> None:
    # A stuck window loses events; it never slows the others.
    with contextlib.suppress(asyncio.QueueFull):
        queue.put_nowait(event)


class Events:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[AppEvent]]] = []

    def publish(self, event: AppEvent) -> None:
        """Thread-safe; never blocks on a slow subscriber."""
        with self._lock:
            subs = list(self._subs)
        for loop, queue in subs:
            try:
                loop.call_soon_threadsafe(_offer, queue, event)
            except RuntimeError:  # that loop is closed; its subscriber unregisters on close
                continue

    async def subscribe(self) -> AsyncIterator[AppEvent]:
        """Registers on first iteration, unregisters when the iterator closes."""
        entry = (asyncio.get_running_loop(), asyncio.Queue[AppEvent](maxsize=QUEUE_MAX))
        with self._lock:
            self._subs.append(entry)
        try:
            while True:
                yield await entry[1].get()
        finally:
            with self._lock:
                self._subs.remove(entry)
