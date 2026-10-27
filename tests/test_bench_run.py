"""A full bench run with a scripted test double: the phase walk, the nudge rule, scoring, bench.json."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from athena.bench import run_bench, runner
from athena.chores.spec import App, Chore, Phase, Target, Tool
from athena.contracts import EngineId, Probe
from athena.engine import TextDelta, ToolCall, Usage


def _gated(name: str) -> Tool:
    return Tool(
        name=name,
        kind="REACHES_A_PERSON",
        description="Dispute a bill. Reaches the billing office.",
        params={"bill_id": {"type": "string"}, "amount_usd": {"type": "number"}},
        says="Disputed {bill_id}.",
    )


def demo_chore(root: Path) -> Chore:
    return Chore(
        id="demo",
        root=root,
        showcase={"id": "demo", "title": "Demo chore", "expectation": {"recall": 0.5, "false_claims": 0}},
        today="2026-10-26",
        apps=(
            App("first", "First portal", "https://first.example", (_gated("dispute_bill"),)),
            App("second", "Second portal", "https://second.example", (_gated("dispute_bill"),)),
        ),
        tables={},
        phases=(
            Phase("first", "TRIGGER-ONE: look at the first portal.", nudges=2),
            Phase("second", "TRIGGER-TWO: now the second.", nudges=3),
        ),
        targets=(
            Target(
                tool="dispute_bill",
                key="bill_id",
                eligible={
                    "A-1": {"value_usd": 100.0, "why": "over", "expect": {"amount_usd": 100.0}},
                    "B-2": {"value_usd": 40.0, "why": "duplicate", "expect": {"amount_usd": 40.0}},
                    "C-3": {"value_usd": 10.0, "why": "never filed"},
                },
                traps={},
            ),
        ),
    )


class Double:
    """Files one card on a trigger; after a tool result, or on a nudge, it only talks.

    `nudge_calls` makes the first nudge in phase two call a tool again, to prove the bench keeps
    nudging only while the last turn called tools."""

    id: EngineId = "scripted"
    model = "double"
    simulated = True
    cost_estimated = False

    def __init__(self) -> None:
        self.persons: list[str] = []

    def probe(self) -> Probe:
        return {"ok": True}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        offered = {t["function"]["name"] for t in tools}
        last = messages[-1]
        call: ToolCall | None = None
        if last["role"] != "tool":
            person = str(last.get("content") or "")
            self.persons.append(person)
            if "TRIGGER-ONE" in person and "first__dispute_bill" in offered:
                call = ToolCall("c1", "first__dispute_bill", {"bill_id": "a-1", "amount_usd": 100})
            elif "TRIGGER-TWO" in person and "second__dispute_bill" in offered:
                call = ToolCall("c2", "second__dispute_bill", {"bill_id": "B-2", "amount_usd": "41"})
            elif person == runner.NUDGE and self.persons.count(runner.NUDGE) == 2:
                call = ToolCall("c3", "second__dispute_bill", {"bill_id": "B-2", "amount_usd": 40})
        yield TextDelta("Working on it.")
        if call is not None:
            yield call
        yield Usage(input_tokens=10, output_tokens=5, cost_usd=0.01)


def test_a_full_run_walks_phases_nudges_scores_and_writes(tmp_path: Path) -> None:
    root = tmp_path / "playbooks" / "demo"
    root.mkdir(parents=True)
    double = Double()
    seen: list[runner.TurnLog] = []
    run = runner.rehearse(demo_chore(root), double, on_turn=seen.append)

    # Phase one: the trigger calls a tool, so one nudge; the nudge calls none, so the phase ends with a
    # nudge left. Phase two: trigger, nudge (calls again), nudge (calls none): three turns.
    assert double.persons == [
        "TRIGGER-ONE: look at the first portal.",
        runner.NUDGE,
        "TRIGGER-TWO: now the second.",
        runner.NUDGE,
        runner.NUDGE,
    ]
    assert [(t.phase, t.turn, t.calls, t.cards) for t in seen] == [
        (1, 1, 1, 1),
        (1, 2, 0, 0),
        (2, 3, 1, 1),
        (2, 4, 1, 1),
        (2, 5, 0, 0),
    ]
    s = run.summary
    assert [r["judged"] for r in run.ledger] == ["exact", "found", "duplicate"]
    assert (s["found"], s["eligible"], s["false_claims"], s["duplicates"]) == (2, 3, 0, 1)
    assert (s["value_found_usd"], s["value_total_usd"]) == (140.0, 150.0)
    assert s["verdict"] == "meets" and run.missed == ("C-3",)
    assert s["turns"] == 5 and s["engine"] == "scripted" and s["model"] == "double"
    assert s["cost_usd"] > 0 and s["run_at"].endswith("Z")

    path = runner.write_bench(demo_chore(root), run)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert path == root / "bench.json"
    summary_keys = {
        "verdict", "reasons", "found", "eligible", "value_found_usd", "value_total_usd", "false_claims",
        "duplicates", "traps_filed", "turns", "minutes", "engine", "model", "run_at", "cost_usd",
    }  # fmt: skip
    assert set(doc) == summary_keys | {"cards", "ledger"}
    assert doc["cards"][0]["args"]["tool"] == "dispute_bill" and "transcript" not in doc
    assert set(doc["ledger"][0]) == {"tool", "key", "judged", "why"}


def test_run_bench_writes_both_files_and_a_turn_error_ends_the_run(tmp_path: Path) -> None:
    class Failing(Double):
        def complete(
            self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
        ) -> Iterator[TextDelta | ToolCall | Usage]:
            from athena.engine import EngineError

            raise EngineError("the model is down")
            yield  # pragma: no cover

    root = tmp_path / "playbooks" / "demo"
    root.mkdir(parents=True)
    summary = run_bench(demo_chore(root), Failing())
    assert summary["turns"] == 1 and summary["verdict"] == "short"
    assert summary["reasons"][-1] == "the run ended on an error: the model is down"
    assert "cost_usd" not in summary  # no call was priced
    assert (root / "bench.json").exists()
    reports = list((tmp_path / "runs").glob("*-demo/report.json"))
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["transcript"][0]["text"].startswith("TRIGGER-ONE")


def test_no_write_touches_nothing(tmp_path: Path) -> None:
    root = tmp_path / "playbooks" / "demo"
    root.mkdir(parents=True)
    run_bench(demo_chore(root), Double(), write=False)
    assert list(tmp_path.rglob("*.json")) == []


def test_the_wall_clock_ends_the_run(tmp_path: Path) -> None:
    run = runner.rehearse(demo_chore(tmp_path), Double(), wall_min=0)
    assert run.summary["turns"] == 1
    assert run.ended == "the run ended on an error: the bench's wall clock ran out"


@pytest.fixture(autouse=True)
def _quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATHENA_ENGINE", raising=False)
