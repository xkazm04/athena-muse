"""A mission plays offline on the scripted engine (`ATHENA_ENGINE=scripted`): it judges where the
conversation stands and drafts each message, every line labelled simulated. An answer to their question
is below the usual bar, so on Auto it waits for the person; their yes resolves it, the thanks goes on
its own and the outcome is filed; a new conversation's first message waits on Assist."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from athena import contracts
from athena.app import Daemon
from athena.engine.scripted import ScriptedEngine
from athena.twins import missions
from missions_kit import ASKED, FIRST, THREAD, MissionWorld, live_twin, mine, theirs

ROUTE = contracts.ROUTES


@pytest.fixture
def world(daemon: Daemon, client: TestClient) -> MissionWorld:
    return MissionWorld(daemon, client)


@pytest.fixture(autouse=True)
def scripted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATHENA_ENGINE", "scripted")


def start(world: MissionWorld, twin_id: str, thread: str) -> dict[str, object]:
    r = world.client.post(
        ROUTE["twin_missions"].format(id=twin_id),
        json={"thread": thread, "goal": "Get Lumen Vale's yes to feature 'Glass Harbor'"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def test_a_mission_plays_offline_from_their_question_to_a_filed_yes(
    world: MissionWorld, daemon: Daemon
) -> None:
    twin_id = live_twin(world)
    world.threads[THREAD] = [mine("m1", FIRST), theirs("m2", ASKED)]
    mission = start(world, twin_id, THREAD)
    held = mission["turns"][-1]  # type: ignore[index]
    assert (held["decision"], held["reason"], held["confidence"], held["bar"]) == (
        "waits",
        "below_bar",
        74,
        80,
    )
    assert held["text"].startswith("(Simulated)")
    assert str(mission["note"]).startswith("(Simulated)") and mission["state"] == "open"
    assert world.sent == []
    (card,) = world.client.get(ROUTE["cards"], params={"state": "waiting"}).json()["cards"]

    r = world.client.post(ROUTE["decision"].format(card_id=card["id"]), json={"verdict": "approve"})
    assert r.status_code == 200, r.text
    assert len(world.sent) == 1

    world.they_write(THREAD, "Yes, go for it! Credit me as Lumen Vale.")
    assert missions.run(daemon, ScriptedEngine(), twin_id, str(mission["id"])) is True
    done = world.client.get(ROUTE["twin_mission"].format(id=twin_id, mid=mission["id"])).json()
    assert done["state"] == "resolved" and done["note"].startswith("(Simulated) They said yes.")
    thanks = done["turns"][-1]
    assert (thanks["decision"], thanks["confidence"]) == ("sent_alone", 92) and len(world.sent) == 2
    assert done["filed"]["chore"] == "file-outcome"


def test_a_new_conversations_first_message_waits_with_its_subject(world: MissionWorld) -> None:
    twin_id = live_twin(world)
    mission = start(world, twin_id, "new.person@example.org")
    first = mission["turns"][-1]  # type: ignore[index]
    assert (first["kind"], first["decision"], first["reason"]) == ("first_message", "waits", "first_message")
    assert first["text"].startswith("(Simulated) Hi new.person")
    (card,) = world.client.get(ROUTE["cards"], params={"state": "waiting"}).json()["cards"]
    assert card["args"]["subject"] == "Get Lumen Vale's yes to feature 'Glass Harbor'"
