"""A project's apps by kind (ADR 0025) and this device's apps (ADR 0026): the store. Each kind accepted
and refused by its own rule, slugs unique in their space, one cap shared with the web origins, a
token sealed outside the database and unsealed only by `token()`, and everything erased with its
space."""

from __future__ import annotations

import typing
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from athena.app import Daemon
from athena.apps.store import web_id
from athena.contracts import APPS_MAX, DEVICE_APPS_MAX, App, AppEvent, AppNew
from athena.errors import ApiError

SECRET = "tok-" + "9f3c" * 8  # a made-up token; never a real one


_HINTS = typing.get_type_hints(App, include_extras=True)
#: The contract's App keys, and the ones it requires (NotRequired read from the annotations).
APP_KEYS = set(_HINTS)
APP_REQUIRED = {k for k, v in _HINTS.items() if typing.get_origin(v) is not typing.NotRequired}


def shaped(app: App) -> App:
    """Every App answered keeps to the contract: no key outside it, every required key present."""
    keys = set(app)
    assert keys <= APP_KEYS, keys - APP_KEYS
    assert keys >= APP_REQUIRED, APP_REQUIRED - keys
    assert all(v is not None for v in app.values())
    return app


def new(**fields: Any) -> AppNew:
    return cast("AppNew", fields)


@pytest.fixture
def disk(tmp_path: Path) -> Iterator[Daemon]:
    d = Daemon.open(tmp_path / "data")
    yield d
    d.store.close()


def project(daemon: Daemon, apps: list[str] | None = None) -> str:
    return daemon.spaces.create({"name": "Label", "apps": apps or []})["id"]


def refused(fn: Any, *args: Any) -> str:
    with pytest.raises(ApiError) as e:
        fn(*args)
    assert e.value.error == "bad_request" and e.value.status == 400
    return e.value.reason


def test_a_website_is_a_public_origin(daemon: Daemon) -> None:
    space = project(daemon)
    app = shaped(daemon.apps.add(space, new(kind="website", address="Studio.Example.com")))
    assert app["kind"] == "website" and app["address"] == "https://studio.example.com"
    assert app["app_id"] == web_id("https://studio.example.com") and app["app_id"].startswith("web_")
    assert (app["label"], app["slug"], app["status"]) == (
        "studio.example.com",
        "studio_example_com",
        "unchecked",
    )
    assert app["tools"] == [] and app["remotes"] == [] and app["sealed"] is False
    assert daemon.spaces.get(space)["apps"] == ["https://studio.example.com"]
    assert "page on this computer" in refused(
        daemon.apps.add, space, new(kind="website", address="http://localhost:3000")
    )
    refused(daemon.apps.add, space, new(kind="website", address="https://x.example/path"))
    refused(daemon.apps.add, space, new(kind="website", address="https://studio.example.com"))  # twice
    refused(daemon.apps.add, space, new(kind="website", address="https://y.example", token="x"))
    refused(daemon.apps.add, space, new(kind="nonsense", address="https://y.example"))


def test_a_local_page_is_loopback_and_wiring_it_is_its_onboarding(daemon: Daemon) -> None:
    space = project(daemon)
    assert not daemon.sites.trusted(space, "http://localhost:3000")
    app = shaped(
        daemon.apps.add(space, new(kind="local_page", address="http://localhost:3000", label="Mixer"))
    )
    assert app["kind"] == "local_page" and app["address"] == "http://localhost:3000"
    assert daemon.sites.trusted(space, "http://localhost:3000")
    site = daemon.sites.get(space, "http://localhost:3000")
    assert site["blocks"] == ["wired by you"] and site["label"] == "Mixer" and site["access"] == "unknown"
    refused(daemon.apps.add, space, new(kind="local_page", address="https://studio.example.com"))
    for loop in ("http://127.0.0.1:8080", "http://[::1]:9000"):
        assert daemon.apps.add(space, new(kind="local_page", address=loop))["kind"] == "local_page"
    # a look that found the person signed in reads ok
    daemon.sites.looked(space, "http://localhost:3000", "signed_in", "opened")
    assert daemon.apps.views(space)[0]["status"] == "ok"
    # an origin added the old way (PATCH spaces.apps) is listed with its derived kind
    daemon.spaces.update(space, {"apps": [*daemon.spaces.get(space)["apps"], "http://localhost:5173"]})
    assert [a["kind"] for a in daemon.apps.views(space)] == ["local_page"] * 4
    assert daemon.apps.views(space)[-1]["status"] == "unchecked"


