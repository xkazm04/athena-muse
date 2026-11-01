"""The seam between the host (WP2.1) and the routine kinds (WP2.2). STUB (WP2.0): signatures final.

A kind is `def run(ctx: RunContext) -> None`. It raises `Skip` when it cannot start (no browser, signed
out, nothing to do, no twin), `Partial` when it stops part-way (a page it could not read), and lets
`CeilingReached` from `extract` end the run; the host records each as the run's outcome. It counts
what it covered on `ctx` (`found`, `of`, `kept`, `cards`) and may leave one plain-words `note`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from athena.contracts import ChannelKind, RecordItem, RecordKind, Routine, SkipReason

if TYPE_CHECKING:
    from athena.app import Daemon


class Skip(Exception):
    def __init__(self, reason: SkipReason, note: str = "") -> None:
        super().__init__(note or reason)
        self.reason: SkipReason = reason
        self.note = note


class Partial(Exception):
    """Stopped part-way; the message says what was covered and why it stopped."""


class CeilingReached(Exception):
    """The next model call would pass the run's ceiling."""


@dataclass(frozen=True)
class PageText:
    url: str  # where the hidden tab ended
    text: str  # the page's text; the caller fences it as page data
    signed_out: bool  # it ended on a sign-in page (a password field showed)


@dataclass
class RunContext:
    daemon: Daemon
    space_id: str
    routine: Routine
    found: int = 0
    of: int | None = None
    kept: int = 0
    cards: int = 0
    note: str = ""
    spent_usd: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)  # the host's own bookkeeping

    def read(self, url: str) -> PageText:
        """Open `url` in a hidden tab of her browser, read its text, close it. Raises Skip("no_browser")
        when the desktop is not running, Skip("signed_out") when it lands on a sign-in page, Partial on
        a timeout or a site the project does not keep."""
        raise NotImplementedError

    def extract(self, system: str, user: str, key: str) -> dict[str, Any]:
        """One tool-less model call (surface `routine`, one ledger row), answered as the JSON object under
        `key`. Adds its cost to `spent_usd`; raises CeilingReached before a call when the spend so far
        leaves no room (a call with no price counts as a tenth of the ceiling)."""
        raise NotImplementedError

    def put(self, kind: RecordKind, body: dict[str, Any], key: str | None = None) -> RecordItem | None:
        """Keep a record through the records' own door (records.actions), by the routine: finds at
        once with the person's track fields kept; any other kind files a card (counted in `cards`).
        Answers the record, or None when it was refused or filed. Counts `kept` when a revision was
        appended."""
        raise NotImplementedError

    def draft(
        self,
        channel: ChannelKind,
        creator_key: str,
        purpose: str,
        context: str,
        thread_key: str | None = None,
    ) -> str | None:
        """A message in the project's twin's voice on `channel`, filed as a `twin_send_web` card the
        person may edit (twins.web.draft). Answers the card id, or None when the project has no live
        twin (the caller then raises Skip("no_twin")). Counts `cards`."""
        raise NotImplementedError
