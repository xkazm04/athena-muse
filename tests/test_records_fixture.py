"""The business fixture (business Phase 1): it seeds a simulated music channel through the daemon's own
code on a fresh folder, every name says simulated, and running it again changes nothing."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from athena.app import Daemon
from athena.records.store import may_render

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "business_fixture.py"
TODAY = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("business_fixture", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _counts(d: Daemon, space: str) -> dict[str, int]:
    rows = d.store.query("SELECT kind, COUNT(*) AS n FROM records WHERE space_id = ? GROUP BY kind", (space,))
    return {r["kind"]: r["n"] for r in rows}


def test_the_fixture_seeds_a_labelled_music_channel_and_is_idempotent(tmp_path: Path) -> None:
    fixture = load()
    d = Daemon.open(tmp_path / "data")
    try:
        space = fixture.seed(d, TODAY)
        assert d.spaces.get(space)["name"] == "Music channel (simulated)"
        assert len(d.records.kinds(space)) == 8
        records = d.records
        assert {
            k: records.count(space, k) for k in ("creator", "track", "thread", "agreement", "file", "stat")
        } == {
            "creator": 4,
            "track": 9,
            "thread": 3,
            "agreement": 3,
            "file": 1,
            "stat": 28,
        }
        tracks = [r["body"] for r in records.latest(space, "track")]
        verdicts = sorted(t.get("verdict", "-") for t in tracks)
        assert verdicts == ["-", "-", "-", "keep", "keep", "keep", "later", "pass", "pass"]
        assert all("(simulated)" in t["title"] for t in tracks)
        assert all("(simulated)" in r["body"]["name"] for r in records.latest(space, "creator"))
        states = sorted(r["body"]["state"] for r in records.latest(space, "agreement"))
        assert states == ["agreed", "declined", "proposed"]
        series = [
            r["body"]["value"]
            for r in reversed(records.latest(space, "stat"))
            if r["body"]["metric"] == "views"
        ]
        assert len(series) == 14
        file_body = records.latest(space, "file")[0]["body"]
        assert d.files.get(space, file_body["file_id"])["size"] > 0  # a real files row
        assert may_render(records, space, file_body["track_key"]) == {"ok": True, "reasons": []}
        renderable = [t["url"] for t in tracks if may_render(records, space, t["url"])["ok"]]
        assert renderable == [file_body["track_key"]]

        before = _counts(d, space)
        assert fixture.seed(d, TODAY) == space
        assert _counts(d, space) == before and len(d.spaces.list()) == 1 and len(d.files.list(space)) == 1
    finally:
        d.store.close()


def test_the_cli_prints_the_space_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert load().main([str(tmp_path / "data")]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["space_id"].startswith("spc_")