def test_an_app_answering_at_an_address_is_on_this_computer_only(daemon: Daemon) -> None:
    space = project(daemon)
    app = shaped(daemon.apps.add(space, new(kind="mcp_http", address="http://127.0.0.1:7400/mcp")))
    assert app["app_id"].startswith("app_") and app["address"] == "http://127.0.0.1:7400/mcp"
    assert (app["label"], app["slug"], app["status"]) == ("127.0.0.1:7400", "app_127_0_0_1_7400", "unchecked")
    assert "argv" not in app and "offered" not in app
    assert "this computer" in refused(
        daemon.apps.add, space, new(kind="mcp_http", address="https://api.example.com/mcp")
    )
    refused(daemon.apps.add, space, new(kind="mcp_http", address="ftp://localhost/x"))
    refused(daemon.apps.add, space, new(kind="mcp_http", address="http://u:p@localhost:1/"))
    refused(daemon.apps.add, space, new(kind="mcp_http"))
    refused(daemon.apps.add, space, new(kind="mcp_http", address="http://localhost:1", offered=True))
    assert [r.app_id for r in daemon.apps.rows(space)] == [app["app_id"]]


def test_a_tool_she_starts_is_a_command(daemon: Daemon) -> None:
    space = project(daemon)
    app = shaped(
        daemon.apps.add(space, new(kind="mcp_stdio", argv=["tools/gravitone.exe", "--serve", "a b"]))
    )
    assert app["argv"] == ["tools/gravitone.exe", "--serve", "a b"]
    assert app["address"] == "tools/gravitone.exe --serve a b"
    assert (app["label"], app["slug"]) == ("gravitone", "gravitone")
    for bad in ([], [""], ["x", 3], "gravitone --serve", None):
        refused(daemon.apps.add, space, new(kind="mcp_stdio", argv=bad))
    refused(daemon.apps.add, space, new(kind="mcp_stdio", argv=["x"], address="http://localhost:1"))


def test_slugs_are_unique_in_their_space(daemon: Daemon) -> None:
    space = project(daemon, ["https://gravitone.example"])
    slugs = [
        daemon.apps.add(space, new(kind="mcp_stdio", argv=["gravitone"]))["slug"],
        daemon.apps.add(space, new(kind="mcp_stdio", argv=["gravitone"], label="Gravitone"))["slug"],
        daemon.apps.add(space, new(kind="mcp_http", address="http://localhost:1", label="Gravitone!"))[
            "slug"
        ],
        daemon.apps.add(space, new(kind="mcp_stdio", argv=["x"], label="Mix-Down 2"))["slug"],
    ]
    assert slugs == ["gravitone", "gravitone_2", "gravitone_3", "mix_down_2"]
    other = project(daemon)
    assert daemon.apps.add(other, new(kind="mcp_stdio", argv=["gravitone"]))["slug"] == "gravitone"
    every = [a["slug"] for a in daemon.apps.views(space)]
    assert len(every) == len(set(every)) and every[0] == "gravitone_example"


def test_a_project_cap_counts_web_and_process_apps_together(daemon: Daemon) -> None:
    origins = [f"https://s{i}.example" for i in range(APPS_MAX - 1)]
    space = project(daemon, origins)
    daemon.apps.add(space, new(kind="mcp_stdio", argv=["one"]))
    assert len(daemon.apps.views(space)) == APPS_MAX
    refused(daemon.apps.add, space, new(kind="mcp_stdio", argv=["two"]))
    refused(daemon.apps.add, space, new(kind="website", address="https://more.example"))
    # the old PATCH of spaces.apps sees the process app too
    refused(daemon.spaces.update, space, {"apps": [*origins, "https://more.example"]})
    daemon.spaces.update(space, {"apps": origins[:-1]})  # dropping one stays possible


