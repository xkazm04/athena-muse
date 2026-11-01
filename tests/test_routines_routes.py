"""The routine routes (business Phase 2, WP2.1): space_routines lists the defaults, routine changes one,
routine_run runs it now and answers the run, routine_runs lists them newest first; unknown refs are
`unknown_ref`."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.contracts import ROUTES
from athena.routines.context import RunContext
from routines_kit import kind, project


def _path(name: str, ref: str) -> str:
    return ROUTES[name].replace("{id}", ref)


def test_the_four_routes(daemon: Daemon, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fn(ctx: RunContext) -> None:
        ctx.found, ctx.of = 1, 1

    kind(monkeypatch, fn)
    space = project(daemon, ["creator", "track"])
    r = client.get(_path("space_routines", space))
    assert r.status_code == 200, r.text
    (watch,) = r.json()["routines"]
    assert watch["kind"] == "watch" and watch["state"] == "on"

    r = client.patch(
        _path("routine", watch["id"]), json={"cadence_s": 3600, "url": "https://youtube.example"}
    )
    assert r.status_code == 200 and r.json()["cadence_s"] == 3600
    r = client.patch(_path("routine", watch["id"]), json={"cadence_s": 60})
    assert r.status_code == 400 and r.json()["error"] == "bad_request"
    r = client.patch(_path("routine", watch["id"]), json=["not", "an", "object"])
    assert r.status_code == 400

    r = client.post(_path("routine_run", watch["id"]))
    assert r.status_code == 200, r.text
    run = r.json()
    assert (run["outcome"], run["found"], run["of"]) == ("ran", 1, 1)
    client.patch(_path("routine", watch["id"]), json={"state": "paused"})
    paused = client.post(_path("routine_run", watch["id"])).json()
    assert (paused["outcome"], paused["reason"]) == ("skipped", "paused")

    r = client.get(_path("routine_runs", watch["id"]))
    assert r.status_code == 200
    assert [x["id"] for x in r.json()["runs"]] == [paused["id"], run["id"]]


def test_unknown_refs(client: TestClient) -> None:
    missing = "rtn_000000000000"
    for method, path in (
        ("GET", _path("space_routines", "sp_000000000000")),
        ("PATCH", _path("routine", missing)),
        ("POST", _path("routine_run", missing)),
        ("GET", _path("routine_runs", missing)),
    ):
        r = client.request(method, path, json={"state": "on"} if method == "PATCH" else None)
        assert (r.status_code, r.json()["error"]) == (404, "unknown_ref"), (method, path)
