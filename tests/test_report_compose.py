"""Composing the report (business Phase 1): one engine call through the validation door, stored as a new
version; a failure keeps the last good spec; pins are constraints; the shape trigger; and no number the
model wrote ever reaches the view."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from athena.app import Daemon
from athena.contracts import RECOMPOSE_MIN_S
from athena.errors import ApiError
from athena.report import compose
from report_kit import Fake, block, project, spec, stat, track, use_sql_records

QUEUE = block("q", "queue", "Tracks waiting", 8, binding={"kind": "track", "filter": {"verdict": None}})
CARDS = block("c", "cards", "For your signature", 4)
VIEWS = block(
    "v", "trend", "Views", 12, binding={"kind": "stat", "filter": {"metric": "views"}, "field": "value"}
)


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    d = use_sql_records(Daemon.open(None))
    yield d
    d.store.close()


def _versions(daemon: Daemon, sid: str) -> list[dict[str, Any]]:
    rows = daemon.store.query("SELECT spec, by FROM reports WHERE space_id = ? ORDER BY version", (sid,))
    assert all(r["by"] == "athena" for r in rows)
    return [json.loads(r["spec"]) for r in rows]


def test_a_good_spec_is_stored_as_a_new_version_with_one_ledger_row(daemon: Daemon) -> None:
    sid = project(daemon)
    track(daemon, sid, 1)
    seen = []
    daemon.events.publish = seen.append  # type: ignore[method-assign]
    fake = Fake([json.dumps(spec(QUEUE, CARDS)), "Here it is: " + json.dumps(spec(CARDS, QUEUE))])
    first = compose.compose(daemon, fake, sid)
    assert not first["default"] and [b["id"] for b in first["spec"]["blocks"]] == ["q", "c"]
    assert first["values"]["q"]["items"][0]["key"].endswith("/1") and "composed_at" in first
    second = compose.compose(daemon, fake, sid)
    assert [b["id"] for b in second["spec"]["blocks"]] == ["c", "q"]
    assert [[b["id"] for b in v["blocks"]] for v in _versions(daemon, sid)] == [["q", "c"], ["c", "q"]]
    rows = daemon.ledger.page(10, sid)["rows"]
    assert [(r["surface"], r["ok"]) for r in rows] == [("report", True), ("report", True)]
    assert seen == [{"type": "report", "space_id": sid}] * 2
    # She was told the vocabulary, the counts as context only, and the current spec.
    system, user = (str(m["content"]) for m in fake.asked[1])
    assert "Never write a number" in system and "- track: 1" in user and '"id": "q"' in user


def test_an_unknown_block_is_dropped_with_its_reason_and_counted(daemon: Daemon) -> None:
    sid = project(daemon)
    out = compose.compose(daemon, Fake([json.dumps(spec(QUEUE, block("g", "gauge", "Speed")))]), sid)
    assert [b["id"] for b in out["spec"]["blocks"]] == ["q"]
    assert out["dropped"] == 1 and out["reasons"] == ["“Speed”: 'gauge' is not a block the report can show."]


@pytest.mark.parametrize(
    "answer", ["I would rather not.", json.dumps({"blocks": "many"}), json.dumps(spec(block("g", "gauge")))]
)
def test_a_garbage_answer_keeps_the_last_good_spec(daemon: Daemon, answer: str) -> None:
    sid = project(daemon)
    compose.compose(daemon, Fake([json.dumps(spec(QUEUE, CARDS))]), sid)
    with pytest.raises(ApiError) as e:
        compose.compose(daemon, Fake([answer]), sid)
    assert e.value.error == "engine_unavailable" and "stands" in e.value.reason
    assert len(_versions(daemon, sid)) == 1
    assert [b["id"] for b in compose.view(daemon, sid)["spec"]["blocks"]] == ["q", "c"]


def test_an_engine_failure_keeps_the_last_good_spec_and_is_ledgered(daemon: Daemon) -> None:
    sid = project(daemon)
    with pytest.raises(ApiError) as e:
        compose.compose(daemon, Fake(fail="the line dropped"), sid)
    assert e.value.error == "engine_unavailable" and "the line dropped" in e.value.reason
    assert _versions(daemon, sid) == [] and compose.view(daemon, sid)["default"]
    assert [(r["surface"], r["ok"]) for r in daemon.ledger.page(10, sid)["rows"]] == [("report", False)]


def test_a_pinned_block_the_model_left_out_survives_by_id(daemon: Daemon) -> None:
    sid = project(daemon)
    compose.compose(daemon, Fake([json.dumps(spec(QUEUE, CARDS))]), sid)
    pinned = compose.set_pins(daemon, sid, {"pinned": ["q"]})
    assert pinned["pinned"] == ["q"]
    # She leaves the queue out and adds a views trend, and repeats the queue under a new id.
    again = block("q2", "queue", "Waiting", 6, binding={"kind": "track", "filter": {"verdict": None}})
    fake = Fake([json.dumps(spec(VIEWS, CARDS, again))])
    out = compose.compose(daemon, fake, sid)
    assert [b["id"] for b in out["spec"]["blocks"]] == ["q", "v", "c"]  # in its old place, no twin
    assert out["spec"]["blocks"][0] == compose.view(daemon, sid)["spec"]["blocks"][0]
    assert out["spec"]["blocks"][0]["title"] == "Tracks waiting" and out["pinned"] == ["q"]
    # The pin reached her as a constraint.
    user = str(fake.asked[0][1]["content"])
    assert "Pinned by the owner (keep each, unchanged, with its id): `q`" in user and '"pinned": true' in user
    # A changed pinned block is put back verbatim.
    changed = block("q", "queue", "Other title", 12, binding={"kind": "track", "filter": {"verdict": None}})
    out = compose.compose(daemon, Fake([json.dumps(spec(changed, CARDS))]), sid)
    assert out["spec"]["blocks"][0]["title"] == "Tracks waiting" and out["spec"]["blocks"][0]["span"] == 8


def test_pins_name_blocks_on_the_report_and_replace_the_set(daemon: Daemon) -> None:
    sid = project(daemon)
    assert compose.set_pins(daemon, sid, {"pinned": ["d-queue", "d-cards"]})["pinned"] == [
        "d-queue",
        "d-cards",
    ]
    assert compose.set_pins(daemon, sid, {"pinned": ["d-cards"]})["pinned"] == ["d-cards"]
    with pytest.raises(ApiError) as e:
        compose.set_pins(daemon, sid, {"pinned": ["nope"]})
    assert e.value.error == "bad_request" and "nope" in e.value.reason


def test_no_number_the_model_wrote_reaches_the_view(daemon: Daemon) -> None:
    sid = project(daemon)
    track(daemon, sid, 1)
    stat(daemon, sid, "views", 7, "2026-10-01T00:00:00Z")
    stat(daemon, sid, "views", 11, "2026-10-02T00:00:00Z")
    answer = spec(
        block("s", "stat", "4242 tracks found", binding={"kind": "track"}),  # a figure in the title
        block(
            "t", "stat", "Tracks found", binding={"kind": "track"}, config={"value": 9191}
        ),  # a figure as config
        block("u", "stat", "Tracks", binding={"kind": "track", "agg": "count"}, count=5353, value=5353),
        block(
            "v",
            "stat",
            "Views",
            binding={"kind": "stat", "filter": {"metric": "views"}, "agg": "sum", "field": "value"},
        ),
        block(
            "p",
            "pipeline",
            "Funnel",
            config={"stages": [{"label": "Top 6464", "binding": {"kind": "track"}}]},
        ),
        title="8282 views and counting",
        callout="We passed 7373 views.",
    )
    out = compose.compose(daemon, Fake([json.dumps(answer)]), sid)
    text = json.dumps(out)
    for planted in ("4242", "9191", "5353", "6464", "8282", "7373"):
        assert planted not in text, planted
    assert out["values"] == {"u": {"count": 1}, "v": {"value": 18.0}}
    # Every figure in the values is one the records give: a count of one track, views seven plus eleven.
    figures = {float(n) for n in re.findall(r"\d+(?:\.\d+)?", json.dumps(out["values"]))}
    assert figures == {1.0, 18.0}
    assert out["dropped"] == 4  # the title, the config, the stage label, and the callout


def test_the_view_of_a_project_with_no_composition_is_the_default(daemon: Daemon) -> None:
    sid = project(daemon)
    out = compose.view(daemon, sid)
    assert out["default"] and out["dropped"] == 0 and "composed_at" not in out
    assert out["spec"]["title"] == "Night Drive Music" and set(out["values"]) == {
        b["id"] for b in out["spec"]["blocks"]
    }
    empty = project(daemon, kinds=[], name="Nothing kept")
    with pytest.raises(ApiError) as e:
        compose.view(daemon, empty)
    assert e.value.error == "bad_request" and e.value.reason == "this project keeps no records"


# --- the shape trigger ----------------------------------------------------------------------------


@pytest.fixture
def inline(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Runs a triggered composition on the caller's thread and notes each one."""
    started: list[str] = []

    def run(fn: Callable[[], None]) -> None:
        started.append("composed")
        fn()

    monkeypatch.setattr(compose, "SPAWN", run)
    return started


