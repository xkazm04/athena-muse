"""A plan-billed engine's ledger row carries no dollar figure; a priced engine's carries one."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from athena.app import Daemon
from athena.contracts import Probe
from athena.engine import TextDelta, Usage
from athena.turn import run_turn


class _Engine:
    simulated = False

    def __init__(self, engine_id: str, cost_estimated: bool) -> None:
        self.id = engine_id
        self.model = "muse-spark-1.3"
        self.cost_estimated = cost_estimated

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[Any]:
        yield TextDelta("Done.")
        yield Usage(input_tokens=16000, output_tokens=40)

    def probe(self) -> Probe:
        return {"ok": True}


@pytest.mark.parametrize(
    ("engine_id", "estimated", "priced"), [("muse_code", False, False), ("muse", True, True)]
)
def test_only_an_estimating_engine_is_priced_from_the_list(
    engine_id: str, estimated: bool, priced: bool
) -> None:
    daemon = Daemon.open(None)
    list(run_turn(daemon, _Engine(engine_id, estimated), "hello", ""))  # type: ignore[arg-type]
    row = daemon.ledger.page(5)["rows"][0]
    assert ("cost_usd" in row) is priced
    assert row["cost_estimated"] is estimated
