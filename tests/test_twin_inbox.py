"""The task inbox: a live twin with the preset picked reads its chosen Notion page on each poll and starts
one mission per new "<who or thread>: <goal>" line; the same line twice is one mission; a line it
cannot place is left alone and reported on the twin in plain words; and the only thing it writes on
the page is one "Taken:" note per line, ruled by the send rule on the Notion channel."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import contracts
from athena.app import Daemon
from athena.contracts import TaskInbox, TwinDetail
from athena.twins import inbox, poller
from connectors_kit import BANNED, conforms
from missions_kit import ASKED, FIRST, THREAD, MissionEngine, MissionWorld, line, live_twin, mine, theirs, use
from twins_kit import INBOX_PAGE, PAGES

ROUTE = contracts.ROUTES


@pytest.fixture
def world(daemon: Daemon, client: TestClient) -> MissionWorld:
    return MissionWorld(daemon, client)


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> MissionEngine:
    found = MissionEngine()
    use(monkeypatch, found)
    return found


def with_inbox(world: MissionWorld, engine: MissionEngine, notion: str = "auto") -> str:
    """A live twin whose task inbox reads the 'Twin inbox' page, with Lumen Vale's question waiting."""
    twin_id = live_twin(world, engine)
    world.threads[THREAD] = [mine("m1", FIRST), theirs("m2", ASKED)]
    world.pages[INBOX_PAGE] = [line("b0", "Write one mission per line, who first.", "paragraph")]
    world.post(twin_id, "twin_pages", {"ids": [PAGES[0][0], PAGES[1][0], PAGES[2][0], INBOX_PAGE]})
    picked = ["file-outcome", "task-inbox", "practice-page"]
    twin: TwinDetail = world.post(twin_id, "twin_chores", {"ids": picked, "inbox": INBOX_PAGE})  # type: ignore[assignment]
    (preset,) = [c for c in twin["chores"] if c["id"] == "task-inbox"]
    assert preset["page"] == INBOX_PAGE and twin["inbox"]["title"] == "Twin inbox"
    world.post(twin_id, "twin_autonomy", {"channel": "notion", "autonomy": notion, "bar": 60})
    return twin_id


def report(world: MissionWorld, twin_id: str) -> TaskInbox:
    found = world.get(twin_id)["inbox"]
    conforms(found, TaskInbox)
    return found  # type: ignore[no-any-return]


def missions_of(world: MissionWorld, twin_id: str) -> list[dict[str, Any]]:
    return [m for m in world.get(twin_id)["missions"] if not m.get("practice")]