def test_the_shape_trigger_fires_on_zero_to_one_and_one_to_zero_only(
    daemon: Daemon, inline: list[str]
) -> None:
    sid = project(daemon)
    fake = Fake([json.dumps(spec(QUEUE, CARDS))] * 3)
    assert not compose.on_records_changed(daemon, lambda: fake, sid, "track", 1, 2)
    assert not compose.on_records_changed(daemon, lambda: fake, sid, "track", 2, 1)
    assert not compose.on_records_changed(daemon, lambda: fake, sid, "track", 0, 0)
    assert compose.on_records_changed(daemon, lambda: fake, sid, "track", 0, 1)
    assert inline == ["composed"] and len(_versions(daemon, sid)) == 1
    # Within RECOMPOSE_MIN_S of that composition, a second shape change waits.
    assert not compose.on_records_changed(daemon, lambda: fake, sid, "creator", 1, 0)
    # Once the last composition is older than that, it fires again.
    daemon.store.run("UPDATE reports SET composed_at = '2020-01-01T00:00:00Z' WHERE space_id = ?", (sid,))
    compose._attempted.clear()
    assert compose.on_records_changed(daemon, lambda: fake, sid, "creator", 1, 0)
    assert len(_versions(daemon, sid)) == 2 and RECOMPOSE_MIN_S > 0


def test_a_failed_triggered_composition_never_raises_and_is_not_retried_at_once(
    daemon: Daemon, inline: list[str]
) -> None:
    sid = project(daemon)
    assert compose.on_records_changed(daemon, lambda: Fake(fail="down"), sid, "track", 0, 1)
    assert _versions(daemon, sid) == []
    assert not compose.on_records_changed(daemon, lambda: Fake(fail="down"), sid, "track", 1, 0)


def test_the_trigger_runs_off_the_callers_thread(daemon: Daemon) -> None:
    import threading

    sid = project(daemon)
    done = threading.Event()
    where: list[str] = []

    class Slow(Fake):
        def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[Any]:
            where.append(threading.current_thread().name)
            yield from super().complete(messages, tools)
            done.set()

    assert compose.on_records_changed(daemon, lambda: Slow([json.dumps(spec(CARDS))]), sid, "track", 0, 1)
    assert done.wait(5) and where == ["report-compose"]
    for t in threading.enumerate():
        if t.name == "report-compose":
            t.join(5)
    assert len(_versions(daemon, sid)) == 1
