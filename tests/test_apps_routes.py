"""The apps routes (ADR 0025, 0026) through the HTTP app: list, add, delete and probe for a project and
for this device, attaching a paired device's instance, the AppList/App envelopes, and no token in
any answer. The app clients and the peer side are fakes here: these tests stand without them."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.apps import routes as routes_apps
from athena.apps.client import Probe
from athena.apps.store import AppRow
from athena.contracts import ROUTES, App, AppList, AppTool, OfferedApp
from athena.server import create_app
from test_apps_store import SECRET, shaped

TOOL: AppTool = {"name": "render", "description": "Renders a mix.", "access": "gated"}


def path(name: str, space: str = "", app_id: str = "") -> str:
    return ROUTES[name].replace("{id}", space).replace("{app_id}", app_id)


class FakeClients:
    def __init__(self) -> None:
        self.seen: list[tuple[str, str | None]] = []

    def probe(self, row: AppRow, token: str | None) -> Probe:
        self.seen.append((row.app_id, token))
        return Probe("ok", [TOOL], None)


@dataclass
class FakePeer:
    name: str


class FakeRegistry:
    def get(self, peer_id: str) -> FakePeer | None:
        return FakePeer("Studio PC") if peer_id == "p1" else None


class FakePeers:
    registry = FakeRegistry()


@pytest.fixture
def disk(tmp_path: Path) -> Iterator[Daemon]:
    d = Daemon.open(tmp_path / "data")
    yield d
    d.store.close()


@pytest.fixture
def fake(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> FakeClients:
    f = FakeClients()
    monkeypatch.setattr(daemon, "app_clients", f)
    return f


def app_of(r: Any) -> App:
    body = r.json()
    assert r.status_code in (200, 201), r.text
    return shaped(body)


def listed(r: Any) -> list[App]:
    assert r.status_code == 200, r.text
    body: AppList = r.json()
    assert set(body) == {"apps"}
    return [shaped(a) for a in body["apps"]]


def test_a_project_lists_adds_probes_and_deletes(
    daemon: Daemon, client: TestClient, fake: FakeClients, monkeypatch: pytest.MonkeyPatch
) -> None:
    space = daemon.spaces.create({"name": "Label", "apps": ["https://studio.example.com"]})["id"]
    assert [a["kind"] for a in listed(client.get(path("space_apps", space)))] == ["website"]

    page = app_of(
        client.post(path("space_apps", space), json={"kind": "local_page", "address": "localhost:3000"})
    )
    assert page["kind"] == "local_page" and daemon.sites.trusted(space, "http://localhost:3000")
    proc = app_of(client.post(path("space_apps", space), json={"kind": "mcp_stdio", "argv": ["gravitone"]}))
    r = client.post(path("space_apps", space), json={"kind": "website", "address": "http://127.0.0.1:8"})
    assert r.status_code == 400 and r.json()["error"] == "bad_request"
    assert "page on this computer" in r.json()["reason"]
    assert client.post(path("space_apps", space), json=["no"]).status_code == 400
    assert [a["app_id"] for a in listed(client.get(path("space_apps", space)))][1:] == [
        page["app_id"],
        proc["app_id"],
    ]

    probed = app_of(client.post(path("space_app_probe", space, proc["app_id"])))
    assert probed["status"] == "ok" and probed["tools"] == [TOOL] and fake.seen == [(proc["app_id"], None)]

    monkeypatch.setattr(routes_apps, "reach", lambda origin: None)
    web = app_of(
        client.post(
            path("space_app_probe", space, listed(client.get(path("space_apps", space)))[0]["app_id"])
        )
    )
    assert web["status"] == "ok" and "checked_at" in web
    monkeypatch.setattr(routes_apps, "reach", lambda origin: f"Athena could not reach {origin}: refused")
    down = app_of(client.post(path("space_app_probe", space, page["app_id"])))
    assert down["status"] == "unreachable" and "could not reach" in down["reason"]

    assert client.delete(path("space_app", space, proc["app_id"])).status_code == 200
    assert client.delete(path("space_app", space, proc["app_id"])).json()["error"] == "unknown_ref"
    assert client.delete(path("space_app", space, page["app_id"])).status_code == 200
    assert daemon.spaces.get(space)["apps"] == ["https://studio.example.com"]
    assert client.get(path("space_apps", "core")).status_code == 404
    assert client.get(path("space_apps", "sp_nothing")).json()["error"] == "unknown_ref"


def test_this_devices_apps_live_at_apps(daemon: Daemon, client: TestClient, fake: FakeClients) -> None:
    assert ROUTES["device_apps"] == "/apps"
    assert listed(client.get(path("device_apps"))) == []
    app = app_of(
        client.post(
            path("device_apps"),
            json={"kind": "mcp_http", "address": "http://localhost:7400/mcp", "offered": True},
        )
    )
    assert app["offered"] is True
    assert [a["app_id"] for a in listed(client.get(path("device_apps")))] == [app["app_id"]]
    assert app_of(client.post(path("device_app_probe", app_id=app["app_id"])))["tools"] == [TOOL]
    r = client.post(path("device_apps"), json={"kind": "website", "address": "https://x.example"})
    assert r.status_code == 400
    assert client.delete(path("device_app", app_id=app["app_id"])).status_code == 200
    assert listed(client.get(path("device_apps"))) == []


def test_no_token_in_any_answer(disk: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClients()
    monkeypatch.setattr(disk, "app_clients", fake)
    client = TestClient(create_app(disk, token="t"), headers={"Authorization": "Bearer t"})
    space = disk.spaces.create({"name": "Label"})["id"]
    answers = [
        client.post(
            path("space_apps", space),
            json={"kind": "mcp_http", "address": "http://localhost:1", "token": SECRET},
        )
    ]
    app = app_of(answers[0])
    assert app["sealed"] is True
    answers.append(client.get(path("space_apps", space)))
    answers.append(client.post(path("space_app_probe", space, app["app_id"])))
    answers.append(
        client.post(path("device_apps"), json={"kind": "mcp_stdio", "argv": ["x"], "token": SECRET})
    )
    answers.append(client.get(path("device_apps")))
    for r in answers:
        assert r.status_code in (200, 201) and SECRET not in r.text
    assert fake.seen == [(app["app_id"], SECRET)]  # the probe was handed the unsealed token
    assert listed(answers[-1])[0]["sealed"] is True


def test_a_paired_devices_instance_is_attached(
    daemon: Daemon, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    space = daemon.spaces.create({"name": "Label"})["id"]
    app = app_of(client.post(path("space_apps", space), json={"kind": "mcp_stdio", "argv": ["gravitone"]}))
    url = path("space_app_remotes", space, app["app_id"])
    body = {"peer_id": "p1", "remote_app_id": "app_b"}

    r = client.post(url, json=body)  # this device works alone
    assert r.status_code == 409 and r.json()["error"] == "bad_request"

    monkeypatch.setattr(daemon, "peers", FakePeers())
    offer: OfferedApp = {
        "app_id": "app_b",
        "kind": "mcp_stdio",
        "label": "Gravitone",
        "tools": [TOOL],
        "has_output": True,
    }
    monkeypatch.setattr("athena.peer.apps.offers", lambda d, peer_id: [offer])
    assert client.post(url, json={"peer_id": "p9", "remote_app_id": "app_b"}).status_code == 404
    missing = client.post(url, json={"peer_id": "p1", "remote_app_id": "app_zz"})
    assert missing.status_code == 404 and "Studio PC" in missing.json()["reason"]
    attached = app_of(client.post(url, json=body))
    (remote,) = attached["remotes"]
    assert (remote["device"], remote["remote_app_id"], remote["status"], remote["tools"]) == (
        "Studio PC",
        "app_b",
        "ok",
        [TOOL],
    )
    assert listed(client.get(path("space_apps", space)))[0]["remotes"] == [remote]
