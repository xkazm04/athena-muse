"""The routines' tables (business Phase 2, WP2.1): the defaults a project's kinds call for, idempotent;
a default no longer called for removed when it never ran, else paused; the change door's validation;
and erase takes routines and their runs with the space."""

from __future__ import annotations

import pytest

from athena.app import Daemon
from athena.contracts import CADENCE_MIN_S, RecordKind
from athena.errors import ApiError
from athena.routines import kinds
from athena.routines.store import new_run
from routines_kit import project


def _kinds(daemon: Daemon, space: str) -> dict[str, str]:
    return {r["kind"]: r["id"] for r in daemon.routines.ensure_defaults(space)}


def test_the_defaults_follow_the_kinds_a_project_keeps(daemon: Daemon) -> None:
    every = project(daemon)
    made = daemon.routines.ensure_defaults(every)
    assert sorted(r["kind"] for r in made) == ["inbox", "outreach", "stats", "watch"]
    for r in made:
        assert r["name"] == kinds.NAME[r["kind"]] and r["cadence_s"] == kinds.CADENCE_S[r["kind"]]
        assert r["ceiling_usd"] == 0.25 and r["state"] == "on" and r["id"].startswith("rtn_")
        assert "next_at" in r and "last_run" not in r
    assert [r["id"] for r in daemon.routines.ensure_defaults(every)] == [r["id"] for r in made]  # idempotent
    some = project(daemon, ["creator", "track", "stat"])
    assert sorted(_kinds(daemon, some)) == ["stats", "watch"]
    assert daemon.routines.ensure_defaults(project(daemon, [])) == []


def test_a_default_no_longer_called_for_goes_when_it_never_ran_else_pauses(daemon: Daemon) -> None:
    space = project(daemon, ["creator", "track", "thread", "stat"])
    made = _kinds(daemon, space)
    run = new_run(made["watch"])
    daemon.routines.write_run(run)
    daemon.records.set_kinds(space, {"kinds": ["thread"]})
    after = {r["kind"]: r for r in daemon.routines.ensure_defaults(space)}
    assert sorted(after) == ["inbox", "watch"]  # stats never ran: removed
    assert after["watch"]["state"] == "paused" and after["watch"]["last_run"]["id"] == run["id"]
    assert after["inbox"]["state"] == "on"


def test_a_change_is_validated(daemon: Daemon) -> None:
    routine_id = _kinds(daemon, project(daemon, ["stat"]))["stats"]
    changed = daemon.routines.change(
        routine_id, {"state": "paused", "cadence_s": CADENCE_MIN_S, "url": "https://studio.example/analytics"}
    )
    assert (changed["state"], changed["cadence_s"], changed["url"]) == (
        "paused",
        CADENCE_MIN_S,
        "https://studio.example/analytics",
    )
    for bad in (
        {"cadence_s": CADENCE_MIN_S - 1},
        {"cadence_s": "900"},
        {"cadence_s": True},
        {"state": "off"},
        {"url": "ftp://studio.example"},
        {"url": "studio.example"},
        {"ceiling_usd": 5},
    ):
        with pytest.raises(ApiError) as e:
            daemon.routines.change(routine_id, bad)  # type: ignore[arg-type]
        assert e.value.error == "bad_request"
    with pytest.raises(ApiError) as e:
        daemon.routines.change("rtn_000000000000", {"state": "on"})
    assert e.value.error == "unknown_ref"


def test_erase_removes_routines_and_runs(daemon: Daemon) -> None:
    kept: list[RecordKind] = ["creator", "track"]
    space, other = project(daemon, kept), project(daemon, kept)
    routine_id = _kinds(daemon, space)["watch"]
    daemon.routines.write_run(new_run(routine_id))
    survivor = _kinds(daemon, other)["watch"]
    daemon.spaces.erase(space)
    for table in ("routines", "routine_runs"):
        rows = daemon.store.query(f"SELECT COUNT(*) AS n FROM {table} WHERE space_id = ?", (space,))
        assert rows[0]["n"] == 0
    with pytest.raises(ApiError):
        daemon.routines.get(routine_id)
    assert daemon.routines.get(survivor)["space_id"] == other
    assert not daemon.routines.write_run(new_run(routine_id))  # a run that ends after the erase is dropped
