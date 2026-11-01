"""Every number on the report is computed from records (business Phase 1): each aggregation, the queue's
absent-field filter, pipeline stages, a series oldest first, and absent versus a real zero."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from athena.app import Daemon
from athena.contracts import Block
from athena.report.compute import value
from report_kit import project, put, stat, track, use_sql_records


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    d = use_sql_records(Daemon.open(None))
    yield d
    d.store.close()


def _b(kind: str, binding: dict[str, Any] | None = None, **config: Any) -> Block:
    out: dict[str, Any] = {"id": "b", "kind": kind, "title": "t", "span": 6, "config": config}
    if binding is not None:
        out["binding"] = binding
    return out  # type: ignore[return-value]


def test_count_reads_the_latest_revision_of_each_key(daemon: Daemon) -> None:
    sid = project(daemon)
    a = track(daemon, sid, 1)
    track(daemon, sid, 2)
    track(daemon, sid, 3, verdict="pass")
    # A verdict on track one is a new revision: still one key, now judged.
    put(
        daemon,
        sid,
        "track",
        a,
        {"url": a, "title": "Song 1", "creator_key": "c1", "found_at": "x", "verdict": "keep"},
    )
    v = value(daemon.records, sid, _b("stat", {"kind": "track", "agg": "count"}), [])
    assert v == {"count": 3}
    kept = value(daemon.records, sid, _b("stat", {"kind": "track", "filter": {"verdict": "keep"}}), [])
    assert kept == {"count": 1}


def test_an_empty_count_is_a_real_zero_and_an_empty_sum_or_last_is_absent(daemon: Daemon) -> None:
    sid = project(daemon)
    assert value(daemon.records, sid, _b("stat", {"kind": "creator", "agg": "count"}), []) == {"count": 0}
    views = {"kind": "stat", "filter": {"metric": "views"}, "field": "value"}
    assert value(daemon.records, sid, _b("stat", {**views, "agg": "sum"}), []) == {}
    assert value(daemon.records, sid, _b("stat", {**views, "agg": "last"}), []) == {}
    assert value(daemon.records, sid, _b("trend", {**views, "agg": "series"}), []) == {"series": []}


def test_sum_last_and_series_over_stats(daemon: Daemon) -> None:
    sid = project(daemon)
    # Written out of order on purpose: a reading's time is `measured_at`, not when it was written.
    stat(daemon, sid, "views", 30, "2026-10-03T00:00:00Z")
    stat(daemon, sid, "views", 10, "2026-10-01T00:00:00Z")
    stat(daemon, sid, "views", 20, "2026-10-02T00:00:00Z")
    stat(daemon, sid, "likes", 999, "2026-10-04T00:00:00Z")  # another metric is not mixed in
    views = {"kind": "stat", "filter": {"metric": "views"}, "field": "value"}
    assert value(daemon.records, sid, _b("stat", {**views, "agg": "sum"}), []) == {"value": 60.0}
    assert value(daemon.records, sid, _b("stat", {**views, "agg": "last"}), []) == {"value": 30.0}
    series = value(daemon.records, sid, _b("trend", {**views, "agg": "series"}), [])["series"]
    assert series == [
        {"t": "2026-10-01T00:00:00Z", "v": 10.0},
        {"t": "2026-10-02T00:00:00Z", "v": 20.0},
        {"t": "2026-10-03T00:00:00Z", "v": 30.0},
    ]


def test_a_series_keeps_the_latest_thirty_points(daemon: Daemon) -> None:
    sid = project(daemon)
    for day in range(1, 36):
        stat(
            daemon,
            sid,
            "views",
            day,
            f"2026-10-{day:02d}T00:00:00Z" if day <= 31 else f"2026-11-{day - 31:02d}T00:00:00Z",
        )
    b = _b("trend", {"kind": "stat", "filter": {"metric": "views"}, "agg": "series", "field": "value"})
    series = value(daemon.records, sid, b, [])["series"]
    assert len(series) == 30 and series[0]["v"] == 6.0 and series[-1]["v"] == 35.0


def test_the_queue_holds_the_tracks_with_no_verdict_field(daemon: Daemon) -> None:
    sid = project(daemon)
    waiting = [track(daemon, sid, 1), track(daemon, sid, 2)]
    track(daemon, sid, 3, verdict="later")
    q = _b("queue", {"kind": "track", "filter": {"verdict": None}}, limit=10)
    items = value(daemon.records, sid, q, [])["items"]
    assert sorted(i["key"] for i in items) == sorted(waiting)
    assert all("verdict" not in i["body"] for i in items)
    assert [i["key"] for i in items] == [waiting[1], waiting[0]]  # newest first
    assert (
        len(
            value(
                daemon.records, sid, _b("queue", {"kind": "track", "filter": {"verdict": None}}, limit=1), []
            )["items"]
        )
        == 1
    )


def test_a_thread_block_is_latest_conversation_first(daemon: Daemon) -> None:
    sid = project(daemon)
    for who, at in (
        ("a", "2026-10-02T00:00:00Z"),
        ("b", "2026-10-05T00:00:00Z"),
        ("c", "2026-10-01T00:00:00Z"),
    ):
        put(daemon, sid, "thread", who, {"creator_key": who, "channel": "mail_web", "last_at": at})
    items = value(daemon.records, sid, _b("thread", {"kind": "thread"}), [])["items"]
    assert [i["key"] for i in items] == ["b", "a", "c"]


def test_pipeline_stages_count_each_stage(daemon: Daemon) -> None:
    sid = project(daemon)
    for who, state in (("a", "proposed"), ("b", "proposed"), ("c", "agreed")):
        put(daemon, sid, "agreement", who, {"creator_key": who, "state": state, "thread_key": who})
    put(
        daemon,
        sid,
        "release",
        "t1",
        {
            "track_key": "t1",
            "title": "x",
            "track_url": "u",
            "creator_channel_url": "c",
            "genre": "g",
            "credits": "c",
        },
    )
    stages = [
        {
            "label": "Proposed",
            "binding": {"kind": "agreement", "filter": {"state": "proposed"}, "agg": "count"},
        },
        {"label": "Agreed", "binding": {"kind": "agreement", "filter": {"state": "agreed"}, "agg": "count"}},
        {"label": "Rendered", "binding": {"kind": "render", "filter": {"state": "rendered"}, "agg": "count"}},
        {"label": "Released", "binding": {"kind": "release", "agg": "count"}},
    ]
    v = value(daemon.records, sid, _b("pipeline", stages=stages), [])
    assert v == {
        "stages": [
            {"label": "Proposed", "count": 2},
            {"label": "Agreed", "count": 1},
            {"label": "Rendered", "count": 0},
            {"label": "Released", "count": 1},
        ]
    }


def test_cards_are_the_projects_waiting_cards(daemon: Daemon) -> None:
    sid, other = project(daemon), project(daemon, name="Other")
    mine = daemon.gate.file(sid, "remember", {"text": "x"}, "Remember x")
    daemon.gate.file(other, "remember", {"text": "y"}, "Remember y")
    cards = daemon.gate.list("waiting")
    assert value(daemon.records, sid, _b("cards"), cards) == {"cards": [mine]}
    assert value(daemon.records, sid, _b("callout"), cards) == {}


def test_records_of_another_project_never_count(daemon: Daemon) -> None:
    sid, other = project(daemon), project(daemon, name="Other")
    track(daemon, other, 1)
    assert value(daemon.records, sid, _b("stat", {"kind": "track", "agg": "count"}), []) == {"count": 0}
