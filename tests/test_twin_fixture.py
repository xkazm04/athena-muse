"""The twins page's fixture (apps/desktop/src/main/twins/fixture/twins.ts) is generated from the twin
prototypes' invented example in wire shape, every object checked against contracts.py, and the committed
file is never out of date."""

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


def test_the_twin_fixture_is_current() -> None:
    assert load().main(["--check"]) == 0, "run: uv run python scripts/twin_fixture.py"


def test_the_check_refuses_a_null_an_unknown_key_and_a_missing_one() -> None:
    m = load()
    out = m.build()
    twin: dict[str, Any] = out["page"]["twins"][0]
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


def test_the_setup_streams_the_ops_that_build_each_frame() -> None:
    out = load().build()
    frames = out["setup"]["frames"]
    assert len(frames) == 12
    for f in frames:
        kinds = [e["type"] for e in f["events"]]
        assert kinds[0] == "start" and kinds[-1] == "done" and "coverage" in kinds
    assert frames[-1]["twin"]["ready"] is True
    assert out["setup"]["golive"]["state"] == "live"
    assert all(p["confirmed"] for p in out["setup"]["golive"]["pieces"])
