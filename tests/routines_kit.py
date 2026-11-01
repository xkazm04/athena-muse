"""Shared by the routine host tests (business Phase 2): a project that keeps records, an engine that
answers JSON at a set price (or none), a host over the daemon, and a fake kind registered in place of
a real one."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from athena.app import Daemon
from athena.engine import Engine, TextDelta, ToolCall, Usage
from athena.routines import kinds
from athena.routines.context import RunContext
from athena.routines.host import Host
from records_kit import project

__all__ = ["PricedEngine", "host", "kind", "project", "watch_of"]


class PricedEngine:
    """Answers every call with `answer` as JSON, at `cost` US dollars (None: the engine gives no price)."""

    id = "scripted"
    model = "scripted"
    simulated = True
    cost_estimated = False

    def __init__(self, cost: float | None = 0.01, answer: dict[str, Any] | None = None) -> None:
        self.cost = cost
        self.answer = answer if answer is not None else {"items": []}
        self.calls = 0

    def probe(self) -> dict[str, Any]:
        return {"ok": True}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        assert tools == []  # a routine's model call has no tools
        self.calls += 1
        yield TextDelta(json.dumps(self.answer))
        yield Usage(input_tokens=10, output_tokens=5, cost_usd=self.cost)


def host(daemon: Daemon, engine: Engine | None = None, tick_s: float = 30.0) -> Host:
    built = engine if engine is not None else PricedEngine()
    return Host(daemon, lambda: built, tick_s=tick_s)


def kind(monkeypatch: pytest.MonkeyPatch, fn: Callable[[RunContext], None], name: str = "watch") -> None:
    """Registers `fn` as the routine kind `name` for the test."""
    monkeypatch.setitem(kinds.RUN, name, fn)  # type: ignore[arg-type]


def watch_of(daemon: Daemon, space_id: str) -> str:
    """The project's watch routine (its defaults ensured)."""
    found = [r for r in daemon.routines.ensure_defaults(space_id) if r["kind"] == "watch"]
    assert found, "the project keeps creator and track records, so it has a watch routine"
    return found[0]["id"]
