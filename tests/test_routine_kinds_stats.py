"""The stats routine (business Phase 2, WP2.2): each reading becomes one stat measured at the run's own
read time, never a date the page claims; names come back lower_snake; no page address is skipped."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from athena.app import Daemon
from athena.routines import stats
from athena.routines.context import CeilingReached, Skip
from records_kit import project
from routine_kinds_kit import SITE, assert_fenced, context, fenced_text

PAGE = f"{SITE}/studio/analytics"
TEXT = "Channel analytics - Last updated 2026-10-15 - Views 12,480 - Subscribers 1,204 - Watch time 389.5"


def test_readings_become_stats_measured_at_the_read_time(daemon: Daemon) -> None:
    space = project(daemon)
    ctx = context(daemon, space, "stats", PAGE)
    ctx.page(PAGE, TEXT)
    ctx.answer(
        "readings",
        {
            "readings": [
                {"metric": "Views", "value": "12,480", "measured_at": "2026-10-15"},
                {"metric": "subscribers", "value": 1204},
                {"metric": "Watch time (hours)", "value": 389.5},
                {"metric": "likes", "value": "lots"},  # not a number: never guessed
            ],
            "measured_at": "2026-10-15T00:00:00Z",
        },
    )
    before = datetime.now(UTC).replace(microsecond=0)
    stats.run(ctx)
    after = datetime.now(UTC)
    kept = {r["body"]["metric"]: r["body"] for r in daemon.records.latest(space, "stat")}
    assert {m: b["value"] for m, b in kept.items()} == {
        "views": 12480.0,
        "subscribers": 1204.0,
        "watch_hours": 389.5,
    }
    times = {b["measured_at"] for b in kept.values()}
    assert len(times) == 1
    measured = datetime.fromisoformat(times.pop())
    assert before <= measured <= after  # the run's clock, not the page's 2026-10-15
    assert (ctx.found, ctx.kept) == (3, 3)
    assert_fenced(ctx)
    assert "Last updated 2026-10-15" in fenced_text(ctx.calls[0])


def test_no_analytics_address_is_skipped(daemon: Daemon) -> None:
    ctx = context(daemon, project(daemon), "stats")
    with pytest.raises(Skip) as skipped:
        stats.run(ctx)
    assert skipped.value.reason == "nothing_to_do"


def test_the_ceiling_ends_the_run(daemon: Daemon) -> None:
    ctx = context(daemon, project(daemon), "stats", PAGE)
    ctx.page(PAGE, TEXT)
    ctx.at_ceiling = True
    with pytest.raises(CeilingReached):
        stats.run(ctx)


def test_a_reading_number_is_read_plainly() -> None:
    from athena.routines.pages import number

    assert [number(v) for v in (7, "1,204", "1.2K", "3 m", "n/a", True, float("nan"))] == [
        7.0,
        1204.0,
        1200.0,
        3_000_000.0,
        None,
        None,
        None,
    ]
