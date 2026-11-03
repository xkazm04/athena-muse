"""A settled turn keeps its parts (her window): text runs, tool lines and cards in the order they
streamed, so the window draws it after a reload as it drew it live. Turns stored before parts were
kept read back exactly as before."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from athena.app import Daemon
from athena.contracts import Probe
from athena.conversation import Conversation
from athena.engine import TextDelta, ToolCall, Usage
from athena.store import Store
from athena.turn import run_turn


class _Engine:
    """Words, a kept fact, more words, then a brief to sign (which ends the rounds)."""

    id = "muse"
    model = "test"
    simulated = True
    cost_estimated = False

    def __init__(self) -> None:
        self.rounds = 0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[Any]:
        self.rounds += 1
        if self.rounds == 1:
            yield TextDelta("Let me ")
            yield TextDelta("note it.")
            yield ToolCall("t1", "remember", {"text": "Taxes are due in April"})
        else:
            yield TextDelta("Noted. ")
            yield ToolCall("t2", "propose_brief", {"brief": "File by April"})
        yield Usage(input_tokens=10, output_tokens=2)

    def probe(self) -> Probe:
        return {"ok": True}


def test_a_settled_turn_keeps_its_parts_in_the_order_they_streamed(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Taxes"})["id"]
    events = list(run_turn(daemon, _Engine(), "remember April", space))  # type: ignore[arg-type]
    streamed = [e["type"] for e in events if e["type"] in ("text", "tool", "card")]
    assert streamed == ["text", "text", "tool", "text", "tool", "card"]
    card_id = next(e["card"]["id"] for e in events if e["type"] == "card")

    person, athena = daemon.conversation.list(space)
    assert "parts" not in person
    assert athena["parts"] == [
        {"kind": "text", "text": "Let me note it."},
        {"kind": "tool", "name": "remember", "label": "Remembered: Taxes are due in April", "class": "auto"},
        {"kind": "text", "text": "Noted. "},
        {
            "kind": "tool",
            "name": "propose_brief",
            "label": "Change this project's brief to: File by April",
            "class": "gated",
        },
        {"kind": "card", "card_id": card_id},
    ]
    # the whole reply stays the turn's text, which the next turn's history reads
    assert athena["text"] == "Let me note it.Noted." and athena["card_id"] == card_id


def test_a_turn_with_no_words_keeps_the_line_it_said(daemon: Daemon) -> None:
    class Quiet(_Engine):
        def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[Any]:
            yield Usage(input_tokens=1, output_tokens=0)

    space = daemon.spaces.create({"name": "Taxes"})["id"]
    list(run_turn(daemon, Quiet(), "anything?", space))  # type: ignore[arg-type]
    athena = daemon.conversation.list(space)[-1]
    assert athena["parts"] == [{"kind": "text", "text": "I have nothing to add."}]


def test_turns_stored_before_parts_read_back_as_before(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(
        "CREATE TABLE turns (id TEXT PRIMARY KEY, space_id TEXT NOT NULL, role TEXT NOT NULL, "
        "text TEXT NOT NULL, created TEXT NOT NULL, cost_usd REAL, card_id TEXT);"
        "INSERT INTO turns VALUES ('turn_old', 'spc_1', 'athena', 'By April.', '2026-10-01T00:00:00Z', "
        "0.0004, 'card_1');"
    )
    old.close()
    store = Store(path)  # the migration adds the column; the old row keeps no parts
    turns = Conversation(store).list("spc_1")
    assert turns == [
        {
            "id": "turn_old",
            "space_id": "spc_1",
            "role": "athena",
            "text": "By April.",
            "created": "2026-10-01T00:00:00Z",
            "cost_usd": 0.0004,
            "card_id": "card_1",
        }
    ]
    # a row whose parts do not read is shown as its text, never an error
    store.run("UPDATE turns SET parts = 'not json' WHERE id = 'turn_old'")
    assert "parts" not in Conversation(store).list("spc_1")[0]
    store.close()
