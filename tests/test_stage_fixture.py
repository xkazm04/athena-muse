"""The stage's staged conversation (apps/desktop/src/main/stage/fixture/staged.ts) is generated from
its source through the daemon's own sketch rules, and the committed file is never out of date."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stage_fixture.py"


def test_the_staged_fixture_is_current() -> None:
    spec = importlib.util.spec_from_file_location("stage_fixture", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(["--check"]) == 0, "run: uv run python scripts/stage_fixture.py"
