"""The report's routes and the per-project ledger (business Phase 1)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.engine import EngineError
from athena.server import create_app
from report_kit import Fake, block, project, spec, track, use_sql_records

H = {"Authorization": "Bearer t"}
QUEUE = block("q", "queue", "Tracks waiting", 8, binding={"kind": "track", "filter": {"verdict": None}})


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    d = use_sql_records(Daemon.open(None))
    yield d
    d.store.close()


@pytest.fixture
def client(daemon: Daemon) -> TestClient:
    return TestClient(create_app(daemon, token="t"), headers=H)


def _engine(monkeypatch: pytest.MonkeyPatch, engine: object) -> None:
    def build(*_: object, **__: object) -> object:
        if isinstance(engine, EngineError):
            raise engine
        return engine

    monkeypatch.setattr("athena.engine.build_engine", build)


def test_get_the_report(client: TestClient, daemon: Daemon) -> None:
    sid = project(daemon)
    track(daemon, sid, 1)
    view = client.get(f"/spaces/{sid}/report").json()
    assert view["default"] and view["values"]["d-queue"]["items"][0]["body"]["title"] == "Song 1"
    assert client.get("/spaces/sp_nothere/report").json()["error"] == "unknown_ref"
    empty = project(daemon, kinds=[], name="Nothing kept")
    r = client.get(f"/spaces/{empty}/report")
    assert r.status_code == 400 and r.json() == {
        "error": "bad_request",
        "reason": "this project keeps no records",
    }


def test_compose_through_the_route(
    client: TestClient, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid = project(daemon)
    _engine(monkeypatch, Fake([json.dumps(spec(QUEUE, block("g", "gauge", "Speed")))]))
    r = client.post(f"/spaces/{sid}/report/compose")
    assert r.status_code == 200
    view = r.json()
    assert [b["id"] for b in view["spec"]["blocks"]] == ["q"] and view["dropped"] == 1
    assert client.get(f"/spaces/{sid}/report").json()["spec"] == view["spec"]


def test_compose_refusals(client: TestClient, daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = project(daemon, kinds=[], name="Nothing kept")
    fake = Fake([json.dumps(spec(QUEUE))])
    _engine(monkeypatch, fake)
    assert client.post(f"/spaces/{empty}/report/compose").json()["error"] == "bad_request"
    assert fake.asked == []  # refused before the engine
    sid = project(daemon)
    _engine(monkeypatch, EngineError("There is no Meta key"))
    r = client.post(f"/spaces/{sid}/report/compose")
    assert r.status_code == 503 and r.json() == {
        "error": "engine_unavailable",
        "reason": "There is no Meta key",
    }


def test_put_pins(client: TestClient, daemon: Daemon) -> None:
    sid = project(daemon)
    r = client.put(f"/spaces/{sid}/report/pins", json={"pinned": ["d-queue"]})
    assert r.status_code == 200 and r.json()["pinned"] == ["d-queue"]
    assert client.get(f"/spaces/{sid}/report").json()["pinned"] == ["d-queue"]
    assert client.put(f"/spaces/{sid}/report/pins", json={"pinned": ["zz"]}).status_code == 400
    assert client.put(f"/spaces/{sid}/report/pins", json={"pinned": "d-queue"}).status_code == 400
    assert client.put(f"/spaces/{sid}/report/pins", content=b"[]").status_code == 400


def test_the_routes_wire_the_shape_trigger(
    client: TestClient, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    from athena.report import compose

    sid = project(daemon)
    calls: list[tuple[str, str, int, int]] = []
    monkeypatch.setattr(
        compose, "on_records_changed", lambda _d, _e, s, k, b, a: calls.append((s, k, b, a)) or True
    )
    assert daemon.records.on_change is not None
    daemon.records.on_change(sid, "track", 0, 1)
    assert calls == [(sid, "track", 0, 1)]


# --- the ledger, per project ----------------------------------------------------------------------


def _row(daemon: Daemon, space_id: str, cost: float | None) -> None:
    daemon.ledger.record(
        surface="report", space_id=space_id, engine="muse", model="m", latency_ms=1, ok=True,
        cost_usd=cost, cost_estimated=cost is not None,
    )  # fmt: skip


def test_the_ledger_filters_by_project_with_its_own_totals(daemon: Daemon) -> None:
    _row(daemon, "sp_a", 0.5)
    _row(daemon, "sp_b", 0.25)
    _row(daemon, "sp_a", None)
    _row(daemon, "", 1.0)
    a = daemon.ledger.page(10, "sp_a")
    assert [r["space_id"] for r in a["rows"]] == ["sp_a", "sp_a"]
    assert a["totals"] == {"calls": 2, "cost_usd": 0.5, "cost_estimated": True}
    assert daemon.ledger.page(10)["totals"]["calls"] == 4
    assert daemon.ledger.page(1, "sp_a")["totals"]["calls"] == 2  # totals are over every filtered row
    assert daemon.ledger.page(10, "sp_none")["totals"] == {
        "calls": 0,
        "cost_usd": 0.0,
        "cost_estimated": False,
    }


def test_the_ledger_route_takes_a_space(client: TestClient, daemon: Daemon) -> None:
    _row(daemon, "sp_a", 0.5)
    _row(daemon, "sp_b", 0.25)
    _row(daemon, "", 1.0)
    assert [r["space_id"] for r in client.get("/ledger?space=sp_b").json()["rows"]] == ["sp_b"]
    core = client.get("/ledger?space=core").json()
    assert [r["space_id"] for r in core["rows"]] == [""]
    assert client.get("/ledger").json()["totals"]["calls"] == 3
    assert client.get("/ledger?space=sp_a&limit=501").status_code == 400
