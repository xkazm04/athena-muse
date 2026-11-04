"""An agent's unattended calls (spark agent-leases): the person's limits, and the rule that decides
whether one app call may run without a card.

The rule is pure (:func:`verdict`): a call runs unattended only when the limits are signed, not ended,
not past their deadline, name the tool, and have a call left. Everything else is the ordinary card.
:class:`Ceiling` holds one lease's limits in memory and takes a call atomically under its lock, so
eight calls at once against five allowed run five. Limits are never raised: nothing here adds a call,
a tool or a minute after the mint.

Only a project's app tools can be named (`<app>__<tool>`, `<app>_on_<device>__<tool>`): her browser,
a twin, a project change, memory, records, the setup conversation and the grant itself never run
unattended, whatever a body sends.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from athena.contracts import (
    AGENT_CALLS_MAX,
    AGENT_FILE_MB_MAX,
    AGENT_MINUTES_MAX,
    CATALOG,
    AgentCeiling,
)
from athena.errors import ApiError

#: Why a call does or does not run unattended. `ok` runs; every other word files the ordinary card.
Verdict = Literal["ok", "unsigned", "ended", "expired", "not_named", "used_up"]

MB = 1024 * 1024
#: Told to the agent when its allowed calls are spent and a card was filed instead.
USED_UP = "The unattended calls you allowed are used up; this one needs your signature."


def verdict(
    *,
    signed: bool,
    ended: bool,
    deadline: float,
    now: float,
    tools: Collection[str],
    used: int,
    max_calls: int,
    name: str,
) -> Verdict:
    """Whether one call to the app tool `name` may run without a card. Pure."""
    if ended:
        return "ended"
    if not signed:
        return "unsigned"
    if now >= deadline:
        return "expired"
    if name not in tools or name in CATALOG:
        return "not_named"
    if used >= max_calls:
        return "used_up"
    return "ok"


def whole(value: Any, low: int, high: int, said: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ApiError("bad_request", f"{said} must be a whole number from {low} to {high}")
    return value


def check(
    raw: Any, app_tools: Collection[str], lease_tools: Collection[str]
) -> tuple[list[str], int, int, int | None]:
    """The person's limits as (tools, max_calls, minutes, file_bytes), or a 400 in plain words.
    `app_tools` are the project's app tool names; `lease_tools` what the agent may use at all."""
    if not isinstance(raw, dict):
        raise ApiError("bad_request", "send the unattended calls as an object")
    names = raw.get("tools")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        raise ApiError("bad_request", "name at least one app tool the agent may run without asking")
    tools = list(dict.fromkeys(names))
    for name in tools:
        if name in CATALOG or name not in app_tools:
            said = f"Only an app's own tools can run without asking; {name} is not one"
            raise ApiError("bad_request", said)
        if name not in lease_tools:
            raise ApiError("bad_request", f"The agent cannot use {name}, so it cannot run it without asking")
    max_calls = whole(raw.get("max_calls"), 1, AGENT_CALLS_MAX, "The number of calls")
    minutes = whole(raw.get("minutes"), 1, AGENT_MINUTES_MAX, "The minutes")
    file_bytes: int | None = None
    if raw.get("file_mb") is not None:
        file_bytes = whole(raw.get("file_mb"), 1, AGENT_FILE_MB_MAX, "The megabytes of files") * MB
    return tools, max_calls, minutes, file_bytes


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class Ceiling:
    """One lease's limits, live. `deadline` is wall-clock seconds; `clock` is read for every call."""

    tools: list[str]
    max_calls: int
    deadline: float
    file_bytes: int | None = None
    used: int = 0
    fetched: int = 0
    signed: bool = False
    ended: bool = False
    card_id: str | None = None
    clock: Callable[[], float] = time.time
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    #: One `app_fetch` at a time per lease, so two pulls cannot both spend the same bytes.
    fetching: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def rule(self, name: str) -> Verdict:
        return verdict(
            signed=self.signed,
            ended=self.ended,
            deadline=self.deadline,
            now=self.clock(),
            tools=self.tools,
            used=self.used,
            max_calls=self.max_calls,
            name=name,
        )

    def take(self, name: str, kept: Callable[[Ceiling], None] | None = None) -> Verdict:
        """Decides one call and, when it runs, spends it, both under the lock; `kept` writes the new
        count while the lock is held, so the stored count never goes backwards."""
        with self.lock:
            said = self.rule(name)
            if said == "ok":
                self.used += 1
                if kept is not None:
                    kept(self)
            return said

    def view(self) -> AgentCeiling:
        out: AgentCeiling = {
            "tools": list(self.tools),
            "max_calls": self.max_calls,
            "used": self.used,
            "deadline": _iso(self.deadline),
            "signed": self.signed,
        }
        if self.file_bytes is not None:
            out["file_bytes"] = self.file_bytes
        if self.card_id is not None:
            out["card_id"] = self.card_id
        return out

    def stored(self) -> dict[str, Any]:
        """The view plus what only the daemon keeps (bytes brought in so far)."""
        return {**self.view(), "fetched": self.fetched}
