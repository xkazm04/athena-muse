"""Missions on a fake Gmail and Notion with a test engine (ADR 0009): a reply from the other side goes
alone only on Auto, sure and clear; otherwise it waits as a signature card with the right reason; an
edited signature sends the edit and teaches the voice, an unedited one does not; a failing send
returns the card to waiting; a resolved mission files its outcome; a money ask hands it back."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import contracts
from athena.app import Daemon
from athena.contracts import Mission, TwinDetail, TwinDraft
from athena.twins import missions
from athena.twins.voice import compile_voice
from connectors_kit import BANNED, conforms
from missions_kit import (
    ASKED,
    FIRST,
    GOAL,
    REPLY,
    THEM,
    THREAD,
    MissionEngine,
    MissionWorld,
    live_twin,
    mine,
    theirs,
    use,
)

ROUTE = contracts.ROUTES


@pytest.fixture
def world(daemon: Daemon, client: TestClient) -> MissionWorld:
    return MissionWorld(daemon, client)


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> MissionEngine:
    found = MissionEngine()
    use(monkeypatch, found)
    return found


def asked_thread(world: MissionWorld) -> None:
    world.threads[THREAD] = [mine("m1", FIRST), theirs("m2", ASKED)]


def start(world: MissionWorld, twin_id: str, thread: str = THREAD, status: int = 201) -> dict[str, Any]:
    r = world.client.post(ROUTE["twin_missions"].format(id=twin_id), json={"thread": thread, "goal": GOAL})
    assert r.status_code == status, r.text
    return r.json()  # type: ignore[no-any-return]


def get(world: MissionWorld, twin_id: str, mission_id: str) -> Mission:
    r = world.client.get(ROUTE["twin_mission"].format(id=twin_id, mid=mission_id))
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def waiting(world: MissionWorld) -> list[dict[str, Any]]:
    return world.client.get(ROUTE["cards"], params={"state": "waiting"}).json()["cards"]  # type: ignore[no-any-return]


def sign(world: MissionWorld, card_id: str, edited: str | None = None, status: int = 200) -> dict[str, Any]:
    body: dict[str, Any] = {"verdict": "approve"}
    if edited is not None:
        body["edited"] = {"text": edited}
    r = world.client.post(ROUTE["decision"].format(card_id=card_id), json=body)
    assert r.status_code == status, r.text
    return r.json()  # type: ignore[no-any-return]


def test_a_reply_goes_alone_on_auto_sure_and_clear_then_the_yes_files_the_outcome(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = live_twin(world, engine)
    asked_thread(world)
    rows_before = len(daemon.ledger.page(500)["rows"])
    mission = start(world, twin_id)
    conforms(mission, Mission)
    assert mission["thread"] == THREAD and mission["with"] == "Lumen Vale" and mission["state"] == "open"
    assert not any(k.startswith("_") for k in mission)
    first, asked, alone = mission["turns"]
    assert (first["side"], first["text"]) == ("twin", FIRST) and "decision" not in first
    assert (asked["side"], asked["text"]) == ("other", ASKED)
    assert (alone["kind"], alone["confidence"], alone["decision"], alone["bar"], alone["risks"]) == (
        "reply",
        91,
        "sent_alone",
        80,
        [],
    )
    assert "reason" not in alone and "draft" not in alone
    (sent,) = world.sent
    assert sent["thread"] == THREAD and THEM in sent["to"] and sent["text"] == REPLY
    assert sent["in_reply_to"] == "<m2@mail.example>" and sent["subject"] == "Re: Feature on Friday?"
    assert waiting(world) == []
    rows = daemon.ledger.page(500)["rows"][: len(daemon.ledger.page(500)["rows"]) - rows_before]
    assert len(rows) == 2 and {r["surface"] for r in rows} == {"twin"}  # the judgement and the draft
    assert [b["done"] for b in mission["beats"]] == [True, True, False, False]

    # nothing new from them: a second run asks nothing and sends nothing
    assert missions.run(daemon, engine, twin_id, mission["id"]) is False
    assert engine.calls == ["judge", "draft"] and len(world.sent) == 1
    start(world, twin_id, status=400)  # one open mission per conversation

    # their yes: resolved, the thanks goes alone, the outcome is filed to Notion on its own (Auto, 60)
    world.they_write(THREAD, "Yes, go for it! Credit me as Lumen Vale.")
    engine.judge = {"state": "resolved", "note": "They said yes to Friday.", "confidence": 90}
    before = len(world.seen("api.notion.com", "PATCH"))
    assert missions.run(daemon, engine, twin_id, mission["id"]) is True
    done = get(world, twin_id, mission["id"])
    assert done["state"] == "resolved" and len(world.sent) == 2
    assert done["filed"]["chore"] == "file-outcome" and done["filed"]["where"] == "Notion: Partnership offer"
    assert done["filed"]["row"]["with"] == "Lumen Vale"
    assert [b["done"] for b in done["beats"]] == [True, True, True, True]
    (note,) = world.seen("api.notion.com", "PATCH")[before:]
    assert note.path == f"/v1/blocks/{'a' * 32}/children" and "Outcome:" in note.body.decode()  # type: ignore[union-attr]

    twin: TwinDetail = world.get(twin_id)
    conforms(twin, TwinDetail)
    assert twin["week"]["sent"] == 2 and twin["week"]["sent_alone"] == 2 and twin["week"]["held_by_risk"] == 0
    assert twin["open_missions"] == 0 and twin["waiting"] == []


def test_a_draft_below_the_bar_waits_as_a_card_the_person_may_edit(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = live_twin(world, engine)
    asked_thread(world)
    engine.draft = {**engine.draft, "confidence": 70}
    mission = start(world, twin_id)
    held = mission["turns"][-1]
    assert (held["decision"], held["reason"], held["bar"], held["confidence"]) == (
        "waits",
        "below_bar",
        80,
        70,
    )
    assert world.sent == []
    (card,) = waiting(world)
    assert card["action"] == "twin_send" and card["label"] == "Send a reply to Lumen Vale as you"
    assert not BANNED.search(card["label"])
    twin = world.get(twin_id)
    (draft,) = twin["waiting"]
    conforms(draft, TwinDraft)
    assert (
        held["draft"] == draft["id"] and draft["card_id"] == card["id"] and draft["mission"] == mission["id"]
    )
    assert (draft["to"], draft["text"], draft["reason"], draft["answers"]) == (
        THEM,
        REPLY,
        "below_bar",
        ASKED,
    )
    assert twin["waiting_count"] == 1
    page = world.client.get(ROUTE["twins"]).json()
    assert page["stats"]["waiting_for_you"] == 1
    # while it waits, the poller leaves the conversation alone
    world.they_write(THREAD, "Also, which Friday?")
    assert missions.run(daemon, engine, twin_id, mission["id"]) is False


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("risk", "risk"),
        ("touches", "risk"),
        ("first", "first_message"),
        ("paused", "paused"),
    ],
)
def test_every_other_draft_waits_with_its_reason(
    world: MissionWorld, engine: MissionEngine, setup: str, reason: str
) -> None:
    twin_id = live_twin(world, engine)
    asked_thread(world)
    thread = THREAD
    if setup == "risk":
        engine.draft = {**engine.draft, "risks": ["Mentions a date you have not confirmed"]}
    elif setup == "touches":  # the model saw no risk; the code finds one it cannot clear
        engine.draft = {**engine.draft, "text": "Totally fine, it can be exclusive to my channel."}
    elif setup == "first":
        thread = "new.person@example.org"
        engine.draft = {**engine.draft, "subject": "Your track 'Glass Harbor'"}
    else:
        world.post(twin_id, "twin_pause")
    mission = start(world, twin_id, thread)
    held = mission["turns"][-1]
    assert (held["decision"], held["reason"]) == ("waits", reason)
    assert world.sent == []
    (card,) = waiting(world)
    if setup == "touches":
        assert held["risks"] == ["It touches a line it must never cross: never agree to exclusive rights"]
    if setup == "first":
        assert held["kind"] == "first_message" and "bar" not in held and mission["with"] == thread
        assert card["args"]["subject"] == "Your track 'Glass Harbor'" and "thread" not in card["args"]
        # signed, it starts the conversation, and the mission lives on it from then on
        sign(world, card["id"])
        assert world.sent[0]["to"] == thread and world.sent[0]["in_reply_to"] == ""
        assert get(world, twin_id, mission["id"])["thread"] == "thnew0"


def test_an_edited_signature_sends_the_edit_and_teaches_the_voice(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = live_twin(world, engine)
    asked_thread(world)
    engine.draft = {**engine.draft, "confidence": 70}
    mission = start(world, twin_id)
    (card,) = waiting(world)
    examples = len(daemon.twins.rows("examples", twin_id))
    mine_words = "You'd get the visualizer and a credit with a link. Friday suit you?"
    signed = sign(world, card["id"], mine_words)
    assert signed["state"] == "approved" and signed["args"]["text"] == mine_words
    assert signed["args"]["drafted"] == REPLY
    (sent,) = world.sent
    assert (
        sent["text"] == mine_words and sent["thread"] == THREAD and sent["in_reply_to"] == "<m2@mail.example>"
    )
    turn = get(world, twin_id, mission["id"])["turns"][-1]
    assert turn["text"] == mine_words and turn["edited_text"] == mine_words and "draft" not in turn
    assert [e["text"] for e in daemon.twins.rows("examples", twin_id)][examples:] == [mine_words]
    assert mine_words in compile_voice(daemon, twin_id)
    twin = world.get(twin_id)
    assert twin["waiting"] == [] and twin["week"]["sent"] == 1 and twin["week"]["sent_alone"] == 0

    # an unedited signature sends the draft as it was and teaches nothing
    world.they_write(THREAD, "Friday works. Which time?")
    assert missions.run(daemon, engine, twin_id, mission["id"]) is True
    (card,) = waiting(world)
    sign(world, card["id"], REPLY)  # the same words are no edit
    assert world.sent[-1]["text"] == REPLY
    assert len(daemon.twins.rows("examples", twin_id)) == examples + 1


def test_a_failing_send_returns_the_card_to_waiting_and_never_sends_twice(
    world: MissionWorld, engine: MissionEngine
) -> None:
    twin_id = live_twin(world, engine)
    asked_thread(world)
    engine.draft = {**engine.draft, "confidence": 70}
    mission = start(world, twin_id)
    (card,) = waiting(world)

    world.send_status = 400
    refused = sign(world, card["id"], status=400)
    assert refused["error"] == "bad_request" and refused["reason"].startswith("Gmail did not send it")
    again = world.client.get(ROUTE["cards"]).json()["cards"][0]
    assert again["state"] == "waiting" and "resolved" not in again
    assert "draft" in get(world, twin_id, mission["id"])["turns"][-1]

    world.send_status = 503  # it may have gone: the problem says so
    unknown = sign(world, card["id"], status=400)
    assert "may have gone" in unknown["reason"]

    world.send_status = 200
    assert sign(world, card["id"])["state"] == "approved"
    assert len(world.sent) == 1
    sign(world, card["id"], status=400)  # already decided: never twice
    assert len(world.sent) == 1


def test_a_money_ask_hands_the_conversation_back_with_its_draft_waiting(
    world: MissionWorld, engine: MissionEngine
) -> None:
    twin_id = live_twin(world, engine)
    world.threads[THREAD] = [mine("m1", FIRST), theirs("m2", "Hey, I'd want $200 for it, is that OK?")]
    engine.draft = {
        "text": "Thanks for saying so. Let me check and come back to you.",
        "confidence": 88,
        "risks": [],
    }
    mission = start(world, twin_id)
    assert engine.calls == ["draft"]  # the code decided: no judgement asked
    held = mission["turns"][-1]
    assert held["risks"][0] == "They asked for money, and it must never promise money or a fee"
    assert (held["decision"], held["reason"]) == ("waits", "risk")
    assert mission["state"] == "handed_back" and "handed this back to you" in mission["note"]
    assert len(waiting(world)) == 1 and world.sent == []
    stats = world.client.get(ROUTE["twins"]).json()["stats"]
    assert stats["waiting_for_you"] == 2 and stats["missions_open"] == 1


def test_a_judgement_that_needs_the_person_drafts_nothing(world: MissionWorld, engine: MissionEngine) -> None:
    twin_id = live_twin(world, engine)
    asked_thread(world)
    engine.judge = {
        "state": "handed_back",
        "note": "They asked about your rates for a series.",
        "confidence": 80,
    }
    mission = start(world, twin_id)
    assert engine.calls == ["judge"] and mission["state"] == "handed_back"
    assert mission["note"] == "They asked about your rates for a series."
    assert waiting(world) == [] and world.sent == []


def test_declining_a_draft_hands_the_conversation_back(world: MissionWorld, engine: MissionEngine) -> None:
    twin_id = live_twin(world, engine)
    asked_thread(world)
    engine.draft = {**engine.draft, "confidence": 70}
    mission = start(world, twin_id)
    (card,) = waiting(world)
    r = world.client.post(ROUTE["decision"].format(card_id=card["id"]), json={"verdict": "decline"})
    assert r.status_code == 200 and r.json()["state"] == "declined"
    after = get(world, twin_id, mission["id"])
    assert after["state"] == "handed_back" and "yours now" in after["note"]
    assert [t["side"] for t in after["turns"]] == ["twin", "other"] and world.sent == []


def test_an_outcome_below_the_notion_bar_waits_as_a_note_card(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = live_twin(world, engine)
    world.post(twin_id, "twin_autonomy", {"channel": "notion", "autonomy": "auto", "bar": 95})
    asked_thread(world)
    engine.judge = {"state": "resolved", "note": "They said yes.", "confidence": 90}
    before = len(world.seen("api.notion.com", "PATCH"))
    mission = start(world, twin_id)
    assert mission["state"] == "resolved" and "filed" not in mission
    (card,) = waiting(world)
    assert card["action"] == "twin_note" and card["label"] == "File the outcome to Notion: Partnership offer"
    (draft,) = world.get(twin_id)["waiting"]
    assert (draft["channel"], draft["reason"], draft["bar"], draft["confidence"]) == (
        "notion",
        "below_bar",
        95,
        90,
    )
    sign(world, card["id"], "Outcome: Lumen Vale said yes to Friday.")
    assert get(world, twin_id, mission["id"])["filed"]["where"] == "Notion: Partnership offer"
    (note,) = world.seen("api.notion.com", "PATCH")[before:]
    assert "Lumen Vale said yes to Friday." in note.body.decode()  # type: ignore[union-attr]
    assert daemon.twins.rows("examples", twin_id) == []  # a note is not the person's voice


def test_a_mission_needs_a_live_twin_a_goal_and_a_conversation(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    unready = world.create()
    refused = start(world, unready, status=400)
    assert "once it is live" in refused["reason"]
    twin_id = live_twin(world, engine)
    for body in ({"thread": THREAD}, {"goal": GOAL}, {"thread": "a@b.example, c@d.example", "goal": GOAL}):
        r = world.client.post(ROUTE["twin_missions"].format(id=twin_id), json=body)
        assert r.status_code == 400, body
    assert start(world, twin_id, "th_missing0", status=400)["reason"].startswith("Gmail could not read")
    assert (
        world.client.get(ROUTE["twin_mission"].format(id=twin_id, mid="ms_000000000000")).status_code == 404
    )
    practice = world.get(twin_id)["rehearsal"]["id"]
    assert world.client.get(ROUTE["twin_mission"].format(id=twin_id, mid=practice)).status_code == 404
    r = world.client.post(
        ROUTE["twin_missions"].format(id=twin_id), json={}, headers={"Authorization": "Bearer nope"}
    )
    assert r.status_code == 401
    assert world.client.post(ROUTE["twin_missions"].format(id="tw_000000000000"), json={}).status_code == 404


def test_answering_a_conversation_they_started_is_a_reply_not_first_contact(
    world: MissionWorld, engine: MissionEngine
) -> None:
    # Gmail first messages wait (Assist); replies may go alone (Auto at 80). A thread the other side
    # opened is answered as a reply, even though the twin has not written in it yet.
    twin_id = live_twin(world, engine)
    world.threads[THREAD] = [theirs("m1", ASKED)]
    mission = start(world, twin_id)
    turn = mission["turns"][-1]
    assert turn["kind"] == "reply" and turn["decision"] == "sent_alone"
    assert world.sent[0]["in_reply_to"] != ""
