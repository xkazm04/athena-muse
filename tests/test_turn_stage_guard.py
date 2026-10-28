"""The stage's AUTO actions (sketch, ask) are offered only on a design turn. Called anywhere else,
they do nothing - in particular they are never taken for `remember` and kept as a fact."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from athena.app import Daemon
from athena.contracts import EngineId, Probe
from athena.engine import TextDelta, ToolCall, Usage
from athena.turn import run_turn


class _StrayStage:
    """Calls `sketch` on the first round, whether offered or not; then answers in words."""

    id: EngineId = "scripted"
    model = "stray"
    simulated = True
    cost_estimated = False

    def __init__(self) -> None:
        self.rounds = 0

    def probe(self) -> Probe:
        return {"ok": True}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        self.rounds += 1
        if self.rounds == 1:
            yield ToolCall("c1", "sketch", {"op": "add", "label": "Pay the club"})
        else:
            yield TextDelta("Done.")


def test_sketch_outside_the_stage_writes_nothing() -> None:
    daemon = Daemon.open(None)
    space = daemon.spaces.create({"name": "Tea"})["id"]
    events = list(run_turn(daemon, _StrayStage(), "hello", space))
    assert not [e for e in events if e["type"] == "tool"]
    assert daemon.memory.page(space, "fact", 10)["rows"] == []
    assert events[-1]["type"] == "done"
