"""Which function runs each routine kind, its default cadence and its name. The host reads this."""

from __future__ import annotations

from collections.abc import Callable

from athena.contracts import RoutineKind
from athena.routines import inbox, outreach, stats, watch
from athena.routines.context import RunContext

#: "twin" is the host's own: a twin's open Gmail missions (WP2.1).
RUN: dict[RoutineKind, Callable[[RunContext], None]] = {
    "watch": watch.run,
    "inbox": inbox.run,
    "stats": stats.run,
    "outreach": outreach.run,
}
CADENCE_S: dict[RoutineKind, int] = {
    "watch": 6 * 3600,
    "inbox": 30 * 60,
    "stats": 24 * 3600,
    "outreach": 3600,
    "twin": 300,
}
NAME: dict[RoutineKind, str] = {
    "watch": "Watch followed creators for new tracks",
    "inbox": "Read the mailbox for replies",
    "stats": "Read the channel's numbers",
    "outreach": "Draft offers to creators of kept tracks",
    "twin": "Work the twin's open conversations",
}
