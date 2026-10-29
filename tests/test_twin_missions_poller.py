"""The poller: off in tests (and whenever ATHENA_TWIN_POLL is 0), started and stopped by the app's
lifespan otherwise; one pass works every open mission of a live twin, and neither a failing mission
nor a failing pass stops it."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.server import create_app
from athena.twins import missions, poller
from missions_kit import ASKED, FIRST, GOAL, THREAD, MissionEngine, MissionWorld, live_twin, mine, theirs, use


@pytest.fixture
def world(daemon: Daemon, client: TestClient) -> MissionWorld:
    return MissionWorld(daemon, client)


@pytest.fixture
def engine(monkeypatch: pytest.MonkeyPatch) -> MissionEngine:
    found = MissionEngine()
    use(monkeypatch, found)
    return found


def test_it_is_off_in_tests_and_reads_its_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    assert poller.interval() is None  # conftest sets ATHENA_TWIN_POLL=0
    monkeypatch.delenv(poller.ENV)
    assert poller.interval() == 300.0
    monkeypatch.setenv(poller.ENV, "45")
    assert poller.interval() == 45.0
    monkeypatch.setenv(poller.ENV, "soon")
    assert poller.interval() == 300.0


def test_the_lifespan_starts_nothing_when_it_is_off(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_: Any) -> None:
        raise AssertionError("the poller started in a test")

    monkeypatch.setattr(poller.Poller, "start", refuse)
    with TestClient(create_app(daemon, token="t")) as client:
        assert client.get("/health").status_code == 200


def test_the_lifespan_starts_and_stops_it(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    monkeypatch.setenv(poller.ENV, "3600")
    real_start, real_stop = poller.Poller.start, poller.Poller.stop

    def start(self: poller.Poller) -> None:
        seen.append("start")
        real_start(self)

    async def stop(self: poller.Poller) -> None:
        seen.append("stop")
        await real_stop(self)

    monkeypatch.setattr(poller.Poller, "start", start)
    monkeypatch.setattr(poller.Poller, "stop", stop)
    with TestClient(create_app(daemon, token="t")) as client:
        assert client.get("/health").status_code == 200
    assert seen == ["start", "stop"]  # and it did not wait out the hour


def test_a_pass_works_open_missions_of_live_twins_and_survives_a_failing_one(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    twin_id = live_twin(world, engine)
    world.threads[THREAD] = [mine("m1", FIRST)]
    r = world.client.post(f"/twins/{twin_id}/missions", json={"thread": THREAD, "goal": GOAL})
    assert r.status_code == 201, r.text
    mission_id = r.json()["id"]
    assert poller.check(daemon, lambda: engine) == 0  # nothing from them yet
    assert engine.calls == []

    world.threads[THREAD].append(theirs("m2", ASKED))
    real = missions.run
    order: list[str] = []

    def flaky(d: Daemon, e: Any, t: str, m: str) -> bool:
        order.append(m)
        if len(order) == 1:
            raise RuntimeError("a failure with no secret in it")
        return real(d, e, t, m)

    found = [("tw_000000000000", "ms_broken00000"), *missions.open_ones(daemon)]
    monkeypatch.setattr(missions, "open_ones", lambda _: found)
    monkeypatch.setattr(missions, "run", flaky)
    assert poller.check(daemon, lambda: engine) == 1
    assert order == ["ms_broken00000", mission_id]
    assert len(world.sent) == 1  # the reply went, once

    # a paused twin's missions are not worked
    monkeypatch.undo()
    use(monkeypatch, engine)
    world.post(twin_id, "twin_pause")
    assert missions.open_ones(daemon) == []


def test_a_mission_whose_conversation_cannot_be_read_keeps_its_state(
    world: MissionWorld, engine: MissionEngine, daemon: Daemon
) -> None:
    twin_id = live_twin(world, engine)
    world.threads[THREAD] = [mine("m1", FIRST)]
    mission_id = world.client.post(
        f"/twins/{twin_id}/missions", json={"thread": THREAD, "goal": GOAL}
    ).json()["id"]
    del world.threads[THREAD]
    assert poller.check(daemon, lambda: engine) == 1
    after = missions.one(daemon, twin_id, mission_id)
    assert after["state"] == "open" and after["note"].startswith("Gmail could not read that conversation")
    assert poller.check(daemon, lambda: engine) == 0  # the same note is not news


def test_the_loop_outlives_a_failing_pass(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    passes: list[int] = []

    def check(*_: Any) -> int:
        passes.append(1)
        if len(passes) == 1:
            raise RuntimeError("boom")
        return 0

    monkeypatch.setattr(poller, "check", check)

    async def go() -> None:
        running = poller.Poller(daemon, lambda: MissionEngine(), 0.01)
        running.start()
        for _ in range(2000):  # up to 20 s on a loaded machine; a few hundredths when idle
            if len(passes) >= 3:
                break
            await asyncio.sleep(0.01)
        await running.stop()

    asyncio.run(go())
    assert len(passes) >= 3
