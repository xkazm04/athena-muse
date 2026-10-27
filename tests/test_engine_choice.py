"""One choice function picks the engine, and every site that needs one asks it."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import athena.engine as engine_mod
from athena import routes_turn
from athena.contracts import EngineId
from athena.engine import EngineError, build_engine, choose, engine_model, status
from athena.engine.claude_code import ClaudeCodeEngine
from athena.engine.meta import MuseEngine
from athena.engine.muse_code import MuseCodeEngine
from athena.engine.scripted import ScriptedEngine
from athena.keys import KeyStore

ENV = ("ATHENA_ENGINE", "ATHENA_MODEL", "META_MODEL", "META_API_KEY", "META_BASE_URL")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    routes_turn.TRANSPORT = None
    yield


def on_path(monkeypatch: pytest.MonkeyPatch, *programs: str) -> None:
    found = {p: f"/bin/{p}" for p in programs}
    monkeypatch.setattr("athena.engine.cli.which", lambda name: found.get(name))


def keys(with_key: bool) -> KeyStore:
    store = KeyStore(None)
    if with_key:
        store.save("sk-test")
    return store


@pytest.mark.parametrize(
    ("env", "with_key", "path", "expected"),
    [
        ("", False, (), ScriptedEngine),
        ("", True, (), MuseEngine),
        ("scripted", True, (), ScriptedEngine),
        ("muse", True, (), MuseEngine),
        ("muse", False, (), "no Meta key"),
        ("muse_code", False, ("muse",), MuseCodeEngine),
        ("muse_code", True, (), "Muse Code is not installed"),
        ("claude_code", False, ("claude",), ClaudeCodeEngine),
        ("CLAUDE_CODE", True, ("claude", "muse"), ClaudeCodeEngine),
        ("claude_code", False, ("muse",), "Claude Code is not installed"),
        ("gpt", True, ("claude", "muse"), "ATHENA_ENGINE must be one of"),
    ],
)
def test_selection_matrix(
    monkeypatch: pytest.MonkeyPatch, env: str, with_key: bool, path: tuple[str, ...], expected: type | str
) -> None:
    if env:
        monkeypatch.setenv("ATHENA_ENGINE", env)
    on_path(monkeypatch, *path)
    if isinstance(expected, str):
        with pytest.raises(EngineError, match=expected):
            build_engine(keys(with_key))
        return
    engine = build_engine(keys(with_key))
    assert isinstance(engine, expected)
    if engine.id != "scripted":  # status names the engine actually built
        assert status(keys(with_key))["engine"] == engine.id
    assert status(keys(with_key))["simulated"] is (engine.id == "scripted")


@pytest.mark.parametrize(
    ("engine_id", "athena_model", "meta_model", "expected"),
    [
        ("muse", "", "", "muse-spark-1.3"),
        ("muse", "", "muse-spark-1.2", "muse-spark-1.2"),
        ("muse", "muse-wonder-1.0", "muse-spark-1.2", "muse-wonder-1.0"),
        ("muse_code", "", "muse-spark-1.2", "muse-spark-1.3"),
        ("muse_code", "muse-wonder-1.0", "", "muse-wonder-1.0"),
        ("claude_code", "", "", "sonnet"),
        ("claude_code", "opus", "", "opus"),
        ("scripted", "opus", "", "scripted"),
    ],
)
def test_model_overrides(
    monkeypatch: pytest.MonkeyPatch, engine_id: EngineId, athena_model: str, meta_model: str, expected: str
) -> None:
    if athena_model:
        monkeypatch.setenv("ATHENA_MODEL", athena_model)
    if meta_model:
        monkeypatch.setenv("META_MODEL", meta_model)
    assert engine_model(engine_id) == expected


@pytest.mark.parametrize("engine_id", ["muse", "muse_code"])
def test_contributor_models_refused_for_every_muse_engine(
    monkeypatch: pytest.MonkeyPatch, engine_id: str
) -> None:
    monkeypatch.setenv("ATHENA_ENGINE", engine_id)
    monkeypatch.setenv("ATHENA_MODEL", "muse-spark-1.3-Contributor")
    on_path(monkeypatch, "muse")
    with pytest.raises(EngineError, match="trains on your content"):
        build_engine(keys(True))


def test_claude_code_may_use_any_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATHENA_ENGINE", "claude_code")
    monkeypatch.setenv("ATHENA_MODEL", "contributor-free-sonnet")
    on_path(monkeypatch, "claude")
    assert build_engine(keys(False)).model == "contributor-free-sonnet"


def test_status_reports_the_chosen_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    assert status(keys(False)) == {
        "engine": "scripted",
        "model": "scripted",
        "key": "absent",
        "simulated": True,
    }
    monkeypatch.setenv("ATHENA_ENGINE", "muse_code")
    assert status(keys(True)) == {
        "engine": "muse_code",
        "model": "muse-spark-1.3",
        "key": "file",
        "simulated": False,
    }
    assert choose(keys(False)) == "muse_code"


def test_every_route_asks_the_one_choice_function(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    asked: list[str] = []

    def spy(_: KeyStore) -> EngineId:
        asked.append("x")
        return "scripted"

    monkeypatch.setattr(engine_mod, "choose", spy)
    assert client.get("/engine").json()["engine"] == "scripted"
    assert len(asked) == 1
    assert client.post("/engine/probe").json()["ok"] is True
    assert len(asked) == 3  # the row's engine, then the build
    resp = client.post("/run", json={"text": "hello", "space_id": ""})
    assert resp.status_code == 200 and len(asked) == 4


def test_routes_name_no_engine_of_their_own() -> None:
    source = (Path(routes_turn.__file__)).read_text(encoding="utf-8")
    assert not re.search(r"[\"'](muse|muse_code|claude_code|scripted)[\"']", source)


def test_a_bad_engine_name_is_a_plain_words_answer(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setenv("ATHENA_ENGINE", "gpt")
    resp = client.get("/engine")
    assert resp.status_code >= 400
    assert "ATHENA_ENGINE must be one of" in resp.json()["reason"]
    probe = client.post("/engine/probe").json()
    assert probe["ok"] is False and "ATHENA_ENGINE" in probe["error"]
    run = client.post("/run", json={"text": "hello", "space_id": ""})
    assert run.json()["error"] == "engine_unavailable"


def test_a_missing_cli_probe_is_recorded_against_the_chosen_engine(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.setenv("ATHENA_ENGINE", "claude_code")
    on_path(monkeypatch)
    probe = client.post("/engine/probe").json()
    assert probe == {
        "ok": False,
        "error": "Claude Code is not installed: put `claude` on PATH, or set another ATHENA_ENGINE",
    }
