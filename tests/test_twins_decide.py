"""The send rule (ADR 0009) as a table: every level, a split either way, the bar's edge (bar-1, bar,
bar+1), a risk, and a paused twin or channel. A draft goes alone only on Auto, at or above the bar,
with an empty risk list, on a connected channel of a live twin; otherwise the first reason that holds."""

from __future__ import annotations

import itertools

import pytest

from athena.contracts import BAR_DEFAULT, Autonomy, AutonomySplit, ChannelStatus, TwinChannel, TwinMessageKind
from athena.twins.decide import DraftFacts, Ruling, decide

BAR = BAR_DEFAULT
LEVELS: tuple[Autonomy, ...] = ("review", "assist", "auto")
KINDS: tuple[TwinMessageKind, ...] = ("first_message", "reply")


def channel(
    autonomy: Autonomy, split: AutonomySplit | None = None, status: ChannelStatus = "connected"
) -> TwinChannel:
    out: TwinChannel = {
        "kind": "gmail",
        "account": "me@example.test",
        "status": status,
        "autonomy": autonomy,
        "bar": BAR,
    }
    if split is not None:
        out["split"] = split
    return out


def facts(kind: TwinMessageKind = "reply", confidence: int = BAR, risks: tuple[str, ...] = ()) -> DraftFacts:
    return DraftFacts(kind=kind, confidence=confidence, risks=risks)


ALONE = Ruling("sent_alone", None)

# (the channel, the draft, live, the ruling)
TABLE: list[tuple[TwinChannel, DraftFacts, bool, Ruling]] = [
    # each level, unsplit, on a sure draft with no risk
    (channel("review"), facts(), True, Ruling("waits", "review")),
    (channel("assist"), facts(), True, Ruling("waits", "assist")),
    (channel("auto"), facts(), True, ALONE),
    # the bar's edge on Auto
    (channel("auto"), facts(confidence=BAR - 1), True, Ruling("waits", "below_bar")),
    (channel("auto"), facts(confidence=BAR), True, ALONE),
    (channel("auto"), facts(confidence=BAR + 1), True, ALONE),
    # a risk holds even the surest draft, and is named before the bar
    (channel("auto"), facts(confidence=99, risks=("Mentions a fee",)), True, Ruling("waits", "risk")),
    (channel("auto"), facts(confidence=BAR - 1, risks=("Mentions a fee",)), True, Ruling("waits", "risk")),
    # the level is named before a risk
    (channel("assist"), facts(risks=("Mentions a fee",)), True, Ruling("waits", "assist")),
    # paused: the twin is not live, or the channel is not connected, whatever else holds
    (channel("auto"), facts(confidence=99), False, Ruling("waits", "paused")),
    (channel("auto", status="needs_sign_in"), facts(confidence=99), True, Ruling("waits", "paused")),
    (channel("auto", status="disconnected"), facts(confidence=99), True, Ruling("waits", "paused")),
    (channel("review"), facts(risks=("x",)), False, Ruling("waits", "paused")),
    # a split decides the level per kind of message
    (channel("assist", {"first_message": "assist", "reply": "auto"}), facts("reply"), True, ALONE),
    (
        channel("assist", {"first_message": "assist", "reply": "auto"}),
        facts("first_message"),
        True,
        Ruling("waits", "first_message"),
    ),
    (
        channel("auto", {"first_message": "review", "reply": "auto"}),
        facts("first_message", confidence=99),
        True,
        Ruling("waits", "first_message"),
    ),
    (channel("review", {"first_message": "auto", "reply": "assist"}), facts("first_message"), True, ALONE),
    (
        channel("review", {"first_message": "auto", "reply": "assist"}),
        facts("reply"),
        True,
        Ruling("waits", "assist"),
    ),
    (
        channel("auto", {"first_message": "auto", "reply": "review"}),
        facts("reply", confidence=99),
        True,
        Ruling("waits", "review"),
    ),
    (
        channel("assist", {"first_message": "assist", "reply": "auto"}),
        facts("reply", confidence=BAR - 1),
        True,
        Ruling("waits", "below_bar"),
    ),
    (
        channel("assist", {"first_message": "assist", "reply": "auto"}),
        facts("reply", risks=("Agrees to exclusive rights",)),
        True,
        Ruling("waits", "risk"),
    ),
]


@pytest.mark.parametrize(("ch", "draft", "live", "ruling"), TABLE)
def test_the_send_rule(ch: TwinChannel, draft: DraftFacts, live: bool, ruling: Ruling) -> None:
    assert decide(ch, draft, twin_live=live) == ruling


def test_only_auto_sure_riskless_live_and_connected_goes_alone() -> None:
    """Every combination: sent alone exactly when all four hold, a reason exactly when it waits, and
    `paused` whenever the twin or the channel is."""
    for level, first, reply, kind, offset, risky, live, connected in itertools.product(
        (*LEVELS, None), LEVELS, LEVELS, KINDS, (-1, 0, 1), (False, True), (False, True), (False, True)
    ):
        split: AutonomySplit | None = None if level is not None else {"first_message": first, "reply": reply}
        ch = channel(level or "assist", split, "connected" if connected else "needs_sign_in")
        held = level if level is not None else (first if kind == "first_message" else reply)
        ruling = decide(ch, facts(kind, BAR + offset, ("a risk",) if risky else ()), twin_live=live)
        alone = live and connected and held == "auto" and offset >= 0 and not risky
        case = (level, first, reply, kind, offset, risky, live, connected)
        assert (ruling.decision == "sent_alone") is alone, case
        assert (ruling.reason is None) is alone, case
        if not (live and connected):
            assert ruling.reason == "paused", case
