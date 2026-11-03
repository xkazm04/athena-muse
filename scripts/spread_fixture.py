"""The book's fixture for the desktop preview (ADR 0024): the simulated music channel seeded by
scripts/business_fixture.py, and a conversation played through the daemon's own turn loop
(`turn.run_turn`) by a stand-in engine that says authored words and calls real tools. Everything
around the words is the daemon's: the tool lines, the cards (filed and one signed through the real
gate), the report parts through the show_blocks door, the stopped try kept with its reason, the
estimated costs, the report's view and what show_report answers another assistant. Each part's moment
comes from the daemon's clock, which the stand-in moves by an authored pacing: the timings are
authored, not measured, and the preview says so. Never edit the output by hand.

    uv run python scripts/spread_fixture.py apps/desktop/src/spread/fixture.json
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from business_fixture import BRIEF, CREATORS, channel_url, seed  # noqa: E402

from athena import clock, mcp_views  # noqa: E402
from athena.app import Daemon  # noqa: E402
from athena.engine import EngineError, TextDelta, ToolCall, Usage  # noqa: E402
from athena.engine.scripted import _chunks  # noqa: E402
from athena.report import compose  # noqa: E402
from athena.turn import execute, run_turn  # noqa: E402

FIXTURE = (
    "Fixture: a simulated music channel. Her words and the pace of each turn were written ahead and "
    "played through the daemon's real turn loop by a stand-in engine; every tool line, card, figure "
    "and est. cost is the daemon's own. The timings are authored, not measured."
)

DELTA_MS = 70  # authored: each three-word delta


class Clock:
    """The daemon's steady clock, moved by the stand-in as if it took that long."""

    def __init__(self) -> None:
        self.now = 1_000_000

    def __call__(self) -> int:
        return self.now


class StandIn:
    """Plays authored rounds: ("text", words), ("call", name, args) or ("fail", reason). Before each
    round's first output the clock moves by that round's think time. Tokens are chars / 4 of what the
    loop really sent, so the est. cost is the price table's over real message sizes."""

    id = "muse"
    model = "muse-spark-1.3"
    simulated = False
    cost_estimated = True

    def __init__(self, tick: Clock, rounds: list[list[tuple[Any, ...]]], think: list[int]) -> None:
        self.tick = tick
        self.rounds = list(rounds)
        self.think = list(think)
        self.n = 0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[Any]:
        self.tick.now += self.think.pop(0) if self.think else 900
        rnd = self.rounds.pop(0) if self.rounds else [("text", "")]
        out = 0
        for item in rnd:
            if item[0] == "fail":
                raise EngineError(item[1])
            if item[0] == "text":
                out += len(item[1])
                for chunk in _chunks(item[1]):
                    self.tick.now += DELTA_MS
                    yield TextDelta(chunk)
            else:
                self.n += 1
                out += len(item[1]) + len(json.dumps(item[2]))
                yield ToolCall(f"call_{self.n}", item[1], item[2])
        sent = len(json.dumps(messages)) + len(json.dumps(tools))
        yield Usage(math.ceil(sent / 4), math.ceil(out / 4))

    def probe(self) -> Any:
        return {"ok": True}


PIPELINE = {
    "kind": "pipeline",
    "title": "From offer to release",
    "config": {
        "stages": [
            {"label": "Offered", "binding": {"kind": "agreement", "filter": {"state": "proposed"}}},
            {"label": "Agreed", "binding": {"kind": "agreement", "filter": {"state": "agreed"}}},
            {"label": "Video made", "binding": {"kind": "render", "filter": {"state": "rendered"}}},
            {"label": "Released", "binding": {"kind": "release"}},
        ]
    },
}
VIEWS = {
    "kind": "trend",
    "title": "Views",
    "binding": {"kind": "stat", "filter": {"metric": "views"}, "agg": "series", "field": "value"},
    "config": {"unit": "views"},
}
QUEUE = {
    "kind": "queue",
    "title": "Songs waiting for you",
    "binding": {"kind": "track", "filter": {"verdict": None}},
}

WORDS_WEEK = (
    "### This week on the channel\n\n"
    "A handful of new songs came in from the creators you follow, and **two** of them fit the "
    "late-night sound you like.\n\n"
    "- *Low Tide Radio* by Moss Arcade is the strongest: slow, warm, no vocals.\n"
    "- *Paper Moons* is lovely but runs long for a video.\n\n"
    "If you keep one, its credits line would read like this:\n\n"
    '```\nMusic: "Low Tide Radio" by Moss Arcade, used with permission\n```'
)
WORDS_FUNNEL = (
    "Most of the work waits between an offer and a signed licence, so a reply to the offers already "
    "out is the quickest win. The views keep climbing week on week."
)
WORDS_OFFERS = (
    "These offers are still open:\n\n"
    "1. **Paper Orbit** - asked through their bio link; bio messages are slow.\n\n"
    "A short nudge to Paper Orbit is the one most likely to move."
)
WORDS_ROUND = (
    "I went through every creator you follow. I kept the new songs that fit and left the rest; they "
    "are in the queue on the report, waiting for your verdict."
)


