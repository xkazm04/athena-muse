"""Giving a twin a mission from the page (the document's new entry): its recent Gmail conversations,
newest first and capped, each with an excerpt of the last message that is never longer than the cap;
Athena's suggested goals, one engine call on surface `twin` that reads the conversation fenced and that
the scripted engine answers; and the mission the slip starts, marked as given on the page."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import contracts
from athena import engine as engine_mod
from athena.app import Daemon
from athena.contracts import GoalList, Mission, ThreadList
from athena.engine import TextDelta, ToolCall, Usage
from athena.engine.scripted import ScriptedEngine
from connectors_kit import BANNED, conforms
from missions_kit import ASKED, FIRST, GOAL, THEM, THREAD, MissionWorld, live_twin, message, mine, theirs

ROUTE = contracts.ROUTES
LONG = (
    "Sounds great! What would I get out of it &amp; would it be exclusive to your channel? "
    + "I ask because last time a channel wanted the track for itself and I said no. " * 4
)


@pytest.fixture
def world(daemon: Daemon, client: TestClient) -> MissionWorld:
    return MissionWorld(daemon, client)


class Spy(ScriptedEngine):
    """The scripted engine, keeping what each call was given."""

    def __init__(self, answer: str | None = None) -> None:
        self.seen: list[list[dict[str, Any]]] = []
        self.answer = answer

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        self.seen.append(messages)
        if self.answer is not None:
            yield TextDelta(self.answer)
            yield Usage(input_tokens=5, output_tokens=5)
            return
        yield from super().complete(messages, tools)


def threads(world: MissionWorld, twin_id: str, status: int = 200) -> dict[str, Any]:
    r = world.client.get(ROUTE["twin_threads"].format(id=twin_id))
    assert r.status_code == status, r.text
    return r.json()  # type: ignore[no-any-return]


def goals(world: MissionWorld, twin_id: str, body: Any, status: int = 200) -> dict[str, Any]:
    r = world.client.post(ROUTE["twin_goals"].format(id=twin_id), json=body)
    assert r.status_code == status, r.text
    return r.json()  # type: ignore[no-any-return]


def three(world: MissionWorld) -> None:
    """Three conversations, listed by the fake in an order that is not Gmail's: the oldest first."""
    world.threads["thold"] = [
        message("o1", "Juno Park <juno@park.example>", "Alex <me@example.test>", "Thanks!", subject="credits")
    ]
    world.threads["thold"][0]["payload"]["headers"][3]["value"] = "Tue, 20 Oct 2026 09:00:00 +0000"
    world.threads[THREAD] = [
        mine("m1", FIRST, date="Thu, 29 Oct 2026 10:00:00 +0000"),
        theirs("m2", LONG, date="Thu, 29 Oct 2026 11:00:00 +0000"),
    ]
    world.threads["thmine"] = [
        message(
            "k1",
            "Alex <me@example.test>",
            "Kai Moss <kai@moss.example>",
            "Hi Kai, are you free next week?",
            subject="A call?",
            date="Thu, 29 Oct 2026 12:00:00 +0000",
        )
    ]


def test_recent_conversations_newest_first_with_a_capped_excerpt(world: MissionWorld) -> None:
    twin_id = live_twin(world)
    three(world)
    found: ThreadList = threads(world, twin_id)  # type: ignore[assignment]
    conforms(found, ThreadList)
    for t in found["threads"]:
        conforms(t, contracts.ThreadSummary)
    assert [t["id"] for t in found["threads"]] == ["thmine", THREAD, "thold"]
    kai, lumen, juno = found["threads"]
    assert (kai["with"], kai["theirs_last"], kai["subject"]) == ("Kai Moss", False, "A call?")
    assert (lumen["with"], lumen["theirs_last"]) == ("Lumen Vale", True)
    assert lumen["last_at"] == "2026-10-29T11:00:00Z"
    assert juno["with"] == "Juno Park" and juno["theirs_last"] is True
    # the excerpt is their words, unescaped, cut on a word and never longer than the cap
    assert len(lumen["snippet"]) <= contracts.SNIPPET_MAX < len(LONG)
    assert lumen["snippet"].startswith("Sounds great! What would I get out of it & would")
    assert lumen["snippet"].endswith("…")
    # at most THREADS_MAX, as Gmail is asked for
    for i in range(contracts.THREADS_MAX + 5):
        world.threads[f"th{i:03d}"] = [theirs(f"x{i}", "Hello")]
    assert len(threads(world, twin_id)["threads"]) == contracts.THREADS_MAX
    asked = [s.url for s in world.seen("gmail.googleapis.com") if s.url.split("?")[0].endswith("/threads")]
    assert asked and all(f"maxResults={contracts.THREADS_MAX}" in u for u in asked)


