"""One bench run: a throwaway daemon, one project, the chore's phases walked turn by turn (ADR 0005).

Nothing is approved. A phase opens with its own message; while the last turn made any tool call and
the phase still has nudges, "Keep going." is sent. That decision reads the turn alone, never the
answer key. A turn that ends on an error ends the run, and the run is still scored.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from athena.app import Daemon
from athena.chores.portal import Portal
from athena.chores.spec import Chore
from athena.clock import now_iso
from athena.contracts import NAME_MAX, BenchSummary, BenchWord, Card, LedgerRow, Probe, Turn
from athena.engine import Engine, EngineError, TextDelta, ToolCall, Usage
from athena.errors import ApiError
from athena.turn import run_turn

NUDGE = "Keep going."
WALL_MIN_DEFAULT = 20.0
LEDGER_ALL = 1_000_000


@dataclass(frozen=True)
class TurnLog:
    phase: int  # 1-based
    turn: int  # 1-based, across the whole run
    app: str
    message: str
    calls: int  # tool calls the engine made in this turn
    cards: int  # portal cards filed in this turn
    error: str = ""


@dataclass(frozen=True)
class Rehearsal:
    summary: BenchSummary
    cards: list[Card]
    ledger: tuple[dict[str, Any], ...]  # the score's judgement, one row per card
    missed: tuple[str, ...]
    exact: int
    turns: list[TurnLog]
    transcript: list[Turn]
    calls: list[LedgerRow]  # the daemon's model-call ledger, oldest first
    ended: str = ""  # why the run stopped early, when it did
    stamp: str = field(default="")


class _Counting:
    """Wraps the engine to count the tool calls of the current turn and to stop at the wall clock."""

    def __init__(self, inner: Engine, deadline: float) -> None:
        self.inner = inner
        self.id = inner.id
        self.model = inner.model
        self.simulated = inner.simulated
        self.cost_estimated = inner.cost_estimated
        self.deadline = deadline
        self.calls = 0

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        if time.monotonic() >= self.deadline:
            raise EngineError("the bench's wall clock ran out")
        for chunk in self.inner.complete(messages, tools):
            if isinstance(chunk, ToolCall):
                self.calls += 1
            yield chunk

    def probe(self) -> Probe:
        return self.inner.probe()


def _space_name(chore: Chore) -> str:
    name = " ".join(str(chore.showcase.get("title") or chore.id).split())
    return name[:NAME_MAX] or chore.id[:NAME_MAX]


def _cost(rows: list[LedgerRow]) -> float | None:
    """The summed cost of the run's model calls; None when any call that ran was unpriced."""
    ran = [r for r in rows if r["ok"]]
    if not ran or any("cost_usd" not in r for r in ran):
        return None
    return round(sum(r.get("cost_usd", 0.0) for r in ran), 4)


def rehearse(
    chore: Chore,
    engine: Engine,
    *,
    wall_min: float = WALL_MIN_DEFAULT,
    on_turn: Callable[[TurnLog], None] | None = None,
) -> Rehearsal:
    from athena.bench import score, verdict

    run_at = now_iso()
    started = time.monotonic()
    counting = _Counting(engine, started + wall_min * 60)
    daemon = Daemon.open(None)
    try:
        space_id = daemon.spaces.create({"name": _space_name(chore)})["id"]
        logs: list[TurnLog] = []
        ended = ""
        n = 0
        for p, phase in enumerate(chore.phases, start=1):
            portal = Portal(chore, phase.app)
            message = phase.message
            nudges_left = phase.nudges
            while True:
                n += 1
                counting.calls = 0
                filed = 0
                error = ""
                try:
                    for event in run_turn(daemon, counting, message, space_id, portal=portal):
                        if event.get("type") == "card" and event["card"]["action"] == "portal_act":
                            filed += 1
                        elif event.get("type") == "error":
                            error = str(event.get("reason") or event.get("error") or "unknown")
                except ApiError as e:
                    error = e.reason
                log = TurnLog(p, n, phase.app, message, counting.calls, filed, error)
                logs.append(log)
                if on_turn is not None:
                    on_turn(log)
                if error:
                    ended = f"the run ended on an error: {error}"
                    break
                if log.calls == 0 or nudges_left <= 0:
                    break
                nudges_left -= 1
                message = NUDGE
            if ended:
                break

        minutes = round((time.monotonic() - started) / 60, 2)
        cards = [c for c in reversed(daemon.gate.list()) if c["action"] == "portal_act"]
        s = score(chore, cards)
        word, reasons = verdict(chore, s, minutes)
        if ended:
            reasons.append(ended)
        calls = list(reversed(daemon.ledger.page(LEDGER_ALL)["rows"]))
        summary: BenchSummary = {
            "verdict": cast(BenchWord, word),
            "reasons": reasons,
            "found": s.found,
            "eligible": s.eligible,
            "value_found_usd": s.value_found_usd,
            "value_total_usd": s.value_total_usd,
            "false_claims": s.false_claims,
            "duplicates": s.duplicates,
            "traps_filed": s.traps_filed,
            "turns": len(logs),
            "minutes": minutes,
            "engine": engine.id,
            "model": engine.model,
            "run_at": run_at,
        }
        cost = _cost(calls)
        if cost is not None:
            summary["cost_usd"] = cost
        return Rehearsal(
            summary=summary,
            cards=cards,
            ledger=s.ledger,
            missed=s.missed,
            exact=s.exact,
            turns=logs,
            transcript=daemon.conversation.list(space_id, LEDGER_ALL),
            calls=calls,
            ended=ended,
            stamp=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        )
    finally:
        daemon.store.close()


def bench_doc(run: Rehearsal) -> dict[str, Any]:
    """`bench.json`: the summary, the cards as filed (label and args) and how each was judged."""
    return {
        **run.summary,
        "cards": [{"label": c["label"], "args": c["args"]} for c in run.cards],
        "ledger": list(run.ledger),
    }


def _dump(path: Path, doc: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_bench(chore: Chore, run: Rehearsal) -> Path:
    return _dump(chore.root / "bench.json", bench_doc(run))


def runs_dir(chore: Chore) -> Path:
    """`runs/` beside the library (`playbooks/` -> the repo root); git-ignored."""
    return chore.root.resolve().parent.parent / "runs"


def write_report(chore: Chore, run: Rehearsal) -> Path:
    """The full run, transcript included, under `runs/<stamp>-<id>/report.json` (never committed)."""
    doc = {
        "chore": chore.id,
        **bench_doc(run),
        "missed": list(run.missed),
        "exact": run.exact,
        "turn_log": [t.__dict__ for t in run.turns],
        "transcript": run.transcript,
        "model_calls": run.calls,
    }
    return _dump(runs_dir(chore) / f"{run.stamp}-{chore.id}" / "report.json", doc)
