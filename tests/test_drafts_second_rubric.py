"""A second rubric on the same shaping machinery (ADR 0010): a toy with three places and its own kinds
runs a scripted design turn end to end through `run_turn`, ledgered on the toy design's surface."""

from __future__ import annotations

from typing import Any, ClassVar, cast

import pytest

from athena.app import Daemon
from athena.contracts import SketchOp, Surface
from athena.drafts.rubric import CHORE_RUBRIC, Rubric
from athena.drafts.shape import SketchDesign
from athena.drafts.sketch import SketchError, apply, empty
from athena.engine.scripted import ScriptedEngine
from athena.turn import run_turn

TOY = Rubric(
    places=("dish", "pantry", "guests"),
    required={"dish": 1, "pantry": 0.5, "guests": 0},
    meaning={
        "dish": "what to cook, in the person's words",
        "pantry": "what is already in the cupboard",
        "guests": "who comes to eat",
    },
    kinds=("idea", "item", "person"),
    allowed={"dish": ("idea",), "pantry": ("item",), "guests": ("person", "idea")},
)
NEED = "Cook a green curry for six friends"


class Dinner(SketchDesign):
    """The toy's design: kept in memory, settled into a coverage line over its own places."""

    surface: ClassVar[Surface] = "twin"
    rules: ClassVar[str] = "## Planning a dinner with the person"
    subject: ClassVar[str] = "the person's dinner"

    def settle(self) -> list[dict[str, Any]]:
        cov = self.rubric.coverage(self.sketch, self.skipped)
        return [{"type": "coverage", "coverage": cov, "agreed": self.rubric.agreed(cov)}]


def of(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e for e in events if e["type"] == kind]


def node(node_id: str, slot: str, kind: str) -> SketchOp:
    raw = {"id": node_id, "kind": kind, "slot": slot, "label": "Rice", "origin": "athena", "confirmed": False}
    return cast("SketchOp", {"op": "add", "node": raw})


def test_a_toy_rubric_runs_a_scripted_design_turn_end_to_end(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Dinner"})["id"]
    design = Dinner(daemon, TOY, empty(), NEED, space)
    tools = design.tools()
    assert tools[0]["function"]["parameters"]["properties"]["kind"]["description"].startswith(
        "idea, item or person"
    )
    assert tools[1]["function"]["parameters"]["properties"]["slot"]["description"] == "dish, pantry or guests"

    events = list(run_turn(daemon, ScriptedEngine(), NEED, space, design=design))
    assert events[0]["type"] == "start" and events[-1]["type"] == "done"
    drawn = of(events, "sketch")[0]["ops"][0]["node"]
    assert (drawn["slot"], drawn["kind"], drawn["origin"], drawn["confirmed"]) == (
        "dish",
        "idea",
        "you",
        True,
    )
    assert drawn["quote"] == NEED  # proved verbatim against the person's own words
    ask = of(events, "ask")[0]["ask"]
    assert ask["slot"] == "pantry" and ask["text"] == "What about what is already in the cupboard?"
    assert of(events, "coverage") == [
        {"type": "coverage", "coverage": {"dish": 1, "pantry": 0, "guests": 0}, "agreed": False}
    ]
    rows = daemon.ledger.page(10)["rows"]
    assert rows and {r["surface"] for r in rows} == {"twin"} and {r["space_id"] for r in rows} == {space}

    # The next turn proposes the pantry in pencil on its usual kind; guests may stay empty, so it is done.
    after = Dinner(daemon, TOY, design.sketch, NEED, space, asked=design.asked_after())
    events = list(run_turn(daemon, ScriptedEngine(), "Rice, I think", space, design=after))
    guess = of(events, "sketch")[0]["ops"][0]["node"]
    assert (guess["slot"], guess["kind"], guess["origin"], guess["confirmed"]) == (
        "pantry",
        "item",
        "athena",
        False,
    )
    assert of(events, "coverage")[0]["coverage"] == {"dish": 1, "pantry": 0.5, "guests": 0}
    assert of(events, "coverage")[0]["agreed"] is True


def test_the_toy_rubric_checks_kinds_and_places() -> None:
    with pytest.raises(SketchError, match="the kind must be one of idea, item, person"):
        apply(empty(), [node("a", "dish", "step")], TOY)
    with pytest.raises(SketchError, match="the slot must be one of dish, pantry, guests"):
        apply(empty(), [node("a", "need", "idea")], TOY)
    with pytest.raises(SketchError, match="a node in dish is one of idea, not item"):
        apply(empty(), [node("a", "dish", "item")], TOY)
    sketch, _ = apply(empty(), [node("a", "guests", "idea")], TOY)
    moved = cast("SketchOp", {"op": "change", "node": {"id": "a", "slot": "pantry"}})
    with pytest.raises(SketchError, match="a node in pantry is one of item, not idea"):
        apply(sketch, [moved], TOY)
    # the chore lets any of its kinds sit in any slot, as before
    apply(empty(), [node("a", "never", "app")], CHORE_RUBRIC)


def test_what_each_place_requires() -> None:
    done = {"dish": 1, "pantry": 0.5, "guests": 0}
    assert TOY.agreed(done) and TOY.missing(done) == []
    assert TOY.agreed({**done, "pantry": "skipped"})  # left open meets a 0.5
    assert not TOY.agreed({**done, "dish": "skipped"})  # but never a 1
    assert TOY.missing({**done, "dish": 0.5, "pantry": 0}) == ["dish", "pantry"]
    assert TOY.open_places(done) == ["pantry", "guests"]


def test_a_rubric_names_each_place_once_in_every_table() -> None:
    with pytest.raises(ValueError, match="meaning"):
        Rubric(TOY.places, TOY.required, {"dish": "x"}, TOY.kinds, TOY.allowed)
    with pytest.raises(ValueError, match=r"0, 0\.5 or 1"):
        Rubric(TOY.places, {**TOY.required, "guests": 0.7}, TOY.meaning, TOY.kinds, TOY.allowed)
    with pytest.raises(ValueError, match="kinds"):
        Rubric(TOY.places, TOY.required, TOY.meaning, TOY.kinds, {**TOY.allowed, "dish": ("dragon",)})
