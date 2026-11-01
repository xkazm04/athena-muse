"""Which spaces have a turn running. Erase and the active-space switch wait on it.

Two holders: `turn` counts every model turn (a chat, a mission, a draft step), and `chat` counts only
the person's own chat turns (turn.py holds both). A routine waits only on `live`: a chat turn open in
its space (business Phase 2); a mission or a draft step never holds a routine back.
"""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager

from athena.errors import ApiError


class Busy:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: Counter[str] = Counter()
        self._closing: set[str] = set()
        self._chats: Counter[str] = Counter()

    def live(self, space_id: str) -> bool:
        """A chat turn is open in the space (a routine waits for it to end)."""
        with self._lock:
            return self._chats[space_id] > 0

    @contextmanager
    def chat(self, space_id: str) -> Iterator[None]:
        """Held for a chat turn's life, beside `turn`."""
        with self._lock:
            self._chats[space_id] += 1
        try:
            yield
        finally:
            with self._lock:
                self._chats[space_id] -= 1

    def running(self, space_id: str) -> bool:
        with self._lock:
            return self._running[space_id] > 0

    def any_running(self) -> bool:
        with self._lock:
            return any(n > 0 for n in self._running.values())

    @contextmanager
    def turn(self, space_id: str) -> Iterator[None]:
        """Held for a turn's life. Refused while the space is being erased."""
        with self._lock:
            if space_id in self._closing:
                raise ApiError("space_busy", "this project is being erased")
            self._running[space_id] += 1
        try:
            yield
        finally:
            with self._lock:
                self._running[space_id] -= 1

    @contextmanager
    def closing(self, space_id: str) -> Iterator[None]:
        """Held for an erase. Refused while a turn runs in the space."""
        with self._lock:
            if self._running[space_id] > 0:
                raise ApiError("space_busy", "Athena is working in this project; try again when she is done")
            self._closing.add(space_id)
        try:
            yield
        finally:
            with self._lock:
                self._closing.discard(space_id)
