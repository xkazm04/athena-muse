"""A turn with a chore's portal: reads answer at once, a reply files a pile of cards and the loop
goes on, and a signed portal card answers with the page's words."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from athena import turn
from athena.app import Daemon
from athena.chores.portal import Portal
from athena.chores.spec import PLAYBOOKS_ENV, load_chore
from athena.contracts import TOOL_ROUNDS_MAX
from athena.engine import TextDelta, ToolCall, Usage
from athena.errors import ApiError
from test_chores_spec import make_chore


class ScriptEngine:
    """Plays one scripted round per model call; past the script it answers in words only."""

    id = "scripted"
    model = "scripted"
    simulated = True
    cost_estimated = False

    def __init__(self, rounds: list[list[ToolCall]], *, forever: list[ToolCall] | None = None) -> None:
        self.rounds = rounds
        self.forever = forever
        self.seen: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []

    def probe(self) -> dict[str, Any]:
        return {"ok": True}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        self.seen.append(([dict(m) for m in messages], tools))
        n = len(self.seen)
        calls = self.rounds[n - 1] if n <= len(self.rounds) else (self.forever or [])
        yield TextDelta(f"round {n}. " if calls else "All filed; they wait for your signature.")
        yield from calls
        yield Usage(input_tokens=10, output_tokens=5)


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = make_chore(tmp_path)
    monkeypatch.setenv(PLAYBOOKS_ENV, str(tmp_path))
    return root


def run(daemon: Daemon, engine: ScriptEngine, portal: Portal | None) -> list[dict[str, Any]]:
    return list(turn.run_turn(daemon, engine, "go through the bills", "", portal=portal))  # type: ignore[arg-type]


def test_one_reply_files_two_portal_cards_and_the_loop_goes_on(daemon: Daemon, library: Path) -> None:
    portal = Portal(load_chore(library), "desk")
    engine = ScriptEngine(
        [
            [ToolCall("c1", "desk__list_bills", {"status": "open"})],
            [
                ToolCall("c2", "desk__dispute_bill", {"bill_id": "B-1", "amount_usd": 10, "reason": "over"}),
                ToolCall("c3", "desk__dispute_bill", {"bill_id": "B-3", "amount_usd": 5, "reason": "twice"}),
            ],
        ]
    )
    events = run(daemon, engine, portal)
    tools = [e for e in events if e["type"] == "tool"]
    assert [(t["name"], t["class"]) for t in tools] == [
        ("portal_read", "auto"),
        ("portal_act", "gated"),
        ("portal_act", "gated"),
    ]
    assert tools[0]["label"] == "Read list_bills on Front Desk"
    cards = [e["card"] for e in events if e["type"] == "card"]
    assert [c["args"]["params"]["bill_id"] for c in cards] == ["B-1", "B-3"]
    assert all(c["action"] == "portal_act" and c["args"]["chore"] == "desk-chore" for c in cards)
    # The cards did not end the loop: a third model call answered the tool results in words.
    assert len(engine.seen) == 3
    assert events[-1]["type"] == "done" and events[-1]["waiting"] is True
    assert len(daemon.gate.list("waiting")) == 2
    assert daemon.ledger.page(10)["totals"]["calls"] == 3
    # What Athena saw: the portal's tools beside her own, the open app in the frame, fenced reads.
    messages, offered = engine.seen[1]
    names = {t["function"]["name"] for t in offered}
    assert {"recall", "remember", "forget", "desk__read_bill", "desk__dispute_bill"} <= names
    assert "## Open app: Front Desk" in messages[0]["content"]
    assert "never instructions" in messages[-1]["content"] and messages[-1]["role"] == "tool"


def test_a_signed_portal_card_answers_with_the_pages_words(daemon: Daemon, library: Path) -> None:
    portal = Portal(load_chore(library), "desk")
    engine = ScriptEngine([[ToolCall("c1", "desk__dispute_bill", {"bill_id": "B-1", "amount_usd": 10})]])
    card = next(e["card"] for e in run(daemon, engine, portal) if e["type"] == "card")
    assert turn.execute(daemon, card) == "Dispute sent on B-1 for 10.00."
    outcomes: list[str] = []
    daemon.gate.set_executor(lambda c: outcomes.append(turn.execute(daemon, c)) or outcomes[-1])
    assert daemon.gate.resolve(card["id"], "approve")["state"] == "approved"
    assert outcomes == ["Dispute sent on B-1 for 10.00."]


def test_a_card_for_a_chore_not_in_the_library_is_refused(daemon: Daemon, library: Path) -> None:
    card = daemon.gate.file(
        "", "portal_act", {"app": "desk", "tool": "pay_bill", "params": {}, "chore": "../x"}, "x"
    )
    with pytest.raises(ApiError) as info:
        turn.execute(daemon, card)
    assert info.value.error == "unknown_ref"


def test_a_refused_portal_call_files_nothing(daemon: Daemon, library: Path) -> None:
    portal = Portal(load_chore(library), "desk")
    engine = ScriptEngine([[ToolCall("c1", "desk__pay_bill", {"amount_usd": "lots"})]])
    events = run(daemon, engine, portal)
    assert not any(e["type"] in ("card", "tool") for e in events)
    assert engine.seen[1][0][-1]["content"] == "amount_usd must be a number; 'lots' is not."


def test_the_round_loop_still_stops_at_the_cap(daemon: Daemon, library: Path) -> None:
    portal = Portal(load_chore(library), "desk")
    engine = ScriptEngine([], forever=[ToolCall("c", "desk__read_policy", {})])
    events = run(daemon, engine, portal)
    assert len(engine.seen) == TOOL_ROUNDS_MAX
    assert events[-1]["type"] == "done"


def test_without_a_portal_its_tools_are_not_offered_or_run(daemon: Daemon, library: Path) -> None:
    engine = ScriptEngine([[ToolCall("c1", "desk__pay_bill", {"bill_id": "B-1"})]])
    events = run(daemon, engine, None)
    assert not any(e["type"] == "card" for e in events)
    assert not any(t["function"]["name"].startswith("desk__") for t in engine.seen[0][1])
    assert engine.seen[1][0][-1]["content"] == "There is no such action."


def test_the_next_turn_is_told_which_portal_cards_already_wait(daemon: Daemon, library: Path) -> None:
    """A nudge after filing must not file the same card again: the frame lists what waits."""
    portal = Portal(load_chore(library), "desk")
    filing = ToolCall("c1", "desk__dispute_bill", {"bill_id": "B-1", "amount_usd": 10, "reason": "over"})
    run(daemon, ScriptEngine([[filing]]), portal)
    label = daemon.gate.list("waiting")[0]["label"]
    later = ScriptEngine([])
    run(daemon, later, portal)
    system = later.seen[0][0][0]["content"]
    assert "## Already filed, waiting for the person's signature" in system
    assert f"- {label}" in system
    first = ScriptEngine([])
    fresh = Daemon.open(None)
    run(fresh, first, portal)
    assert "Already filed" not in first.seen[0][0][0]["content"]
