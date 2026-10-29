"""The send rule (ADR 0009): one pure function decides whether a twin's draft goes out alone.

The interactive path, the poller and the dress rehearsal all call `decide`; nothing else sends.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from athena.contracts import Autonomy, SendDecision, TwinChannel, TwinMessageKind, WaitReason


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


def level(channel: TwinChannel, kind: TwinMessageKind) -> Autonomy:
    """The level that holds for this kind of message: the channel's `split` level when it has one,
    else its `autonomy`."""
    split = channel.get("split")
    return split[kind] if split is not None else channel["autonomy"]


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
    if not twin_live or channel["status"] != "connected":
        return Ruling("waits", "paused")
    held = level(channel, draft.kind)
    if held != "auto":
        if "split" in channel and draft.kind == "first_message":
            return Ruling("waits", "first_message")
        return Ruling("waits", held)
    if draft.risks:
        return Ruling("waits", "risk")
    if draft.confidence < channel["bar"]:
        return Ruling("waits", "below_bar")
    return Ruling("sent_alone", None)
