"""The send rule (ADR 0009): one pure function decides whether a twin's draft goes out alone.

The interactive path, the poller and the dress rehearsal all call `decide`; nothing else sends.
WP4 builds it; until then it raises.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from athena.contracts import SendDecision, TwinChannel, TwinMessageKind, WaitReason


@dataclass(frozen=True)
class DraftFacts:
    """What the rule reads from a draft: the kind of message, how sure it is and its risk list."""

    kind: TwinMessageKind
    confidence: int  # whole percent
    risks: tuple[str, ...]


class Ruling(NamedTuple):
    """`(decision, reason)`: reason is None exactly when the draft is sent alone."""

    decision: SendDecision
    reason: WaitReason | None


def decide(channel: TwinChannel, draft: DraftFacts, *, twin_live: bool) -> Ruling:
    """A draft is sent alone only when all of these hold:

    - the channel is connected and the twin is live;
    - the level is `auto` (the channel's `split` level for this kind of message when it has one);
    - `confidence >= bar`;
    - `risks` is empty.

    Everything else waits, with the first reason that holds, in this order:

    1. `paused`: the twin is not live or the channel is not connected. A paused twin or channel
       never sends.
    2. The level: `first_message` when a split channel holds first messages below Auto, else
       `review` or `assist`.
    3. `risk`: its risk list is not empty.
    4. `below_bar`: it is less sure than the channel's bar.

    Pure: no clock, no store, no I/O, so the same facts always get the same ruling.
    """
    raise NotImplementedError("the send rule is built in WP4")