def test_no_gmail_is_said_in_plain_words(world: MissionWorld) -> None:
    twin_id = live_twin(world)
    world.daemon.connectors.disconnect("gmail")
    refused = threads(world, twin_id, status=400)["reason"]
    assert "Gmail" in refused and not BANNED.search(refused)
    assert threads(world, "tw_0123456789ab", status=404)["error"] == "unknown_ref"


def test_suggested_goals_on_scripted_one_call_reading_the_conversation_fenced(
    world: MissionWorld, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    twin_id = live_twin(world)
    world.threads[THREAD] = [mine("m1", FIRST), theirs("m2", ASKED)]
    spy = Spy()
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: spy)
    before = sum(r["surface"] == "twin" for r in daemon.ledger.page(500)["rows"])
    found: GoalList = goals(world, twin_id, {"thread": THREAD})  # type: ignore[assignment]
    conforms(found, GoalList)
    assert found["goals"] == [
        "Get Lumen's yes to 'Feature on Friday?'",
        "Answer Lumen's questions and agree on next steps",
        "Thank Lumen and close the conversation kindly",
    ]
    assert sum(r["surface"] == "twin" for r in daemon.ledger.page(500)["rows"]) == before + 1
    (call,) = spy.seen
    user = str(call[-1]["content"])
    assert "<<<gmail:" in user and ASKED in user  # their words, inside the fence
    assert ASKED not in str(call[0]["content"])
    # someone new: no conversation to read
    new = goals(world, twin_id, {"to": "Kai Moss <kai@moss.example>"})["goals"]
    assert len(new) == 3 and new[0] == "Introduce yourself to kai and ask for a short call"
    assert all(len(g) <= contracts.LABEL_MAX for g in new)


def test_goals_are_optional_and_asked_for_one_conversation(
    world: MissionWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    twin_id = live_twin(world)
    world.threads[THREAD] = [mine("m1", FIRST), theirs("m2", ASKED)]
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: Spy("I would rather not."))
    assert goals(world, twin_id, {"thread": THREAD}) == {"goals": []}
    many = '{"goals": ["Get a yes", "Get a yes", "", 7, "Book a call", "Ask for a date", "One more"]}'
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: Spy(many))
    assert goals(world, twin_id, {"to": THEM})["goals"] == ["Get a yes", "Book a call", "Ask for a date"]
    for body in ({}, {"thread": THREAD, "to": THEM}, {"to": "two@a.example, three@b.example"}, {"thread": 7}):
        assert not BANNED.search(goals(world, twin_id, body, status=400)["reason"])


def test_the_slips_start_is_a_mission_given_on_the_page(world: MissionWorld) -> None:
    twin_id = live_twin(world)
    world.threads[THREAD] = [mine("m1", FIRST), theirs("m2", ASKED)]
    r = world.client.post(ROUTE["twin_missions"].format(id=twin_id), json={"thread": THREAD, "goal": GOAL})
    assert r.status_code == 201, r.text
    mission: Mission = r.json()
    conforms(mission, Mission)
    assert (mission["source"], mission["thread"], mission["with"]) == ("page", THREAD, "Lumen Vale")
    page = world.client.get(ROUTE["twins"]).json()
    (shown,) = [m for t in page["twins"] for m in t["missions"] if m["id"] == mission["id"]]
    assert shown["source"] == "page"
    # someone new: the first message is the one the send rule's first-message level holds
    body = {"thread": "kai@moss.example", "goal": "Ask Kai for a call"}
    new = world.client.post(ROUTE["twin_missions"].format(id=twin_id), json=body).json()
    assert new["source"] == "page" and new["with"] == "kai@moss.example"
    assert new["turns"][-1]["kind"] == "first_message" and new["turns"][-1]["reason"] == "first_message"
