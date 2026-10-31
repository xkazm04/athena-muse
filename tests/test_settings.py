"""Settings (ADR 0012): the look, the engine choice and its refusals, through the real app."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.engine import build_engine, decide
from athena.engine.scripted import ScriptedEngine
from athena.keys import KeyStore
from athena.server import create_app
from athena.settings import DEFAULT_LOOK, ENGINE_KEY, THEME_KEY

TOKEN = "t"


@pytest.fixture(autouse=True)
def no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("META_API_KEY", raising=False)


def on_path(monkeypatch: pytest.MonkeyPatch, *programs: str) -> None:
    found = {p: f"/bin/{p}" for p in programs}
    monkeypatch.setattr("athena.engine.cli.which", lambda name: found.get(name))


def heard(daemon: Daemon) -> list[dict[str, Any]]:
    """Every event published from here on, kept in a list."""
    seen: list[dict[str, Any]] = []
    original = daemon.events.publish

    def keep(event: dict[str, Any]) -> None:
        seen.append(event)
        original(event)

    daemon.events.publish = keep  # type: ignore[method-assign]
    return seen


# --- the look -------------------------------------------------------------------------------------


def test_a_fresh_daemon_reads_the_default_look(client: TestClient) -> None:
    view = client.get("/settings").json()
    assert view["look"] == DEFAULT_LOOK == {"theme": "auto", "type_scale": "standard", "motion": "system"}
    assert view["engine"] == "scripted" and view["source"] == "default"
    assert "choice" not in view and "data_dir" not in view  # nothing on disk in a test


def test_the_look_is_written_and_both_windows_hear_it(client: TestClient, daemon: Daemon) -> None:
    seen = heard(daemon)
    r = client.post("/settings/look", json={"theme": "light", "motion": "calm"})
    assert r.status_code == 200
    assert r.json()["look"] == {"theme": "light", "type_scale": "standard", "motion": "calm"}
    assert seen == [{"type": "settings", "look": r.json()["look"]}]
    # A partial body keeps the rest.
    again = client.post("/settings/look", json={"type_scale": "large"}).json()["look"]
    assert again == {"theme": "light", "type_scale": "large", "motion": "calm"}


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ({"theme": "sepia"}, "theme must be one of auto, dark, light"),
        ({"type_scale": "compact"}, "type_scale must be one of standard, large"),
        ({"motion": "full"}, "motion must be one of system, calm"),
        ({"skin": "wavefront"}, "no look called skin"),
    ],
)
def test_a_bad_look_is_refused_whole(client: TestClient, body: dict[str, Any], said: str) -> None:
    # Beside a good value: one bad value writes nothing at all.
    good = {"type_scale": "large"} if "type_scale" not in body else {"theme": "dark"}
    r = client.post("/settings/look", json={**good, **body})
    assert r.status_code == 400 and said in r.json()["reason"]
    assert client.get("/settings").json()["look"] == DEFAULT_LOOK


def test_an_empty_look_is_refused(client: TestClient) -> None:
    r = client.post("/settings/look", json={})
    assert r.status_code == 400 and "send theme, type_scale or motion" in r.json()["reason"]


def test_a_body_that_is_not_an_object_is_refused(client: TestClient) -> None:
    assert client.post("/settings/look", content=b"nope").json()["error"] == "bad_request"
    assert client.post("/settings/engine", json=["muse"]).status_code == 400


def test_an_unknown_stored_row_reads_as_its_default(client: TestClient, daemon: Daemon) -> None:
    daemon.settings.set(THEME_KEY, "sepia")
    daemon.settings.set(ENGINE_KEY, "gpt")
    view = client.get("/settings").json()
    assert view["look"]["theme"] == "auto" and "choice" not in view


# --- the engine -----------------------------------------------------------------------------------


def test_options_say_what_each_engine_lacks(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    on_path(monkeypatch, "claude")
    engines = {o["id"]: o for o in client.get("/settings").json()["engines"]}
    assert engines["claude_code"] == {"id": "claude_code", "readiness": "ready"}
    assert engines["muse_code"]["readiness"] == "not_installed" and "`muse`" in engines["muse_code"]["reason"]
    assert engines["muse"]["readiness"] == "no_key" and "META_API_KEY" in engines["muse"]["reason"]
    assert engines["scripted"] == {"id": "scripted", "readiness": "simulated"}


def test_choosing_an_engine_moves_the_next_turn(
    client: TestClient, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    on_path(monkeypatch, "claude")
    seen = heard(daemon)
    r = client.post("/settings/engine", json={"engine": "claude_code"})
    assert r.status_code == 200
    view = r.json()
    assert view["engine"] == "claude_code" and view["source"] == "setting" and view["choice"] == "claude_code"
    assert client.get("/engine").json()["engine"] == "claude_code"
    assert seen[-1]["type"] == "engine" and seen[-1]["status"]["engine"] == "claude_code"
    # Built per request: no restart stands between the choice and the next turn.
    assert build_engine(KeyStore(None), stored=daemon.settings.engine_choice()).id == "claude_code"


@pytest.mark.parametrize(
    ("engine", "said"),
    [
        ("muse", "no Meta key"),
        ("muse_code", "Muse Code is not installed"),
        ("gpt", "engine must be one of"),
    ],
)
def test_an_engine_that_cannot_run_is_refused(
    client: TestClient, daemon: Daemon, monkeypatch: pytest.MonkeyPatch, engine: str, said: str
) -> None:
    on_path(monkeypatch)
    r = client.post("/settings/engine", json={"engine": engine})
    assert r.status_code in (400, 503) and said in r.json()["reason"]
    assert daemon.settings.engine_choice() == ""


def test_athena_engine_pins_the_engine_and_refuses_a_choice(
    client: TestClient, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    daemon.settings.set(ENGINE_KEY, "scripted")
    monkeypatch.setenv("ATHENA_ENGINE", "claude_code")
    on_path(monkeypatch, "claude")
    view = client.get("/settings").json()
    assert view["engine"] == "claude_code" and view["source"] == "env" and view["choice"] == "scripted"
    r = client.post("/settings/engine", json={"engine": "scripted"})
    assert r.json()["error"] == "engine_unavailable" and "ATHENA_ENGINE" in r.json()["reason"]


def test_a_muse_choice_without_a_key_runs_simulated_as_before() -> None:
    keys = KeyStore(None)
    assert decide(keys, "muse") == ("scripted", "default")
    keys.save("sk-test")
    assert decide(keys, "muse") == ("muse", "setting")
    assert decide(keys, "scripted") == ("scripted", "setting")
    assert decide(keys, "") == ("muse", "default")
    assert isinstance(build_engine(KeyStore(None), stored="scripted"), ScriptedEngine)


def test_a_key_saved_through_the_engine_routes_makes_muse_choosable(client: TestClient) -> None:
    assert client.post("/settings/engine", json={"engine": "muse"}).status_code == 503
    client.post("/engine/key", json={"key": "sk-test"})
    r = client.post("/settings/engine", json={"engine": "muse"})
    assert r.status_code == 200 and r.json()["engine"] == "muse"


@pytest.fixture
def on_disk(tmp_path: Path) -> Iterator[Daemon]:
    d = Daemon.open(tmp_path)
    yield d
    d.store.close()


def test_the_data_dir_is_said_when_there_is_one(on_disk: Daemon, tmp_path: Path) -> None:
    c = TestClient(create_app(on_disk, token=TOKEN), headers={"Authorization": f"Bearer {TOKEN}"})
    assert c.get("/settings").json()["data_dir"] == str(tmp_path)
    c.post("/settings/look", json={"theme": "dark"})
    reopened = Daemon.open(tmp_path)
    try:
        assert reopened.settings.look()["theme"] == "dark"  # a row, not a window's memory
    finally:
        reopened.store.close()
