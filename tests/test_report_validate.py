"""The validation door (business Phase 1): what survives, why each block was dropped, in plain words."""

from __future__ import annotations

from typing import Any

from athena.contracts import BLOCKS_MAX, CALLOUT_MAX, REPORT_TITLE_MAX, VOCAB
from athena.report.default import default_spec
from athena.report.validate import check, validate
from athena.report.vocab import BLOCKS, composer_docs
from report_kit import MUSIC, block, spec

QUEUE = block("q", "queue", "Tracks waiting", binding={"kind": "track", "filter": {"verdict": None}})
CARDS = block("c", "cards", "Waiting for you")


def _one(b: dict[str, Any], kinds: list[Any] = MUSIC) -> list[str]:
    """The reasons when `b` is checked beside a block that always survives."""
    checked = check(spec(CARDS, b), kinds)
    assert [x["id"] for x in checked.spec["blocks"]] == ["c"]
    assert len(checked.reasons) == 1
    return checked.reasons


def test_a_good_spec_passes_whole_and_is_stamped() -> None:
    raw = spec(
        QUEUE,
        block(
            "v", "trend", "Views", binding={"kind": "stat", "filter": {"metric": "views"}, "field": "value"}
        ),
        block("s", "stat", "Creators followed", binding={"kind": "creator", "filter": {"followed": True}}),
        block("f", "list", "Latest", binding={"kind": "track"}, config={"fields": ["title"], "limit": 5}),
        CARDS,
        callout="Two new creators answered this week.",
    )
    raw["vocab"] = 0  # an older stamp is restamped, not refused
    out, reasons = validate(raw, MUSIC)
    assert reasons == [] and out["vocab"] == VOCAB and len(out["blocks"]) == 5
    assert out["blocks"][1]["binding"]["agg"] == "series" and out["blocks"][2]["binding"]["agg"] == "count"
    # The callout above is "Two", a word: words pass, digits do not.
    assert out["callout"] == "Two new creators answered this week."


def test_each_drop_has_its_reason() -> None:
    assert "is not a block the report can show" in _one(block("x", "gauge"))[0]
    assert "not tied to any records" in _one(block("x", "stat"))[0]
    assert (
        "keeps no release records"
        in _one(block("x", "stat", binding={"kind": "release"}), kinds=["track"])[0]
    )
    assert "Athena does not keep" in _one(block("x", "stat", binding={"kind": "invoice"}))[0]
    assert "1 to 12" in _one(block("x", "cards", span=13))[0]
    assert "1 to 12" in _one(block("x", "cards", span=0))[0]
    assert "has no id" in _one({"kind": "cards", "title": "x", "span": 3, "config": {}})[0]


def test_config_contracts() -> None:
    # A stat that sums needs a numeric field, and over stats one metric.
    assert "which field" in _one(block("x", "stat", binding={"kind": "stat", "agg": "sum"}))[0]
    assert (
        "not a figure"
        in _one(block("x", "stat", binding={"kind": "track", "agg": "sum", "field": "title"}))[0]
    )
    assert "one metric" in _one(block("x", "trend", binding={"kind": "stat", "field": "value"}))[0]
    assert (
        "draws a series"
        in _one(block("x", "trend", binding={"kind": "stat", "agg": "count", "filter": {"metric": "v"}}))[0]
    )
    assert "holds tracks" in _one(block("x", "queue", binding={"kind": "creator"}))[0]
    assert (
        "no verdict yet"
        in _one(block("x", "queue", binding={"kind": "track", "filter": {"verdict": "keep"}}))[0]
    )
    assert (
        "1 to 3 fields"
        in _one(block("x", "list", binding={"kind": "track"}, config={"fields": ["a", "b", "c", "d"]}))[0]
    )
    assert (
        "show 11 items"
        in _one(block("x", "list", binding={"kind": "track"}, config={"fields": ["title"], "limit": 11}))[0]
    )
    assert "takes no `size`" in _one(block("x", "cards", config={"size": "big"}))[0]
    assert (
        "each pipeline stage is a count"
        in _one(
            block(
                "x",
                "pipeline",
                config={"stages": [{"label": "Out", "binding": {"kind": "release", "agg": "sum"}}]},
            )
        )[0]
    )
    assert "1 to 6 stages" in _one(block("x", "pipeline", config={"stages": []}))[0]
    # A queue with no filter is given its one filter.
    out, _ = validate(spec(block("q", "queue", binding={"kind": "track"})), MUSIC)
    assert out["blocks"][0]["binding"] == {"kind": "track", "filter": {"verdict": None}}


