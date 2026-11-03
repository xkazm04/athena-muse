"""A turn keeps its moments and its stop (ADR 0024): each stored part says when it began, the Athena
turn how long it took, and a turn the engine stopped is kept with why, out of the model's history.
Record tool lines are said in plain words, and the report as other assistants see it has a route."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import mcp_views
from athena.app import Daemon
from athena.contracts import Probe
from athena.engine import EngineError, TextDelta, ToolCall, Usage
from athena.turn import dispatch, run_turn
from report_kit import project, stat, track


class _Clock:
    """The daemon's steady clock, moved by hand: the engine advances it as if it took that long."""

    def __init__(self) -> None:
        self.now = 50_000

    def __call__(self) -> int:
        return self.now


@pytest.fixture
def tick(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    c = _Clock()
    monkeypatch.setattr("athena.clock.monotonic_ms", c)
    return c


class _Engine:
    """Round one: thinks 1.5 s, says a line, takes 0.5 s more and keeps a fact. Round two: 3 s, then
    a closing line. Or, with `fail`, the second round fails with that reason."""

    id = "muse"
    model = "test"
    simulated = True
    cost_estimated = False

    def __init__(self, clock: _Clock, fail: str | None = None) -> None:
        self.clock = clock
        self.fail = fail
        self.rounds = 0
        self.seen: list[list[dict[str, Any]]] = []

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[Any]:
        self.rounds += 1
        self.seen.append([dict(m) for m in messages])
        if self.rounds == 1:
            self.clock.now += 1500
            yield TextDelta("Let me look. ")
            self.clock.now += 500
            yield ToolCall("t1", "remember", {"text": "Taxes are due in April"})
        else:
            self.clock.now += 3000
            if self.fail:
                raise EngineError(self.fail)
            yield TextDelta("Done.")
        yield Usage(input_tokens=10, output_tokens=2)

    def probe(self) -> Probe:
        return {"ok": True}


def test_each_part_keeps_its_moment_and_the_turn_its_length(daemon: Daemon, tick: _Clock) -> None:
    space = daemon.spaces.create({"name": "Taxes"})["id"]
    list(run_turn(daemon, _Engine(tick), "remember April", space))  # type: ignore[arg-type]
    person, athena = daemon.conversation.list(space)
    assert "duration_ms" not in person and "stopped" not in athena
    assert [(p["kind"], p.get("at_ms")) for p in athena["parts"]] == [
        ("text", 1500),
        ("tool", 2000),
        ("text", 5000),
    ]
    assert athena["duration_ms"] == 5000


def test_an_engine_error_keeps_the_stopped_turn_and_its_reason(
    daemon: Daemon, tick: _Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    published: list[dict[str, Any]] = []
    monkeypatch.setattr(daemon.events, "publish", published.append)
    space = daemon.spaces.create({"name": "Taxes"})["id"]
    reason = "Meta is rate limiting; try again in a minute"
    events = list(run_turn(daemon, _Engine(tick, fail=reason), "remember April", space))  # type: ignore[arg-type]
    assert events[-1] == {"type": "error", "error": "engine_unavailable", "reason": reason}

    person, athena = daemon.conversation.list(space)
    assert (person["role"], athena["role"]) == ("person", "athena")
    assert athena["stopped"] == reason and athena["text"] == "" and athena["duration_ms"] == 5000
    # what streamed before it stopped stays, with its moments
    assert [(p["kind"], p.get("at_ms")) for p in athena["parts"]] == [("text", 1500), ("tool", 2000)]
    assert "cost_usd" not in athena
    assert [e["type"] for e in published if e["type"] == "turn_done"] == ["turn_done"]


def test_the_next_turns_history_leaves_the_stopped_turn_out(daemon: Daemon, tick: _Clock) -> None:
    space = daemon.spaces.create({"name": "Taxes"})["id"]
    list(run_turn(daemon, _Engine(tick, fail="It stopped"), "first try", space))  # type: ignore[arg-type]
    again = _Engine(tick)
    list(run_turn(daemon, again, "second try", space))  # type: ignore[arg-type]
    history = [(m["role"], m["content"]) for m in again.seen[0][1:]]
    assert history == [("user", "first try"), ("user", "second try")]
    assert len(daemon.conversation.list(space)) == 4  # the page of the stopped try is still there
    assert [t["role"] for t in daemon.conversation.said(space, 10)] == ["person", "person", "athena"]


def test_a_turn_stored_without_moments_reads_back_without_them(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Taxes"})["id"]
    daemon.conversation.append(space, "athena", "Old words", parts=[{"kind": "text", "text": "Old words"}])
    (turn,) = daemon.conversation.list(space)
    assert turn["parts"] == [{"kind": "text", "text": "Old words"}]
    assert "duration_ms" not in turn and "stopped" not in turn


def test_record_tool_lines_are_said_in_plain_words(daemon: Daemon) -> None:
    sid = project(daemon)
    track(daemon, sid, 1)
    done = dispatch(daemon, sid, ToolCall("c1", "record_list", {"kind": "track"}))
    assert [e["label"] for e in done.events] == ["Looked through the songs"]
    everything = dispatch(daemon, sid, ToolCall("c2", "record_list", {}))
    assert [e["label"] for e in everything.events] == ["Looked through what the project keeps"]


def test_the_elsewhere_route_answers_what_show_report_answers(daemon: Daemon, client: TestClient) -> None:
    sid = project(daemon)
    track(daemon, sid, 1)
    stat(daemon, sid, "views", 120.0, "2026-10-01T00:00:00Z")
    got = client.get(f"/spaces/{sid}/report/elsewhere").json()
    tool = mcp_views.call(daemon, sid, "show_report")
    assert got["view"] == tool["structuredContent"]
    assert got["text"] == tool["content"][0]["text"]


def test_the_elsewhere_route_refuses_a_project_that_is_not_there(client: TestClient) -> None:
    r = client.get("/spaces/spc_000000000000/report/elsewhere")
    assert r.status_code == 404
