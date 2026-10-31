"""The relay between the daemon and her browser in the desktop shell (ADR 0013).

The shell long-polls `GET /browser/next?wait=N` and answers each call once with `POST /browser/done`.
A caller here blocks on `call()` until the answer comes or its deadline passes; a deadline that
passes answers `timeout` and a late answer is dropped. With no shell polling, every call answers
`no_browser` at once ("her browser is not open"), so a turn never waits on a window that is not there.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from athena.clock import mint

#: The longest one long-poll may hold the shell's request.
WAIT_MAX_S = 25.0
#: A shell that has not polled for this long is not there.
GONE_AFTER_S = WAIT_MAX_S + 15.0
#: The default deadline of one hand.
CALL_TIMEOUT_S = 45.0

NOT_OPEN = "Her browser is not open; the desktop app runs it."


@dataclass
class _Waiting:
    call: dict[str, Any]
    done: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None


class Relay:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._cond = threading.Condition()
        self._queue: deque[str] = deque()
        self._waiting: dict[str, _Waiting] = {}
        self._polled: float | None = None
        self._polling = 0

    def connected(self) -> bool:
        with self._cond:
            if self._polling:
                return True
            return self._polled is not None and self._clock() - self._polled < GONE_AFTER_S

    def call(
        self,
        hand: str,
        args: dict[str, Any] | None = None,
        *,
        tab: int | None = None,
        load: int | None = None,
        url: str | None = None,
        timeout: float = CALL_TIMEOUT_S,
    ) -> dict[str, Any]:
        """One hand, answered `{ok, output, reason?, tab?, ...}`. `load` and `url` bind the call to
        the page it was judged on: the shell refuses it with `moved` when the tab has left that page."""
        if not self.connected():
            return {"ok": False, "reason": "no_browser", "output": NOT_OPEN}
        call_id = mint("hand_")
        call: dict[str, Any] = {"id": call_id, "hand": hand, "args": args or {}}
        if tab is not None:
            call["tab"] = tab
        if load is not None:
            call["load"] = load
        if url is not None:
            call["url"] = url
        waiting = _Waiting(call)
        with self._cond:
            self._waiting[call_id] = waiting
            self._queue.append(call_id)
            self._cond.notify_all()
        answered = waiting.done.wait(timeout)
        with self._cond:
            self._waiting.pop(call_id, None)
            if call_id in self._queue:
                self._queue.remove(call_id)
        if not answered or waiting.result is None:
            return {"ok": False, "reason": "timeout", "output": "Her browser did not answer in time."}
        return waiting.result

    def next(self, wait: float) -> dict[str, Any] | None:
        """The shell's long-poll: the next call, or None after `wait` seconds."""
        wait = max(0.0, min(wait, WAIT_MAX_S))
        deadline = self._clock() + wait
        with self._cond:
            self._polling += 1
            self._polled = self._clock()
            try:
                while True:
                    while self._queue:
                        found = self._waiting.get(self._queue.popleft())
                        if found is not None:
                            return found.call
                    left = deadline - self._clock()
                    if left <= 0:
                        return None
                    self._cond.wait(left)
            finally:
                self._polling -= 1
                self._polled = self._clock()

    def done(self, call_id: str, result: dict[str, Any]) -> bool:
        """The shell's answer. False for an id nobody waits on (late, or never issued)."""
        with self._cond:
            waiting = self._waiting.get(call_id)
        if waiting is None or waiting.done.is_set():
            return False
        waiting.result = result
        waiting.done.set()
        return True
