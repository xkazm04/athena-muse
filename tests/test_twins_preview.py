"""How a twin sounds now (the voice section's nested preview): one engine call on surface `twin`, kept
until the compiled voice changes, so opening the voice page twice costs once; what changed since is
counted by the code; the scripted engine answers it, labelled simulated, and a twin with no voice yet
is refused in plain words. It is kept in the store, so it survives a restart and is erased with the
Project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import contracts
from athena.app import Daemon
from athena.contracts import TwinDetail, TwinPreview
from athena.server import create_app
from athena.twins import preview
from connectors_kit import BANNED, conforms
from twins_kit import World

ROUTE = contracts.ROUTES["twin_preview"]
AUTH = {"Authorization": "Bearer t"}


@pytest.fixture
def world(daemon: Daemon, client: TestClient) -> World:
    return World(daemon, client)


def calls(daemon: Daemon) -> int:
    return sum(r["surface"] == "twin" for r in daemon.ledger.page(500)["rows"])


def sounds(world: World, twin_id: str, status: int = 200) -> dict[str, Any]:
    r = world.client.get(ROUTE.format(id=twin_id))
    assert r.status_code == status, r.text
    return r.json()  # type: ignore[no-any-return]


def test_no_voice_yet_is_refused_in_plain_words(world: World) -> None:
    twin_id = world.create()
    world.play(twin_id, frames=4)  # the voice is learned, still her pencil
    refused = sounds(world, twin_id, status=400)
    assert "no voice yet" in refused["reason"] and not BANNED.search(refused["reason"])
    assert sounds(world, "tw_0123456789ab", status=404)["error"] == "unknown_ref"


def test_one_call_kept_until_the_voice_changes(world: World, daemon: Daemon) -> None:
    twin_id = world.create()
    world.play(twin_id, frames=5)  # the voice inked, a dial set in the person's words
    before = calls(daemon)
    first = sounds(world, twin_id)
    conforms(first, TwinPreview)
    assert first["text"].startswith("(Simulated)") and first["inbound"].startswith("(Simulated)")
    assert first["changed"] == []  # the first one compares nothing
    assert calls(daemon) == before + 1
    assert sounds(world, twin_id) == first and calls(daemon) == before + 1  # opened twice, paid once
    twin: TwinDetail = world.get(twin_id)
    conforms(twin, TwinDetail)
    assert twin["preview"] == first  # the voice section reads the kept one, with no call

    world.post(twin_id, "twin_dials", {"dials": {"formality": 1, "length": 4}})
    assert "preview" not in world.get(twin_id)  # kept for a voice that is no more
    second = sounds(world, twin_id)
    assert calls(daemon) == before + 2
    assert second["changed"] == ["Formality from 3 to 1 of 5", "Length from 2 to 4 of 5"]
    assert second["text"] != first["text"]  # the scripted reply moves with its dials


def test_it_answers_the_latest_message_it_answered(world: World) -> None:
    twin_id = world.create()
    world.play(twin_id)
    world.stream(twin_id, "twin_rehearse", {"goal": "Get Lumen Vale's yes to feature 'Glass Harbor'"})
    got = sounds(world, twin_id)
    assert got["inbound"] == preview.their_last(world.daemon, twin_id)
    assert "Go for it" in got["inbound"]  # the rehearsal's last word from the other side


def test_what_changed_is_counted_by_the_code() -> None:
    before = {"voice": ["Warm"], "dials": {"Formality": 2}, "examples": 0}
    after = {"voice": ["Warm", "Short"], "dials": {"Formality": 3}, "examples": 2}
    assert preview.changes(before, after) == [
        "Now: Short",
        "Formality from 2 to 3 of 5",
        "2 more messages you rewrote in your own words",
    ]
    assert preview.changes(after, {**after, "voice": ["Short"]}) == ["No longer: Warm"]
    assert preview.changes(after, after) == [
        "What it knows, remembers or must never do changed; its voice did not"
    ]


def test_a_kept_preview_survives_a_restart_and_is_erased_with_the_project(tmp_path: Path) -> None:
    first_daemon = Daemon.open(tmp_path)
    world = World(first_daemon, TestClient(create_app(first_daemon, token="t"), headers=AUTH))
    twin_id = world.create()
    world.play(twin_id, frames=5)
    first = sounds(world, twin_id)
    first_daemon.store.close()

    again = Daemon.open(tmp_path)  # the daemon restarted over the same data folder
    world = World(again, TestClient(create_app(again, token="t"), headers=AUTH))
    before = calls(again)
    assert world.get(twin_id)["preview"] == first
    assert sounds(world, twin_id) == first and calls(again) == before  # nothing written again
    world.post(twin_id, "twin_dials", {"dials": {"formality": 1}})
    assert sounds(world, twin_id)["changed"] == ["Formality from 3 to 1 of 5"]  # against the kept one
    assert len(again.twins.rows("previews", twin_id)) == 1  # one kept per twin

    space = world.get(twin_id)["space_id"]
    assert world.client.delete(contracts.ROUTES["space"].format(id=space)).status_code == 200
    assert again.store.query("SELECT COUNT(*) FROM twin_previews")[0][0] == 0
    again.store.close()
