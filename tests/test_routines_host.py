"""The routine host (business Phase 2, WP2.1): one admission decision with named refusals recorded as
skipped runs, single flight, catch-up without back-fill, a ceiling that ends a run visibly as partial,
a skip not re-recorded every tick, and the lifespan that starts it unless ATHENA_TWIN_POLL is 0."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.contracts import RUNS_KEPT, RecordKind
from athena.engine import EngineError
from athena.engine.scripted import ScriptedEngine
from athena.routines import host as host_mod
from athena.routines.context import Partial, RunContext, Skip
from athena.routines.store import new_run
from athena.server import create_app
from athena.turn import run_turn
from routines_kit import PricedEngine, host, kind, project, watch_of

WATCH: list[RecordKind] = ["creator", "track"]  # the kinds of the watch routine alone


def _ran(calls: list[str]) -> Any:
    def fn(ctx: RunContext) -> None:
        calls.append(ctx.routine["id"])
        ctx.found, ctx.of = 2, 3
        ctx.note = "Read two of three creators."

    return fn


def _age(daemon: Daemon, routine_id: str, seconds: int) -> None:
    """Moves every run of the routine `seconds` into the past (as if the daemon had been closed)."""
    then = (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat(timespec="seconds")
    then = then.replace("+00:00", "Z")
    for r in daemon.store.query("SELECT id, body FROM routine_runs WHERE routine_id = ?", (routine_id,)):
        body = json.loads(r["body"])
        body["started"] = then
        daemon.store.run(
            "UPDATE routine_runs SET started = ?, body = ? WHERE id = ?", (then, json.dumps(body), r["id"])
        )


# --- admission ------------------------------------------------------------------------------------


def test_a_run_records_what_it_covered_with_its_denominator(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    kind(monkeypatch, _ran(calls))
    space = project(daemon, WATCH)
    routine_id = watch_of(daemon, space)
    run = host(daemon).run_now(routine_id)
    assert run["outcome"] == "ran" and (run["found"], run["of"]) == (2, 3)
    assert run["note"] == "Read two of three creators." and "ended" in run
    assert daemon.routines.runs(routine_id)[0]["id"] == run["id"]
    assert daemon.routines.get(routine_id)["last_run"]["id"] == run["id"]


def test_a_paused_routine_never_runs(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    kind(monkeypatch, _ran(calls))
    routine_id = watch_of(daemon, project(daemon, WATCH))
    daemon.routines.change(routine_id, {"state": "paused"})
    run = host(daemon).run_now(routine_id)
    assert (run["outcome"], run.get("reason")) == ("skipped", "paused")
    assert host(daemon).tick() == []  # a tick never picks it
    assert calls == []
    assert "next_at" not in daemon.routines.get(routine_id)


def test_a_live_chat_turn_holds_it_until_the_turn_ends(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    kind(monkeypatch, _ran(calls))
    space = project(daemon, WATCH)
    routine_id = watch_of(daemon, space)
    ticking = host(daemon)
    turn = run_turn(daemon, ScriptedEngine(), "hello", space)
    next(turn)  # the turn is open: turn.py holds busy.chat beside busy.turn
    assert daemon.busy.live(space)
    wrote = ticking.tick()
    assert [(r["outcome"], r.get("reason")) for r in wrote] == [("skipped", "live_turn")]
    assert ticking.tick() == []  # still live: the same skip is not written again
    assert calls == []
    list(turn)  # the turn ends
    assert not daemon.busy.live(space)
    wrote = ticking.tick()  # it was never dropped: the next tick runs it
    assert [r["outcome"] for r in wrote] == ["ran"] and calls == [routine_id]
    outcomes = [r["outcome"] for r in daemon.routines.runs(routine_id)]
    assert outcomes == ["ran", "skipped"]


def test_a_mission_or_a_draft_step_does_not_hold_it(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    kind(monkeypatch, _ran(calls))
    space = project(daemon, WATCH)
    routine_id = watch_of(daemon, space)
    with daemon.busy.turn(space):  # what missions.run and a draft step hold
        assert not daemon.busy.live(space)
        assert host(daemon).run_now(routine_id)["outcome"] == "ran"
    with daemon.busy.chat(space):  # what a chat turn holds
        assert host(daemon).run_now(routine_id)["reason"] == "live_turn"
    assert calls == [routine_id]


def test_single_flight_two_at_once_one_runs_one_records_running(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered, release = threading.Event(), threading.Event()

    def slow(ctx: RunContext) -> None:
        entered.set()
        assert release.wait(5)

    kind(monkeypatch, slow)
    routine_id = watch_of(daemon, project(daemon, WATCH))
    first: list[Any] = []
    worker = threading.Thread(target=lambda: first.append(host(daemon).run_now(routine_id)))
    worker.start()
    assert entered.wait(5)
    second = host(daemon).run_now(routine_id)  # another Host: the claim is the daemon's
    release.set()
    worker.join(5)
    assert (second["outcome"], second.get("reason")) == ("skipped", "running")
    assert first[0]["outcome"] == "ran"
    assert not daemon.routines.running(routine_id)  # the claim was released
    assert sorted(r["outcome"] for r in daemon.routines.runs(routine_id)) == ["ran", "skipped"]


def test_the_claim_is_released_when_the_kind_raises(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(ctx: RunContext) -> None:
        raise RuntimeError("secret-value-xyz")

    kind(monkeypatch, boom)
    routine_id = watch_of(daemon, project(daemon, WATCH))
    run = host(daemon).run_now(routine_id)
    assert run["outcome"] == "failed"
    assert run["note"] == "It stopped on an unexpected error (RuntimeError)."  # never the value
    assert not daemon.routines.running(routine_id)
    assert host(daemon).run_now(routine_id)["outcome"] == "failed"  # not "running"


@pytest.mark.parametrize(
    ("raised", "outcome", "reason", "note"),
    [
        (Skip("no_browser", "Her browser is not open."), "skipped", "no_browser", "Her browser is not open."),
        (Partial("Read one page of two."), "partial", None, "Read one page of two."),
        (EngineError("the engine said no"), "failed", None, "the engine said no"),
    ],
)
def test_what_a_kind_raises_is_the_runs_outcome(
    daemon: Daemon,
    monkeypatch: pytest.MonkeyPatch,
    raised: Exception,
    outcome: str,
    reason: str | None,
    note: str,
) -> None:
    def fn(ctx: RunContext) -> None:
        raise raised

    kind(monkeypatch, fn)
    run = host(daemon).run_now(watch_of(daemon, project(daemon, WATCH)))
    assert (run["outcome"], run.get("reason"), run.get("note")) == (outcome, reason, note)


def test_no_engine_is_a_named_skip(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    def fn(ctx: RunContext) -> None:
        ctx.extract("system", "user", "items")

    def none() -> Any:
        raise EngineError("no key for the engine")

    kind(monkeypatch, fn)
    routine_id = watch_of(daemon, project(daemon, WATCH))
    run = host_mod.Host(daemon, none).run_now(routine_id)
    assert (run["outcome"], run["reason"], run["note"]) == ("skipped", "no_engine", "no key for the engine")


# --- the cadence: catch-up, no back-fill, a skip written once --------------------------------------


def test_catch_up_runs_each_overdue_routine_once_and_never_back_fills(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    kind(monkeypatch, _ran(calls))
    kind(monkeypatch, _ran(calls), "inbox")
    space = project(daemon, [*WATCH, "thread"])
    watch = watch_of(daemon, space)
    inbox = next(r["id"] for r in daemon.routines.of_space(space) if r["kind"] == "inbox")
    ticking = host(daemon)
    ticking.tick()  # never ran: both due at once
    assert sorted(calls) == sorted([watch, inbox])
    calls.clear()
    assert ticking.tick() == [] and calls == []  # nothing due
    # the daemon was closed for three days: the watch (6 h) missed twelve intervals, the inbox (30 min)
    # a hundred and forty-four; each runs once
    _age(daemon, watch, 3 * 24 * 3600)
    _age(daemon, inbox, 3 * 24 * 3600)
    ticking.tick()
    assert sorted(calls) == sorted([watch, inbox])
    ticking.tick()
    ticking.tick()
    assert len(calls) == 2
    assert [r["outcome"] for r in daemon.routines.runs(watch)] == ["ran", "ran"]
    nxt = datetime.fromisoformat(daemon.routines.get(watch)["next_at"].replace("Z", "+00:00"))
    assert timedelta(hours=5, minutes=59) < nxt - datetime.now(UTC) <= timedelta(hours=6)


def test_a_skip_reason_is_not_recorded_every_tick(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    reasons = ["no_browser"] * 3 + ["signed_out"] * 2

    def fn(ctx: RunContext) -> None:
        raise Skip(reasons.pop(0))  # type: ignore[arg-type]

    kind(monkeypatch, fn)
    routine_id = watch_of(daemon, project(daemon, WATCH))
    ticking = host(daemon)
    for _ in range(5):
        ticking.tick()  # a skip is no completion: it stays due and is tried every tick
    assert reasons == []
    assert [r.get("reason") for r in daemon.routines.runs(routine_id)] == ["signed_out", "no_browser"]
    # a cadence after the last written skip, the same reason is written again
    reasons.append("signed_out")
    _age(daemon, routine_id, 7 * 3600)
    ticking.tick()
    assert daemon.routines.runs(routine_id)[0].get("reason") == "signed_out"
    assert len(daemon.routines.runs(routine_id)) == 3


def test_the_persons_run_now_always_records(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    def fn(ctx: RunContext) -> None:
        raise Skip("no_browser")

    kind(monkeypatch, fn)
    routine_id = watch_of(daemon, project(daemon, WATCH))
    host(daemon).run_now(routine_id)
    run = host(daemon).run_now(routine_id)
    assert (run["outcome"], run.get("reason")) == ("skipped", "no_browser")
    assert len(daemon.routines.runs(routine_id)) == 2


def test_runs_kept_are_the_newest(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    routine_id = watch_of(daemon, project(daemon, WATCH))
    for _ in range(RUNS_KEPT + 5):
        run = new_run(routine_id)
        run["ended"] = run["started"]
        assert daemon.routines.write_run(run)
    runs = daemon.routines.runs(routine_id)
    assert len(runs) == RUNS_KEPT and runs[0]["id"] == run["id"]
    stored = daemon.store.query("SELECT COUNT(*) AS n FROM routine_runs WHERE routine_id = ?", (routine_id,))
    assert stored[0]["n"] == RUNS_KEPT


# --- the ceiling ------------------------------------------------------------------------------------


def test_a_run_stops_at_its_ceiling_as_partial(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = PricedEngine(cost=0.04)

    def greedy(ctx: RunContext) -> None:
        for _ in range(100):
            ctx.extract("Read it.", "page text", "items")
            ctx.found += 1

    kind(monkeypatch, greedy)
    space = project(daemon, WATCH)
    routine_id = watch_of(daemon, space)
    run = host(daemon, engine).run_now(routine_id)
    ceiling = daemon.routines.get(routine_id)["ceiling_usd"]
    assert ceiling == 0.25  # the default exists without configuration
    assert run["outcome"] == "partial" and "ceiling of $0.25" in run["note"]
    assert run["spent_usd"] <= ceiling + 0.04  # at most one call past it
    assert engine.calls == run["found"] == 7  # 0.24 spent leaves room for one more, then it stops
    rows = [r for r in daemon.ledger.page(50, space)["rows"] if r["surface"] == "routine"]
    assert len(rows) == engine.calls  # every call is a ledger row on surface routine


def test_an_unpriced_engine_stops_after_ten_calls(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = PricedEngine(cost=None)

    def greedy(ctx: RunContext) -> None:
        while True:
            ctx.extract("Read it.", "page text", "items")

    kind(monkeypatch, greedy)
    run = host(daemon, engine).run_now(watch_of(daemon, project(daemon, WATCH)))
    assert run["outcome"] == "partial" and engine.calls == 10
    assert "spent_usd" not in run  # no figure is not $0


# --- events and the lifespan ----------------------------------------------------------------------


def test_a_written_run_is_published(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    kind(monkeypatch, _ran([]))
    space = project(daemon, WATCH)
    routine_id = watch_of(daemon, space)
    seen: list[Any] = []
    monkeypatch.setattr(daemon.events, "publish", seen.append)
    host(daemon).run_now(routine_id)
    assert [(e["type"], e["space_id"], e["routine"]["id"]) for e in seen] == [("routine", space, routine_id)]
    assert seen[0]["routine"]["last_run"]["outcome"] == "ran"


def test_the_lifespan_starts_nothing_when_polling_is_off(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: Any) -> None:
        raise AssertionError("the host started in a test")

    monkeypatch.setattr(host_mod.Host, "start", refuse)
    with TestClient(create_app(daemon, token="t")) as client:
        assert client.get("/health").status_code == 200


def test_the_lifespan_starts_the_host_ticks_and_stops_it(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    ticked = threading.Event()
    monkeypatch.setenv("ATHENA_TWIN_POLL", "3600")
    real_start, real_stop = host_mod.Host.start, host_mod.Host.stop

    def start(self: host_mod.Host) -> None:
        seen.append("start")
        real_start(self)

    async def stop(self: host_mod.Host) -> None:
        seen.append("stop")
        await real_stop(self)

    def tick(self: host_mod.Host) -> list[Any]:
        ticked.set()  # the first tick is at once: the catch-up
        return []

    monkeypatch.setattr(host_mod.Host, "start", start)
    monkeypatch.setattr(host_mod.Host, "stop", stop)
    monkeypatch.setattr(host_mod.Host, "tick", tick)
    with TestClient(create_app(daemon, token="t")) as client:
        assert client.get("/health").status_code == 200
        assert ticked.wait(5)
    assert seen == ["start", "stop"]  # and it did not wait out the tick


def test_the_loop_outlives_a_failing_tick(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    ticks: list[int] = []

    def tick(self: host_mod.Host) -> list[Any]:
        ticks.append(1)
        if len(ticks) == 1:
            raise RuntimeError("boom")
        return []

    monkeypatch.setattr(host_mod.Host, "tick", tick)

    async def go() -> None:
        running = host(daemon, tick_s=0.01)
        running.start()
        for _ in range(2000):
            if len(ticks) >= 3:
                break
            await asyncio.sleep(0.01)
        await running.stop()

    asyncio.run(go())
    assert len(ticks) >= 3
