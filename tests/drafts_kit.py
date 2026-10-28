"""Shared by the authoring, key and test-run tests: an agreed draft of the staged need, a chore an
author model would write for it, and a stand-in engine that answers each step by what it is asked."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from athena.app import Daemon
from athena.contracts import Draft, EngineId, Probe
from athena.drafts.demo import NEED, seed
from athena.engine import EngineError, TextDelta, ToolCall, Usage

__all__ = ["NEED", "Fake", "agreed_draft", "chore_answer", "data_daemon"]


def agreed_draft(daemon: Daemon) -> Draft:
    """The staged need at `shape`, its sketch agreed, as the demo seeds it."""
    stored = seed(daemon)
    assert stored["agreed"]
    return stored


def playbook() -> dict[str, Any]:
    return {
        "title": "The club invoice checked against attendance",
        "short_title": "Club invoice check",
        "promise": "Every billed day the kids did not attend is disputed with the club, on your signature.",
        "category": "family",
        "job": "contest",
        "brief": "She compares the club's invoice with the school's attendance and disputes extra days.",
        "persona": "A parent with two kids in an after-school club",
        "expectation": {"recall": 0.75, "false_claims": 0, "minutes": 20, "why": "A careful parent."},
    }


def world() -> dict[str, Any]:
    return {
        "today": "2026-10-28",
        "apps": [
            {
                "app_id": "school",
                "name": "Maple School portal",
                "origin": "https://portal.maple-school.example",
                "view": {"view": "Attendance, October"},
                "tools": [
                    {
                        "name": "list_attendance",
                        "kind": "READ",
                        "description": "Attendance days by child.",
                        "params": {"child": {"type": "string"}},
                        "returns": {"table": "attendance", "match": {"child": "child"}},
                    }
                ],
            },
            {
                "app_id": "club",
                "name": "Sunbeam Club billing",
                "origin": "https://billing.sunbeam-club.example",
                "tools": [
                    {
                        "name": "read_invoice",
                        "kind": "READ",
                        "description": "The October invoice, one row per billed day.",
                        "params": {},
                        "returns": {"table": "invoice_lines"},
                    },
                    {
                        "name": "dispute_day",
                        "kind": "REACHES_A_PERSON",
                        "description": "Dispute one billed day with the club office.",
                        "params": {
                            "reason": {"type": "string"},
                            "line_id": {"type": "string", "key": True},
                        },
                        "says": "Your dispute of {line_id} is with the club office.",
                    },
                    {
                        "name": "pay_invoice",
                        "kind": "PERMANENT",
                        "description": "Pay the whole invoice.",
                        "params": {"invoice_id": {"type": "string"}},
                        "says": "Paid {invoice_id}.",
                    },
                ],
            },
        ],
        "tables": {
            "attendance": [
                {"date": "2026-10-05", "child": "Ada", "present": True},
                {"date": "2026-10-06", "child": "Ada", "present": False},
                {"date": "2026-10-07", "child": "Ben", "present": False},
            ],
            "invoice_lines": [
                {"line_id": "L1", "date": "2026-10-05", "child": "Ada", "amount_usd": 18},
                {"line_id": "L2", "date": "2026-10-06", "child": "Ada", "amount_usd": 18},
                {"line_id": "L3", "date": "2026-10-07", "child": "Ben", "amount_usd": 18},
            ],
        },
        "phases": [
            {"app": "school", "message": "Here is the school portal: look at who went when.", "nudges": 0},
            {
                "app": "club",
                "message": "Now the club's invoice: dispute any day they did not go.",
                "nudges": 0,
            },
        ],
    }


def chore_answer(edit: Any = None, *, fenced: bool = False) -> str:
    """An author model's answer; `edit(playbook, world)` breaks it on purpose."""
    pb, w = copy.deepcopy(playbook()), copy.deepcopy(world())
    if edit is not None:
        edit(pb, w)
    body = json.dumps({"playbook": pb, "world": w})
    return f"Here it is.\n```json\n{body}\n```\nDone." if fenced else body


def broken_table(_: dict[str, Any], w: dict[str, Any]) -> None:
    """A READ tool that reads a table the world does not have, and no phases."""
    w["apps"][0]["tools"][0]["returns"]["table"] = "register"
    w["phases"] = []


PREVIEW_ANSWER = json.dumps(
    {
        "expected": [
            {
                "app": "club",
                "tool": "dispute_day",
                "key": "L2",
                "label": "Dispute Oct 6",
                "why": "Ada was away.",
            },
            {
                "app": "club",
                "tool": "dispute_day",
                "key": "L3",
                "label": "Dispute Oct 7",
                "why": "Ben was away.",
            },
            {"app": "club", "tool": "dispute_day", "key": "l3", "label": "again", "why": "a duplicate"},
            {"app": "club", "tool": "refund_all", "key": "L1", "label": "no such tool", "why": "invented"},
            {
                "app": "school",
                "tool": "list_attendance",
                "key": "Ada",
                "label": "a read",
                "why": "not an act",
            },
            {"app": "club", "tool": "dispute_day", "key": "L1", "label": "Dispute Oct 5", "why": "Unsure."},
        ]
    }
)


class Fake:
    """A stand-in model that answers each step by what it is asked: the author (a queue of answers),
    the preview, the placement of the person's lines, and the test run's portal turns (it files a
    dispute for each line in `files` once per phase on the club)."""

    id: EngineId = "scripted"
    model = "fake"
    simulated = True
    cost_estimated = False

    def __init__(
        self,
        authored: list[str] | None = None,
        *,
        preview: str = PREVIEW_ANSWER,
        place: str = "{}",
        files: tuple[str, ...] = ("L2", "L3"),
        fail: str = "",
    ) -> None:
        self.authored = list(authored if authored is not None else [chore_answer()])
        self.preview = preview
        self.place = place
        self.files = files
        self.fail = fail  # "author", "preview", "place" or "run": that step's calls raise
        self.asked: list[list[dict[str, Any]]] = []

    def probe(self) -> Probe:
        return {"ok": True}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        self.asked.append(messages)
        system = str(messages[0]["content"])
        if tools:
            step = "run"
        elif "You write one chore" in system:
            step = "author"
        elif "Before a test run" in system:
            step = "preview"
        else:
            step = "place"
        if step == self.fail:
            raise EngineError("Claude Code stopped")
        if step == "author":
            yield TextDelta(self.authored.pop(0) if len(self.authored) > 1 else self.authored[0])
        elif step == "preview":
            yield TextDelta(self.preview)
        elif step == "place":
            yield TextDelta(self.place)
        else:
            offered = {t["function"]["name"] for t in tools}
            if messages[-1]["role"] != "tool" and "club__dispute_day" in offered:
                yield TextDelta("Filing the disputes.")
                for i, line in enumerate(self.files):
                    yield ToolCall(f"c{i}", "club__dispute_day", {"line_id": line, "reason": "absent"})
            else:
                yield TextDelta("Read it.")
        yield Usage(input_tokens=100, output_tokens=20, cost_usd=0.01)


def data_daemon(tmp_path: Path) -> Daemon:
    return Daemon.open(tmp_path / "data")