def test_device_level_apps(daemon: Daemon, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    app = shaped(
        daemon.apps.add("", new(kind="mcp_stdio", argv=["gravitone"], offered=True, output_dir=str(out)))
    )
    assert app["offered"] is True and app["output_dir"] == str(out)
    plain = shaped(daemon.apps.add("", new(kind="mcp_http", address="http://localhost:9")))
    assert plain["offered"] is False
    assert [r.app_id for r in daemon.apps.offered()] == [app["app_id"]]
    assert [a["app_id"] for a in daemon.apps.views("")] == [app["app_id"], plain["app_id"]]
    refused(daemon.apps.add, "", new(kind="website", address="https://x.example"))
    refused(daemon.apps.add, "", new(kind="mcp_stdio", argv=["y"], output_dir="relative/folder"))
    refused(daemon.apps.add, "", new(kind="mcp_stdio", argv=["y"], output_dir=str(out / "missing")))
    refused(daemon.apps.add, "", new(kind="mcp_stdio", argv=["y"], offered="yes"))
    # a project's process app may name an output folder (local app_fetch), never be offered
    space = project(daemon)
    assert daemon.apps.add(space, new(kind="mcp_stdio", argv=["z"], output_dir=str(out)))[
        "output_dir"
    ] == str(out)
    for i in range(DEVICE_APPS_MAX - 2):
        daemon.apps.add("", new(kind="mcp_stdio", argv=[f"t{i}"]))
    refused(daemon.apps.add, "", new(kind="mcp_stdio", argv=["over"]))


def test_a_token_is_sealed_outside_the_database(disk: Daemon) -> None:
    space = project(disk)
    app = shaped(
        disk.apps.add(space, new(kind="mcp_http", address="http://localhost:7400/mcp", token=SECRET))
    )
    assert app["sealed"] is True and SECRET not in str(app)
    assert disk.apps.token(space, app["app_id"]) == SECRET
    assert disk.data_dir is not None
    for name in ("athena.db", "athena.db-wal"):
        path = disk.data_dir / name
        if path.exists():
            assert SECRET.encode() not in path.read_bytes()
    bare = disk.apps.add(space, new(kind="mcp_stdio", argv=["x"]))
    assert bare["sealed"] is False and disk.apps.token(space, bare["app_id"]) is None
    disk.apps.remove(space, app["app_id"])
    assert disk.apps.token(space, app["app_id"]) is None


def test_no_data_dir_refuses_a_token(daemon: Daemon) -> None:
    space = project(daemon)
    assert "token" in refused(
        daemon.apps.add, space, new(kind="mcp_http", address="http://localhost:1", token=SECRET)
    )
    assert daemon.apps.views(space) == []


def test_erased_with_the_space(disk: Daemon) -> None:
    space = project(disk)
    app = disk.apps.add(space, new(kind="mcp_http", address="http://localhost:1", token=SECRET))
    disk.apps.add(space, new(kind="local_page", address="http://localhost:3000"))
    disk.apps.put_remote(
        space,
        app["app_id"],
        {"peer_id": "p1", "device": "Studio PC", "remote_app_id": "app_b", "status": "ok", "tools": []},
    )
    device = disk.apps.add("", new(kind="mcp_stdio", argv=["kept"]))
    sealed = disk.apps._seal_port()
    assert sealed.unseal(f"app.{app['app_id']}") == SECRET
    disk.spaces.erase(space)
    for table in ("apps", "app_remotes", "sites"):
        assert disk.store.query(f"SELECT 1 FROM {table} WHERE space_id = ?", (space,)) == []
    assert sealed.unseal(f"app.{app['app_id']}") is None
    assert [a["app_id"] for a in disk.apps.views("")] == [device["app_id"]]


def test_remove_probe_remotes_and_events(daemon: Daemon) -> None:
    heard: list[AppEvent] = []
    daemon.events.publish = heard.append  # type: ignore[method-assign]
    space = project(daemon)
    web = daemon.apps.add(space, new(kind="local_page", address="http://localhost:3000"))
    proc = daemon.apps.add(space, new(kind="mcp_stdio", argv=["gravitone"]))
    tool = {"name": "render", "description": "Renders a mix.", "access": "gated"}
    probed = shaped(daemon.apps.set_probe(space, proc["app_id"], "ok", [tool], None))  # type: ignore[list-item]
    assert probed["tools"] == [tool] and probed["status"] == "ok" and "checked_at" in probed
    remote = shaped(
        daemon.apps.put_remote(
            space,
            proc["app_id"],
            {"peer_id": "p1", "device": "Studio PC", "remote_app_id": "app_b", "status": "ok", "tools": []},
        )
    )
    assert [r["device"] for r in remote["remotes"]] == ["Studio PC"]
    assert daemon.apps.remotes(space, proc["app_id"])[0]["remote_app_id"] == "app_b"
    daemon.apps.drop_remote(space, proc["app_id"], "p1")
    assert daemon.apps.remotes(space, proc["app_id"]) == []
    with pytest.raises(ApiError):
        daemon.apps.put_remote(
            space,
            web["app_id"],
            {"peer_id": "p1", "device": "x", "remote_app_id": "y", "status": "ok", "tools": []},
        )
    daemon.apps.remove(space, web["app_id"])
    assert daemon.spaces.get(space)["apps"] == []
    assert daemon.sites.trusted(space, "http://localhost:3000")  # its sites row is left alone
    daemon.apps.remove(space, proc["app_id"])
    assert daemon.apps.views(space) == []
    with pytest.raises(ApiError) as e:
        daemon.apps.get(space, proc["app_id"])
    assert e.value.error == "unknown_ref"
    assert {"type": "app", "space_id": space} in heard
    assert sum(1 for h in heard if h["type"] == "app") == 7
