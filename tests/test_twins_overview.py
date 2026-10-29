"""The overview: `GET /twins` answers a TwinPage whose stat strip follows SCHEMA's formulas over the
rows, with an unmeasured figure omitted ("-" on screen), never 0; a twin's week costs are its
Project's ledger rows on surface `twin` from the last seven days."""

from __future__ import annotations

from typing import Any

from starlette.testclient import TestClient

from athena import contracts
from athena.app import Daemon
from athena.contracts import TwinPage, TwinSummary
from athena.twins.view import health
from connectors_kit import conforms


def twin(daemon: Daemon, client: TestClient, name: str, state: str, missions: list[str]) -> tuple[str, str]:
    space = client.post(contracts.ROUTES["spaces"], json={"name": name}).json()["id"]
    twin_id = client.post(contracts.ROUTES["twins"], json={"space_id": space}).json()["id"]
    daemon.twins.put(twin_id, state=state)  # type: ignore[arg-type]
    for i, mission_state in enumerate(missions):
        body: dict[str, Any] = {
            "twin_id": twin_id,
            "title": f"Mission {i}",
            "with": "Someone",
            "channel": "gmail",
            "goal": "A goal",
            "state": mission_state,
            "beats": [],
            "created": "2026-10-29T10:00:00Z",
        }
        daemon.twins.save("missions", twin_id, space, f"ms_{name}{i}", body)
    return twin_id, space


def cost(daemon: Daemon, space: str, usd: float, *, surface: str = "twin", ts: str | None = None) -> None:
    row = daemon.ledger.record(
        surface=surface,  # type: ignore[arg-type]
        space_id=space,
        engine="muse",
        model="m",
        latency_ms=1,
        ok=True,
        cost_usd=usd,
        cost_estimated=True,
    )
    if ts is not None:
        daemon.store.run("UPDATE ledger SET ts = ? WHERE id = ?", (ts, row["id"]))


def test_an_empty_overview_measures_nothing(client: TestClient) -> None:
    page = client.get(contracts.ROUTES["twins"]).json()
    assert page == {"twins": [], "stats": {"live": 0, "waiting_for_you": 0, "missions_open": 0}}


def test_the_stat_strip_follows_the_schemas_formulas(daemon: Daemon, client: TestClient) -> None:
    desk, desk_space = twin(daemon, client, "Desk", "live", ["open", "resolved", "handed_back"])
    family, family_space = twin(daemon, client, "Family", "paused", ["resolved"])
    partners, partners_space = twin(daemon, client, "Partners", "setting_up", [])
    cost(daemon, desk_space, 1.234)
    cost(daemon, desk_space, 0.6)
    cost(daemon, desk_space, 5.0, surface="turn")  # not the twin's
    cost(daemon, desk_space, 9.0, ts="2026-01-01T00:00:00Z")  # older than a week
    cost(daemon, partners_space, 0.06)

    page: TwinPage = client.get(contracts.ROUTES["twins"]).json()
    conforms(page, TwinPage)
    rows = {t["id"]: t for t in page["twins"]}
    for row in rows.values():
        conforms(row, TwinSummary)
    assert list(rows) == [desk, family, partners]
    assert rows[desk]["week"] == {"cost_usd": 1.834}
    assert rows[family]["week"] == {}  # nothing measured: every figure omitted, never 0
    assert rows[partners]["week"] == {"cost_usd": 0.06}
    assert (rows[desk]["open_missions"], rows[family]["open_missions"]) == (2, 0)
    assert rows[partners]["readiness"] == 0 and rows[partners]["name"] == "Partners"

    # SCHEMA: live = rows live; waiting_for_you = waiting + handed back; missions_open = open or
    # handed back; the weekly sums skip what was not measured, money to the cent
    assert page["stats"] == {"live": 1, "waiting_for_you": 1, "missions_open": 2, "cost_usd_week": 1.89}
    assert family_space


def test_a_channels_health_follows_when_it_last_spoke() -> None:
    from datetime import UTC, datetime

    now = datetime(2026, 10, 29, 16, 20, tzinfo=UTC)
    assert health("2026-10-29T15:52:00Z", now) == "active"
    assert health("2026-10-27T10:05:00Z", now) == "quiet"
    assert health("2026-09-26T19:30:00Z", now) == "stale"
    assert health("", now) is None and health("not a time", now) is None