def test_new_lines_become_missions_once_and_the_rest_is_reported(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = with_inbox(world, engine)
    world.pages[INBOX_PAGE] += [
        line("b1", "Lumen Vale: Get Lumen's yes to a second feature in December"),
        line("b2", "kai@moss.example: Ask Kai for a short call next week", "to_do"),
        line("b3", "Morgan: Ask about the invoice"),
        line("b4", "A thought without a colon"),
    ]
    notes_before = len(world.notes)
    writes_before = [s for s in world.seen("api.notion.com") if s.method != "GET"]
    assert poller.check(daemon, lambda: engine) >= 2

    found = missions_of(world, twin_id)
    assert [(m["with"], m["source"]) for m in found] == [
        ("Lumen Vale", "notion"),
        ("kai@moss.example", "notion"),
    ]
    assert found[0]["thread"] == THREAD  # the name placed it on their conversation: answering it is a reply
    assert found[0]["goal"] == "Get Lumen's yes to a second feature in December"
    got = report(world, twin_id)
    assert got["taken"] == 2 and got["title"] == "Twin inbox" and "checked_at" in got
    (unplaced,) = got["unplaced"]
    assert "Morgan" in unplaced and "no recent conversation" in unplaced and not BANNED.search(unplaced)

    # the only writes on Notion: one "Taken:" note per line it took, on the inbox page
    new_notes = world.notes[notes_before:]
    assert [page for page, _ in new_notes] == [INBOX_PAGE, INBOX_PAGE]
    assert all(text.startswith("Taken: ") for _, text in new_notes)
    assert "Lumen Vale: Get Lumen's yes" in new_notes[0][1] and "kai@moss.example" in new_notes[1][1]
    writes = [s for s in world.seen("api.notion.com") if s.method != "GET"][len(writes_before) :]
    assert len(writes) == 2 and all(s.method == "PATCH" and INBOX_PAGE in s.url for s in writes)

    # read again: the same lines, its own notes and the same words in a new block start nothing
    world.pages[INBOX_PAGE].append(line("b5", "Lumen Vale: Get Lumen's yes to a second feature in December"))
    poller.check(daemon, lambda: engine)
    assert len(missions_of(world, twin_id)) == 2
    assert report(world, twin_id)["taken"] == 2
    assert len(world.notes) == notes_before + 2

    # a line placed later leaves the report: Morgan writes, then is named by their address
    world.pages[INBOX_PAGE].append(line("b6", "morgan@ledger.example: Ask about the invoice"))
    poller.check(daemon, lambda: engine)
    assert len(missions_of(world, twin_id)) == 3
    assert report(world, twin_id)["unplaced"] == [unplaced]  # "Morgan:" still names no one


def test_an_unplaceable_line_is_left_alone_and_nothing_is_written(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = with_inbox(world, engine)
    world.threads["thkai"] = [mine("k1", "Hi, Lumen Vale here too?")]  # a second conversation named Lumen
    world.pages[INBOX_PAGE] += [
        line("b1", "Lumen: Ask again"),
        line("b2", "two@a.example, three@b.example: Ask both"),
        line("b3", f"{THREAD}: Get a yes"),
    ]
    before = len(world.notes)
    poller.check(daemon, lambda: engine)
    got = report(world, twin_id)
    assert got["taken"] == 1  # the thread by its id
    assert [m["thread"] for m in missions_of(world, twin_id)] == [THREAD]
    assert len(got["unplaced"]) == 2
    assert "names 2 of your conversations" in got["unplaced"][0]
    assert "one address" in got["unplaced"][1]
    assert len(world.notes) == before + 1
    # a line on a conversation that already has an open mission is reported, not taken twice
    world.pages[INBOX_PAGE].append(line("b4", "lumen@vale.example: Get a yes, again"))
    poller.check(daemon, lambda: engine)
    assert len(missions_of(world, twin_id)) == 1
    assert any("already has an open mission" in u for u in report(world, twin_id)["unplaced"])


def test_the_taken_note_waits_for_a_signature_on_review(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = with_inbox(world, engine, notion="review")
    world.pages[INBOX_PAGE].append(line("b1", "kai@moss.example: Ask Kai for a short call"))
    before = len(world.notes)
    poller.check(daemon, lambda: engine)
    assert len(world.notes) == before  # nothing written alone
    (note,) = [d for d in world.get(twin_id)["waiting"] if d["channel"] == "notion"]
    assert note["subject"].startswith("Taken: kai@moss.example") and note["reason"] == "review"
    (mission,) = missions_of(world, twin_id)
    r = world.client.post(ROUTE["decision"].format(card_id=note["card_id"]), json={"verdict": "approve"})
    assert r.status_code == 200, r.text
    assert world.notes[before:] == [(INBOX_PAGE, world.notes[before][1])]
    assert world.notes[before][1].startswith("Taken: kai@moss.example")
    after = next(m for m in missions_of(world, twin_id) if m["id"] == mission["id"])
    assert after["state"] == mission["state"] and "filed" not in after


def test_it_reads_only_live_twins_and_says_when_the_page_is_gone(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = with_inbox(world, engine)
    world.pages[INBOX_PAGE].append(line("b1", "kai@moss.example: Ask Kai for a short call"))
    world.post(twin_id, "twin_pause")
    assert inbox.check(daemon) == 0 and missions_of(world, twin_id) == []
    world.post(twin_id, "twin_golive")
    del world.pages[INBOX_PAGE]
    assert inbox.check(daemon) == 0
    problem = report(world, twin_id).get("problem", "")
    assert "could not read 'Twin inbox'" in problem and not BANNED.search(problem)
    # the inbox reads a page it may read, never a database or a page it was not given
    refused = world.post(twin_id, "twin_chores", {"ids": ["task-inbox"], "inbox": PAGES[2][0]}, status=400)
    assert "page it may read" in refused["reason"]
    world.post(twin_id, "twin_chores", {"ids": ["file-outcome"], "inbox": INBOX_PAGE}, status=400)