def test_a_digit_in_a_title_label_unit_or_callout_is_refused() -> None:
    assert "has a number in it" in _one(block("x", "cards", "3 cards waiting"))[0]
    assert (
        "has a number in it"
        in _one(block("x", "stat", "Views", binding={"kind": "creator"}, config={"unit": "x1000"}))[0]
    )
    assert (
        "has a number in it"
        in _one(
            block("x", "pipeline", config={"stages": [{"label": "Top 10", "binding": {"kind": "release"}}]})
        )[0]
    )
    out, reasons = validate(spec(CARDS, callout="You gained 1200 views."), MUSIC)
    assert "callout" not in out and reasons == [
        "The callout had a number in it, so it is not shown (numbers on the report come from records only)."
    ]
    # A callout block with nothing to show goes too, with its own reason.
    checked = check(spec(CARDS, block("co", "callout", "Note"), callout="Up 40%"), MUSIC)
    assert [b["id"] for b in checked.spec["blocks"]] == ["c"] and len(checked.reasons) == 2
    # The report's title: a figure in the model's title gives way to the project's own name.
    assert check(spec(CARDS, title="12 tracks to judge"), MUSIC, "Night Drive").spec["title"] == "Night Drive"


def test_over_long_title_and_callout_are_cut_not_dropped() -> None:
    out, reasons = validate(spec(CARDS, title="t" * 200, callout="w " * 400), MUSIC)
    assert reasons == [] and len(out["title"]) == REPORT_TITLE_MAX and len(out["callout"]) <= CALLOUT_MAX


def test_more_than_blocks_max_drops_the_tail() -> None:
    blocks = [block(f"c{i}", "cards", "Waiting", span=1) for i in range(BLOCKS_MAX + 2)]
    out, reasons = validate(spec(*blocks), MUSIC)
    assert [b["id"] for b in out["blocks"]] == [f"c{i}" for i in range(BLOCKS_MAX)]
    assert len(reasons) == 2 and all(f"at most {BLOCKS_MAX} blocks" in r for r in reasons)


def test_a_duplicate_id_keeps_the_first() -> None:
    checked = check(spec(CARDS, block("c", "queue", "Again", binding={"kind": "track"})), MUSIC)
    assert [b["kind"] for b in checked.spec["blocks"]] == ["cards"]
    assert checked.reasons == ["“Again”: another block already has the id “c”; the first was kept."]


def test_nothing_left_is_the_default_spec_and_says_so() -> None:
    checked = check(spec(block("x", "gauge")), MUSIC, "Night Drive")
    assert (
        checked.default and checked.spec == default_spec("Night Drive", MUSIC) and len(checked.reasons) == 1
    )
    rejected = check("not a spec", MUSIC, "Night Drive")
    assert rejected.default and rejected.rejected and rejected.reasons == []


def test_the_default_spec_passes_its_own_door_for_every_kind_set() -> None:
    for kinds in (MUSIC, ["track"], ["stat", "file"], [], ["release", "agreement"]):
        d = default_spec("P", kinds)  # type: ignore[arg-type]
        checked = check(d, kinds, "P")  # type: ignore[arg-type]
        assert checked.reasons == [] and not checked.default and checked.spec == d, kinds
        bound = {b["binding"]["kind"] for b in d["blocks"] if "binding" in b}
        assert bound <= set(kinds)
    music = default_spec("P", MUSIC)
    assert [b["id"] for b in music["blocks"]][:4] == ["d-queue", "d-creators", "d-pipeline", "d-views"]
    stages = music["blocks"][2]["config"]["stages"]
    assert [s["label"] for s in stages] == ["Proposed", "Agreed", "Rendered", "Released"]


def test_the_composer_docs_come_from_the_registry() -> None:
    docs = composer_docs(MUSIC)
    for kind, entry in BLOCKS.items():
        assert f"- `{kind}`: {entry['description']}" in docs
    assert f"Block vocabulary version {VOCAB}" in docs and "Never write a number" in docs
    assert "keep the id of every block" in docs and "`pinned`" in docs
    assert "- `track`" in docs and "- `file`" not in docs  # only the kinds the project keeps
