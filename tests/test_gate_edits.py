"""The gate with edits (ADR 0009): a twin's draft may be signed with the person's words, checked for its
action and stored on the card beside the draft's own; any other card takes no edit. The executor runs
off the event loop, and one that fails returns the card to waiting with its problem as the answer."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.contracts import TEXT_MAX, Card
from athena.errors import ApiError


def twin_card(daemon: Daemon, action: str = "twin_send") -> Card:
    return daemon.gate.file("", action, {"text": "the draft", "to": "a@b.example"}, "Send a reply as you")  # type: ignore[arg-type]


def decide(client: TestClient, card_id: str, body: dict[str, Any]) -> Any:
    return client.post(f"/decisions/{card_id}", json=body)


def test_an_edit_is_stored_beside_the_draft_and_the_same_words_are_no_edit(daemon: Daemon) -> None:
    ran: list[Card] = []
    daemon.gate.set_executor(lambda c: ran.append(c) or "sent")
    card = twin_card(daemon)
    signed = daemon.gate.resolve(card["id"], "approve", "  my own words  ")
    assert signed["args"] == {"text": "my own words", "drafted": "the draft", "to": "a@b.example"}
    assert ran[0]["args"]["text"] == "my own words" and daemon.gate.get(card["id"])["state"] == "approved"

    same = twin_card(daemon)
    assert "drafted" not in daemon.gate.resolve(same["id"], "approve", "the draft ")["args"]
    note = twin_card(daemon, "twin_note")
    assert daemon.gate.resolve(note["id"], "approve", "a note")["args"]["text"] == "a note"
    declined = twin_card(daemon)
    assert daemon.gate.resolve(declined["id"], "decline", "ignored")["args"]["text"] == "the draft"


def test_an_edit_is_checked_and_a_refused_one_changes_nothing(daemon: Daemon) -> None:
    other = daemon.gate.file("", "propose_brief", {"brief": "b"}, "Change the brief")
    with pytest.raises(ApiError) as info:
        daemon.gate.resolve(other["id"], "approve", "another brief")
    assert "only a twin's draft" in info.value.reason
    card = twin_card(daemon)
    for bad in ("   ", "x" * (TEXT_MAX + 1)):
        with pytest.raises(ApiError):
            daemon.gate.resolve(card["id"], "approve", bad)
    with pytest.raises(ApiError):
        daemon.gate.resolve(twin_card(daemon, "twin_note")["id"], "approve", "x" * 4001)
    assert daemon.gate.get(other["id"])["state"] == "waiting"
    assert daemon.gate.get(card["id"]) == card


def test_a_failed_executor_returns_the_card_to_waiting_with_its_problem(daemon: Daemon) -> None:
    calls: list[str] = []

    def executor(c: Card) -> str:
        calls.append(c["id"])
        if len(calls) == 1:
            raise ApiError("bad_request", "Gmail did not send it: it said no")
        if len(calls) == 2:
            raise RuntimeError("a bug, never shown")
        return "sent"

    daemon.gate.set_executor(executor)
    card = twin_card(daemon)
    with pytest.raises(ApiError) as info:
        daemon.gate.resolve(card["id"], "approve", "edited once")
    assert info.value.reason == "Gmail did not send it: it said no"
    back = daemon.gate.get(card["id"])
    assert back["state"] == "waiting" and "resolved" not in back
    assert back["args"]["text"] == "edited once"  # the person's words are kept for the next try
    with pytest.raises(ApiError) as info:
        daemon.gate.resolve(card["id"], "approve")
    assert info.value.reason == "It could not be done, so nothing changed. Try again."
    assert daemon.gate.resolve(card["id"], "approve")["state"] == "approved"
    assert daemon.gate.get(card["id"])["args"]["drafted"] == "the draft"
    with pytest.raises(ApiError):
        daemon.gate.resolve(card["id"], "approve")
    assert len(calls) == 3


def test_the_route_takes_the_edit_and_runs_the_executor_off_the_loop(
    daemon: Daemon, client: TestClient
) -> None:
    where: list[bool] = []

    def executor(c: Card) -> str:
        try:
            asyncio.get_running_loop()
            where.append(True)
        except RuntimeError:
            where.append(False)
        return "sent"

    daemon.gate.set_executor(executor)
    card = twin_card(daemon)
    r = decide(client, card["id"], {"verdict": "approve", "edited": {"text": "mine"}})
    assert r.status_code == 200 and r.json()["args"]["text"] == "mine"
    assert where == [False]
    for body in ({"verdict": "approve", "edited": "mine"}, {"verdict": "approve", "edited": {"words": "x"}}):
        assert decide(client, twin_card(daemon)["id"], body).status_code == 400
    other = daemon.gate.file("", "forget", {"id": "mem_1"}, "Forget it")
    r = decide(client, other["id"], {"verdict": "approve", "edited": {"text": "x"}})
    assert r.status_code == 400 and daemon.gate.get(other["id"])["state"] == "waiting"
    assert decide(client, other["id"], {"verdict": "decline"}).json()["state"] == "declined"