def script(space: str) -> list[dict[str, Any]]:
    moss = channel_url(CREATORS[3][1])
    velvet = channel_url(CREATORS[2][1])
    return [
        {
            "say": "What came in this week?",
            "think": [1400, 1800],
            "rounds": [[("call", "record_list", {"kind": "track"})], [("text", WORDS_WEEK)]],
        },
        {
            "say": "How is the channel doing from first offer to release, and are the views growing?",
            "think": [1600, 2200, 1200],
            "rounds": [
                [("call", "record_list", {"kind": "agreement"})],
                [("call", "show_blocks", {"blocks": [PIPELINE, VIEWS, QUEUE]})],
                [("text", WORDS_FUNNEL)],
            ],
        },
        {
            "say": "Offer Velvet Static a licence for their songs.",
            "think": [1500],
            "rounds": [
                [
                    ("text", "I'll keep the offer to Velvet Static on record. It waits for your signature."),
                    (
                        "call",
                        "record_put",
                        {
                            "kind": "agreement",
                            "body": {
                                "creator_key": velvet,
                                "state": "proposed",
                                "thread_key": "velvet-comment",
                                "plan": "pro",
                            },
                        },
                    ),
                ]
            ],
        },
        {
            "say": "Change the brief: we only license songs from creators on a paid plan.",
            "think": [1300],
            "sign": True,
            "rounds": [
                [
                    ("text", "Here is the brief with that rule in it. It changes only once you sign."),
                    (
                        "call",
                        "propose_brief",
                        {"brief": BRIEF + PAID_ONLY},
                    ),
                ]
            ],
        },
        {
            "say": "Which offers are still waiting on a reply?",
            "think": [1200, 9000],
            "rounds": [
                [
                    ("text", "I'll look at the offers and the conversations they came from."),
                    ("call", "record_list", {"kind": "agreement"}),
                ],
                [("fail", "Meta is rate limiting; try again in a minute")],
            ],
        },
        {
            "say": "Which offers are still waiting on a reply?",
            "think": [1300, 1100, 1700],
            "rounds": [
                [("call", "record_list", {"kind": "agreement"})],
                [("call", "record_list", {"kind": "thread"})],
                [("text", WORDS_OFFERS)],
            ],
        },
        {
            "say": "Go through every creator we follow and keep any new songs you find.",
            "think": [4000, 21500, 33000, 27500, 18000, 6000],
            "rounds": [
                [("call", "record_list", {"kind": "creator"})],
                [("call", "recall", {"query": "songs the owner likes"})],
                [
                    (
                        "call",
                        "record_put",
                        {
                            "kind": "track",
                            "body": {
                                "url": "https://youtube.example/watch?v=sim0101",
                                "title": "Friday Ferries (simulated)",
                                "creator_key": moss,
                                "found_at": "2026-11-03T10:00:00Z",
                            },
                        },
                    ),
                    (
                        "call",
                        "record_put",
                        {
                            "kind": "track",
                            "body": {
                                "url": "https://youtube.example/watch?v=sim0102",
                                "title": "Lamplight Loop (simulated)",
                                "creator_key": moss,
                                "found_at": "2026-11-03T10:00:00Z",
                            },
                        },
                    ),
                ],
                [("call", "remember", {"text": "Moss Arcade posted two new late-night songs this Friday."})],
                [("call", "record_list", {"kind": "track"})],
                [("text", WORDS_ROUND)],
            ],
        },
    ]


PAID_ONLY = " We only license songs from creators on a paid plan; a free-plan song is never used."
CALLOUT = "Two songs wait for your verdict, and the offers sit between asking and agreeing."


def arrange(daemon: Daemon, tick: Clock, space: str) -> None:
    """Her arrangement through the composer's own door: the default parts reordered, the funnel and the
    views added, her title and one sentence; then the person pins the queue and the views."""
    spec = compose.view(daemon, space)["spec"]
    blocks = [*spec["blocks"], {**PIPELINE, "id": "funnel", "span": 12}, {**VIEWS, "id": "views", "span": 6}]
    answer = {
        "v": spec["v"],
        "vocab": spec["vocab"],
        "title": "The channel this week",
        "callout": CALLOUT,
        "blocks": blocks,
    }
    engine = StandIn(tick, [[("text", json.dumps(answer))]], [2000])
    view = compose.compose(daemon, engine, space)  # type: ignore[arg-type]
    queue = next(b["id"] for b in view["spec"]["blocks"] if b["kind"] == "queue")
    compose.set_pins(daemon, space, {"pinned": [queue, "views"]})


def build() -> dict[str, Any]:
    tick = Clock()
    clock.monotonic_ms = tick  # type: ignore[assignment]  # the stand-in's authored pace
    with tempfile.TemporaryDirectory() as tmp:
        daemon = Daemon.open(Path(tmp))
        try:
            daemon.gate.set_executor(lambda card: execute(daemon, card))
            space = seed(daemon)
            arrange(daemon, tick, space)
            for turn in script(space):
                engine = StandIn(tick, turn["rounds"], turn["think"])
                events = list(run_turn(daemon, engine, turn["say"], space))  # type: ignore[arg-type]
                if turn.get("sign"):
                    card = next(e["card"] for e in events if e["type"] == "card")
                    daemon.gate.resolve(card["id"], "approve")
            spaces = daemon.spaces.list()
            return {
                "fixture": FIXTURE,
                "engine": {"engine": "muse", "model": StandIn.model, "key": "absent", "simulated": False},
                "active": space,
                "spaces": spaces,
                "turns": daemon.conversation.list(space),
                "cards": daemon.gate.list(),
                "report": compose.view(daemon, space),
                "elsewhere": mcp_views.host_report(daemon, space),
                "ledger": daemon.ledger.page(50),
            }
        finally:
            daemon.store.close()


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "apps/desktop/src/spread/fixture.json"
    text = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")  # LF on every platform
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
