"""The twins page's fixture (apps/desktop/src/main/twins/fixture/twins.ts) is what the daemon answers:
the generator drives it in-process on the scripted engine over the fake Gmail and Notion, every object
is checked against contracts.py, and the committed file is never out of date."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "twin_fixture.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("twin_fixture", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built() -> dict[str, Any]:
    return load().build()  # type: ignore[no-any-return]


def test_the_twin_fixture_is_current() -> None:
    # the daemon is driven again here: a change to the routes, the twin rules or the scripted engine
    # that changes what the page is shown makes the committed file stale
    assert load().main(["--check"]) == 0, "run: uv run python scripts/twin_fixture.py"


def test_the_check_refuses_a_null_an_unknown_key_and_a_missing_one(built: dict[str, Any]) -> None:
    m = load()
    twin: dict[str, Any] = built["page"]["twins"][0]
    for broken in (
        {**twin, "since": None},
        {**twin, "nickname": "desk"},
        {k: v for k, v in twin.items() if k != "purpose"},
    ):
        with pytest.raises(SystemExit):
            m.check(broken, m.C.TwinSummary, "twin")


def test_the_check_refuses_a_banned_word() -> None:
    with pytest.raises(SystemExit):
        load().plain_words({"line": "Paste your API key here"})


def test_the_setup_streams_the_ops_that_build_each_frame(built: dict[str, Any]) -> None:
    frames = built["setup"]["frames"]
    assert len(frames) == 12
    for f in frames:
        kinds = [e["type"] for e in f["events"]]
        assert kinds[0] == "start" and kinds[-1] == "done" and "coverage" in kinds
        assert f["events"][0]["engine"] == "scripted" and f["events"][0]["simulated"] is True
    assert [f["twin"]["readiness"] for f in frames] == [14, 21, 29, 36, 43, 43, 64, 79, 86, 100, 100, 100]
    assert built["setup"]["firstReadyFrame"] == 9
    assert built["setup"]["created"]["space_id"] != ""  # POST /twins {space_id: ""} made its own Project
    assert built["setup"]["golive"]["state"] == "live"


def test_the_rehearsal_is_one_stream_and_the_marks_never_play_it_again(built: dict[str, Any]) -> None:
    r = built["setup"]["rehearsal"]
    kinds = [e["event"]["type"] for e in r["events"]]
    assert kinds == ["turn"] * 5 + ["outcome"]
    played = [e["event"]["turn"] for e in r["events"] if e["event"]["type"] == "turn"]
    waits = [t["id"] for t in played if t.get("decision") == "waits"]
    assert waits == [m["mark"]["turn"] for m in r["marks"]] == ["t1", "t3"]
    # a mark answers the whole twin: the same turns, now marked, and nothing played again
    marked = r["marks"][-1]["twin"]["rehearsal"]["turns"]
    assert [t["id"] for t in marked] == [t["id"] for t in played]
    assert marked[2]["mark"] == "edited" and marked[0]["mark"] == "me"
    assert r["handed"]["events"][-1]["event"] == {"type": "outcome", "state": "handed_back"}


def test_the_overview_and_previews_come_from_the_daemon(built: dict[str, Any]) -> None:
    names = [(t["name"], t["state"]) for t in built["page"]["twins"]]
    assert names == [("Client desk", "live"), ("Family admin", "paused"), ("Partnerships", "setting_up")]
    desk = built["page"]["twins"][0]
    assert {d["reason"] for d in desk["waiting"]} == {"below_bar", "risk"}
    assert {m["state"] for m in desk["missions"] if not m.get("practice")} == {
        "open",
        "resolved",
        "handed_back",
    }
    assert built["pageAfter"]["stats"]["live"] == built["page"]["stats"]["live"] + 1
    partners = built["setup"]["twinId"]
    assert built["previews"][partners]["changed"] == ["1 more message you rewrote in your own words"]
    assert all(p["text"].startswith("(Simulated)") for p in built["previews"].values())
