"""The folded Twins poller (business Phase 2, WP2.1): each live twin has a `twin:<twin_id>` routine that
works its open missions exactly as the poller's pass did, and its task inbox; a failing mission never
stops the others; a paused twin's routine skips `no_twin`; a mission now waits for a live chat turn in
its project; and ATHENA_TWIN_POLL still sets the cadence (0 keeps the host off, as in every test).

Moved from tests/test_twin_missions_poller.py (the `Poller` class is gone; `poller.check` stays for the
tests that drive a twin by hand)."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.routines.host import Host
from athena.twins import missions, poller
from missions_kit import (
    ASKED,
    FIRST,
    GOAL,
    THREAD,
    MissionEngine,
    MissionWorld,
    line,
    live_twin,
    mine,
    theirs,
    use,
)
from twins_kit import INBOX_PAGE, PAGES


@pytest.fixture
def world(daemon: Daemon, client: TestClient) -> MissionWorld:
    return MissionWorld(daemon, client)


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> MissionEngine:
    found = MissionEngine()
    use(monkeypatch, found)
    return found


def _routine(daemon: Daemon, twin_id: str) -> str:
    space = str(daemon.twins.row(twin_id)["space_id"])
    found = [r for r in daemon.routines.ensure_defaults(space) if r["kind"] == "twin"]
    assert [r["id"] for r in found] == [f"twin:{twin_id}"]
    return found[0]["id"]


def _mission(world: MissionWorld, twin_id: str) -> str:
    r = world.client.post(f"/twins/{twin_id}/missions", json={"thread": THREAD, "goal": GOAL})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def test_the_interval_and_the_twin_cadence_read_athena_twin_poll(
    daemon: Daemon, world: MissionWorld, engine: MissionEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert poller.interval() is None  # conftest sets ATHENA_TWIN_POLL=0: the host does not tick
    monkeypatch.delenv(poller.ENV)
    assert poller.interval() == 300.0
    monkeypatch.setenv(poller.ENV, "soon")
    assert poller.interval() == 300.0
    twin_id = live_twin(world, engine)
    routine_id = _routine(daemon, twin_id)
    twin = daemon.routines.get(routine_id)
    assert (twin["kind"], twin["cadence_s"], twin["ceiling_usd"]) == ("twin", 300, 0.25)
    monkeypatch.setenv(poller.ENV, "45")
    assert poller.interval() == 45.0
    _routine(daemon, twin_id)
    assert daemon.routines.get(routine_id)["cadence_s"] == 45


def test_the_routine_works_open_missions_and_survives_a_failing_one(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    twin_id = live_twin(world, engine)
    world.threads[THREAD] = [mine("m1", FIRST)]
    mission_id = _mission(world, twin_id)
    routine_id = _routine(daemon, twin_id)
    host = Host(daemon, lambda: engine)
    run = host.run_now(routine_id)  # nothing from them yet
    assert (run["outcome"], run["found"], run["of"]) == ("ran", 1, 1)
    assert engine.calls == []

    world.threads[THREAD].append(theirs("m2", ASKED))
    real = missions.run
    order: list[str] = []

    def flaky(d: Daemon, e: Any, t: str, m: str) -> bool:
        order.append(m)
        if len(order) == 1:
            raise RuntimeError("a failure with no secret in it")
        return real(d, e, t, m)

    found = [(twin_id, "ms_broken00000"), *missions.open_ones(daemon)]
    monkeypatch.setattr(missions, "open_ones", lambda _: found)
    monkeypatch.setattr(missions, "run", flaky)
    run = host.run_now(routine_id)
    assert run["outcome"] == "ran" and run["of"] == 2 and "1 moved on" in run["note"]
    assert order == ["ms_broken00000", mission_id]
    assert len(world.sent) == 1  # the reply went, once
    assert "secret" not in str(daemon.routines.runs(routine_id))

    # a paused twin's routine works nothing
    monkeypatch.undo()
    use(monkeypatch, engine)
    world.post(twin_id, "twin_pause")
    assert missions.open_ones(daemon) == []
    run = host.run_now(routine_id)
    assert (run["outcome"], run["reason"]) == ("skipped", "no_twin")


def test_a_mission_whose_conversation_cannot_be_read_keeps_its_state(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = live_twin(world, engine)
    world.threads[THREAD] = [mine("m1", FIRST)]
    mission_id = _mission(world, twin_id)
    del world.threads[THREAD]
    routine_id = _routine(daemon, twin_id)
    host = Host(daemon, lambda: engine)
    assert "1 moved on" in host.run_now(routine_id)["note"]
    after = missions.one(daemon, twin_id, mission_id)
    assert after["state"] == "open" and after["note"].startswith("Gmail could not read that conversation")
    assert "0 moved on" in host.run_now(routine_id)["note"]  # the same note is not news


def test_a_mission_waits_for_a_live_chat_turn_in_its_project(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = live_twin(world, engine)
    world.threads[THREAD] = [mine("m1", FIRST)]
    _mission(world, twin_id)
    world.threads[THREAD].append(theirs("m2", ASKED))
    routine_id = _routine(daemon, twin_id)
    space = str(daemon.twins.row(twin_id)["space_id"])
    host = Host(daemon, lambda: engine)
    with daemon.busy.chat(space):
        wrote = host.tick()
        assert [(r["routine_id"], r["outcome"], r.get("reason")) for r in wrote] == [
            (routine_id, "skipped", "live_turn")
        ]
        assert world.sent == [] and engine.calls == []
    wrote = host.tick()  # the turn ended: the next tick works it
    assert [r["outcome"] for r in wrote] == ["ran"]
    assert len(world.sent) == 1


def test_the_routine_reads_the_twins_task_inbox(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = live_twin(world, engine)
    world.threads[THREAD] = [mine("m1", FIRST), theirs("m2", ASKED)]
    world.pages[INBOX_PAGE] = [line("b0", "Write one mission per line, who first.", "paragraph")]
    world.post(twin_id, "twin_pages", {"ids": [PAGES[0][0], PAGES[1][0], PAGES[2][0], INBOX_PAGE]})
    world.post(
        twin_id, "twin_chores", {"ids": ["file-outcome", "task-inbox", "practice-page"], "inbox": INBOX_PAGE}
    )
    world.pages[INBOX_PAGE].append(line("b1", "Lumen Vale: Get Lumen's yes to a second feature in December"))
    run = Host(daemon, lambda: engine).run_now(_routine(daemon, twin_id))
    assert run["outcome"] == "ran" and run["note"].startswith("It took 1 new task from its inbox.")
    found = [m for m in world.get(twin_id)["missions"] if not m.get("practice")]
    assert [(m["with"], m["source"]) for m in found] == [("Lumen Vale", "notion")]
