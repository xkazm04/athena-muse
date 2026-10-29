"""The dress rehearsal on the scripted engine: Athena plays the other side on a Notion practice page,
every twin draft is ruled by the send rule and shown, never sent; a held reply carries the risk the
code found; the person's edit becomes a voice example and an unedited "that's me" never does; a money
ask hands the conversation back; then it goes live with writes on, and pausing is its own state."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import contracts
from athena.app import Daemon
from athena.contracts import MissionTurn, TwinDetail
from athena.twins.rehearse import code_risks, merged
from athena.twins.voice import compile_voice
from connectors_kit import BANNED, conforms
from twins_kit import PAGES, World

GOAL = "Get Lumen Vale's yes to feature 'Glass Harbor'"


@pytest.fixture
def world(daemon: Daemon, client: TestClient) -> World:
    return World(daemon, client)


def ready_twin(world: World) -> str:
    twin_id = world.create()
    world.play(twin_id)
    assert world.get(twin_id)["ready"]
    return twin_id


def turns(events: list[dict[str, Any]]) -> list[MissionTurn]:
    return [e["turn"] for e in events if e["type"] == "turn"]


def test_the_staged_rehearsal_holds_one_reply_and_sends_one_alone(world: World, daemon: Daemon) -> None:
    twin_id = ready_twin(world)
    before = len(world.provider.seen)
    events = world.stream(twin_id, "twin_rehearse", {"goal": GOAL})
    played = turns(events)
    for t in played:
        conforms(t, contracts.MissionTurn)
    assert [t["side"] for t in played] == ["twin", "other", "twin", "other", "twin"]
    first, _, held, _, alone = played
    assert (first["kind"], first["confidence"], first["decision"], first["reason"]) == (
        "first_message",
        84,
        "waits",
        "first_message",
    )
    assert "bar" not in first and first["risks"] == []  # first messages are on Assist: no bar applies
    assert (held["kind"], held["confidence"], held["decision"], held["reason"], held["bar"]) == (
        "reply",
        77,
        "waits",
        "risk",
        80,
    )
    # the model said no risk; the code found one it cannot clear
    assert held["risks"] == ["It touches a line it must never cross: never agree to exclusive rights"]
    assert (alone["confidence"], alone["decision"], alone["bar"], alone["risks"]) == (
        91,
        "sent_alone",
        80,
        [],
    )
    assert "reason" not in alone
    assert events[-1] == {"type": "outcome", "state": "resolved"}

    twin = world.get(twin_id)
    rehearsal = twin["rehearsal"]
    conforms(rehearsal, contracts.Mission)
    assert (
        rehearsal["practice"] is True
        and rehearsal["with"] == "Lumen Vale"
        and rehearsal["channel"] == "notion"
    )
    assert rehearsal["state"] == "resolved" and rehearsal["turns"] == played
    assert "Played on your Notion practice page 'Practice: Lumen Vale'." in rehearsal["note"]
    assert twin["missions"] == [rehearsal] and twin["open_missions"] == 0

    # written to the practice page under the first picked page, one line a turn and the outcome
    notion = [s for s in world.seen("api.notion.com") if world.provider.seen.index(s) >= before]
    (created,) = [s for s in notion if s.method == "POST" and s.path == "/v1/pages"]
    assert created.json["parent"]["page_id"] == PAGES[0][0]
    assert created.json["properties"]["title"]["title"][0]["text"]["content"] == "Practice: Lumen Vale"
    appended = [s for s in notion if s.method == "PATCH"]
    assert len(appended) == len(played) + 1
    assert "it would send this on its own" in appended[4].body.decode()  # type: ignore[union-attr]
    record = daemon.connectors.vault.record("notion")
    assert record.writes_enabled and set(record.allowlist) == {PAGES[0][0], "e" * 32}
    assert daemon.connectors.connection("notion")["writes"] is True
    notion_channel = next(c for c in twin["channels"] if c["kind"] == "notion")
    assert notion_channel["health"] == "active" and "last_at" in notion_channel
    # never sent to a person: no mail left, no card was filed
    assert not [s for s in world.seen("gmail.googleapis.com", "POST")]
    assert world.client.get(contracts.ROUTES["cards"]).json()["cards"] == []
    rows = daemon.ledger.page(500)["rows"]
    assert {r["surface"] for r in rows} == {"twin"}


def test_marks_teach_only_with_the_persons_own_words(world: World, daemon: Daemon) -> None:
    twin_id = ready_twin(world)
    played = turns(world.stream(twin_id, "twin_rehearse", {"goal": GOAL}))
    first, other, held, _, _ = played
    mine = "You'd get a free visualizer and a credit. It isn't exclusive: it stays yours to share anywhere."

    twin = world.post(twin_id, "twin_mark", {"turn": first["id"], "mark": "me"})
    assert twin["rehearsal"]["turns"][0]["mark"] == "me"
    assert daemon.twins.rows("examples", twin_id) == []  # an unedited "that's me" is never an example

    twin = world.post(twin_id, "twin_mark", {"turn": held["id"], "mark": "edited", "edited_text": mine})
    conforms(twin, TwinDetail)
    marked = twin["rehearsal"]["turns"][2]
    assert (marked["mark"], marked["edited_text"]) == ("edited", mine)
    assert [e["text"] for e in daemon.twins.rows("examples", twin_id)] == [mine]
    assert mine in compile_voice(daemon, twin_id)  # every later draft writes like it

    # marked "that's me" after all: the example goes with the edit
    twin = world.post(twin_id, "twin_mark", {"turn": held["id"], "mark": "me"})
    assert "edited_text" not in twin["rehearsal"]["turns"][2]
    assert daemon.twins.rows("examples", twin_id) == []

    world.post(twin_id, "twin_mark", {"turn": other["id"], "mark": "me"}, status=400)
    world.post(
        twin_id, "twin_mark", {"turn": held["id"], "mark": "edited", "edited_text": held["text"]}, status=400
    )
    world.post(twin_id, "twin_mark", {"turn": held["id"], "mark": "edited"}, status=400)
    world.post(twin_id, "twin_mark", {"turn": "t99", "mark": "me"}, status=404)
    world.post(twin_id, "twin_mark", {"turn": first["id"], "mark": "maybe"}, status=400)


def test_a_money_ask_hands_the_conversation_back(world: World) -> None:
    twin_id = ready_twin(world)
    events = world.stream(
        twin_id, "twin_rehearse", {"goal": "Get Mira Soleil's yes to feature 'Salt Lines' for no fee"}
    )
    played = turns(events)
    assert [t["side"] for t in played] == ["twin", "other", "twin"]
    asked, answer = played[1], played[2]
    assert "$200" in asked["text"]
    assert answer["risks"][0] == "They asked for money, and it must never promise money or a fee"
    assert (answer["decision"], answer["reason"]) == ("waits", "risk")
    assert events[-1] == {"type": "outcome", "state": "handed_back"}
    twin = world.get(twin_id)
    assert twin["rehearsal"]["state"] == "handed_back" and twin["open_missions"] == 1
    assert "handed this back to you" in twin["rehearsal"]["note"]
    page = world.client.get(contracts.ROUTES["twins"]).json()
    assert page["stats"]["waiting_for_you"] == 1 and page["stats"]["missions_open"] == 1
    # a new rehearsal replaces it
    world.stream(twin_id, "twin_rehearse", {"goal": GOAL})
    twin = world.get(twin_id)
    assert len(twin["missions"]) == 1 and twin["rehearsal"]["state"] == "resolved"


def test_without_a_practice_page_it_is_kept_here_and_says_so(daemon: Daemon, client: TestClient) -> None:
    world = World(daemon, client, notion_create=500)
    twin_id = ready_twin(world)
    events = world.stream(twin_id, "twin_rehearse", {"goal": GOAL})
    assert events[-1]["type"] == "outcome"
    note = world.get(twin_id)["rehearsal"]["note"]
    assert "Kept on this computer: Notion would not make the practice page." in note
    assert not [s for s in world.seen("api.notion.com", "PATCH")]


def test_it_rehearses_only_when_ready_and_goes_live_only_after(world: World, daemon: Daemon) -> None:
    twin_id = world.create()
    world.play(twin_id, frames=8)
    refused = world.post(twin_id, "twin_rehearse", {"goal": GOAL}, status=400)
    assert "not ready to rehearse yet" in refused["reason"] and "what it may send alone" in refused["reason"]
    world.post(twin_id, "twin_golive", status=400)
    world.post(twin_id, "twin_pause", status=400)  # nothing to pause while it is set up

    twin_id = ready_twin(world)
    refused = world.post(twin_id, "twin_golive", status=400)
    assert "rehearse it once" in refused["reason"]
    world.stream(twin_id, "twin_rehearse", {"goal": GOAL})
    daemon.connectors.set_writes("gmail", False)
    live = world.post(twin_id, "twin_golive")
    assert live["state"] == "live" and "since" in live and "ask" not in live
    assert daemon.connectors.connection("gmail")["writes"] is True
    assert daemon.connectors.connection("notion")["writes"] is True

    paused = world.post(twin_id, "twin_pause")
    assert (paused["state"], paused["paused_because"]) == ("paused", "You paused it.")
    assert daemon.connectors.connection("gmail")["writes"] is True  # pausing is the twin's own state
    again = world.post(twin_id, "twin_golive")
    assert again["state"] == "live" and again["since"] == live["since"] and "paused_because" not in again


def test_the_codes_risks_lead_and_cannot_be_cleared() -> None:
    nevers = [
        "Never promise money or a fee",
        "Never agree to exclusive rights",
        "Never write after 9 pm their time",
    ]
    found, stuck = code_risks(nevers, "Could you pay me $200?", "Sure, exclusive it is.")
    assert stuck and found == [
        "They asked for money, and it must never promise money or a fee",
        "It touches a line it must never cross: never agree to exclusive rights",
    ]
    assert code_risks(nevers, "Sounds good!", "Great, thank you.") == ([], False)
    assert code_risks(["Never agree to exclusive rights"], "$200 please", "ok") == (
        [],
        False,
    )  # no money line
    assert merged(found, ["They asked for money, and it must never promise money or a fee", "A date", 3]) == [
        *found,
        "A date",
    ]
    assert len(merged([], [f"risk {i}" for i in range(9)])) == contracts.RISKS_MAX


def test_what_the_rehearsal_shows_is_in_plain_words(world: World) -> None:
    twin_id = ready_twin(world)
    world.stream(twin_id, "twin_rehearse", {"goal": GOAL})
    rehearsal = world.get(twin_id)["rehearsal"]
    for line in [rehearsal["note"], *[r for t in rehearsal["turns"] for r in t.get("risks", [])]]:
        assert not BANNED.search(line), line
