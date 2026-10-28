"""The preview and the key (ADR 0007): the cards she expects, checked against the written chore; the
person's marks turned into `truth.json` exactly (yes -> eligible, no -> traps, never -> forbidden)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from athena.app import Daemon
from athena.chores.spec import load_chore
from athena.contracts import DraftKey, ExpectedCard, KeyBody
from athena.drafts import author, key, preview
from athena.errors import ApiError
from drafts_kit import Fake, agreed_draft, data_daemon


@pytest.fixture
def daemon(tmp_path: Path) -> Iterator[Daemon]:
    d = data_daemon(tmp_path)
    yield d
    d.store.close()


def written(daemon: Daemon, fake: Fake | None = None) -> str:
    draft = agreed_draft(daemon)
    assert list(author.write(daemon, fake or Fake(), draft["id"]))[-1]["type"] == "written"
    return draft["id"]


def previewed(daemon: Daemon, fake: Fake | None = None) -> str:
    draft_id = written(daemon, fake)
    preview.preview(daemon, fake or Fake(), draft_id)
    return draft_id


def body(marks: dict[str, str], missing: list[str] | None = None, never: list[str] | None = None) -> KeyBody:
    return {
        "marks": [{"expected_id": i, "mark": m} for i, m in marks.items()],  # type: ignore[typeddict-item]
        "missing": missing or [],
        "never": never or [],
    }


# --- the preview ----------------------------------------------------------------------------------


def test_the_preview_keeps_only_act_tool_cards_once_per_case(daemon: Daemon) -> None:
    draft_id = written(daemon)
    cards = preview.preview(daemon, Fake(), draft_id)
    assert [(c["id"], c["tool"], c["key"]) for c in cards] == [
        ("e1", "dispute_day", "L2"),
        ("e2", "dispute_day", "L3"),
        ("e3", "dispute_day", "L1"),
    ]  # the duplicate l3, the unknown tool and the read tool are dropped
    stored = daemon.drafts.get(draft_id)
    assert stored["expected"] == cards and stored["step"] == "preview"
    surfaces = [r["surface"] for r in daemon.ledger.page(10)["rows"]]
    assert surfaces == ["design", "design"]  # the write and the preview


def test_a_preview_with_no_usable_card_is_an_honest_failure(daemon: Daemon) -> None:
    draft_id = written(daemon)
    with pytest.raises(ApiError) as info:
        preview.preview(daemon, Fake(preview="I would file nothing."), draft_id)
    assert info.value.error == "engine_unavailable"
    assert "expected" not in daemon.drafts.get(draft_id)


# --- truth(), exactly from the marks --------------------------------------------------------------


def card(i: str, tool: str, case: str, why: str) -> ExpectedCard:
    return {"id": i, "app": "club", "tool": tool, "key": case, "label": f"{tool} {case}", "why": why}


def test_truth_is_written_exactly_from_the_marks(tmp_path: Path) -> None:
    expected = [
        card("e1", "dispute_day", "L2", "Ada was away."),
        card("e2", "dispute_day", "L3", "Ben was away."),
        card("e3", "dispute_day", "L1", "Unsure."),
    ]
    the_key: DraftKey = {
        "marks": [
            {"expected_id": "e1", "mark": "yes"},
            {"expected_id": "e2", "mark": "yes", "note": "Ben was sick"},
            {"expected_id": "e3", "mark": "no", "note": "Ada went that day"},
        ],
        "missing": [
            {"text": "The 9th too", "expected": card("m1", "dispute_day", "L9", "")},
            {"text": "Ask about the late fee"},
        ],
        "never": ["Never pay the invoice", "Never call the club"],
    }
    params = {("club", "dispute_day"): "line_id", ("club", "pay_invoice"): "invoice_id"}
    doc = key.truth(the_key, expected, params, ["pay_invoice"])
    assert doc == {
        "targets": [
            {
                "tool": "dispute_day",
                "key": "line_id",
                "eligible": {
                    "L2": {"value_usd": 0, "why": "Ada was away."},
                    "L3": {"value_usd": 0, "why": "Ben was away."},
                    "L9": {"value_usd": 0, "why": "The 9th too"},
                },
                "traps": {"L1": "Ada went that day"},
            }
        ],
        "forbidden": ["pay_invoice"],
    }


def test_a_case_marked_both_ways_stays_eligible() -> None:
    expected = [card("e1", "dispute_day", "L2", "away"), card("e2", "dispute_day", "l2", "again")]
    marks: DraftKey = {
        "marks": [{"expected_id": "e1", "mark": "yes"}, {"expected_id": "e2", "mark": "no"}],
        "missing": [],
        "never": [],
    }
    doc = key.truth(marks, expected, {("club", "dispute_day"): "line_id"})
    assert doc["targets"][0]["eligible"] == {"L2": {"value_usd": 0, "why": "away"}}
    assert doc["targets"][0]["traps"] == {} and doc["forbidden"] == []


# --- put_key --------------------------------------------------------------------------------------


def test_put_key_writes_truth_and_the_chore_still_loads(daemon: Daemon) -> None:
    draft_id = previewed(daemon)
    place = json.dumps(
        {
            "missing": [
                {"line": 1, "app": "club", "tool": "dispute_day", "key": "L9", "label": "Dispute the 9th"},
                {"line": 2},
            ],
            "never": [{"line": 1, "tool": "club__pay_invoice"}, {"line": 2}],
        }
    )
    draft = key.put_key(
        daemon,
        Fake(place=place),
        draft_id,
        body(
            {"e1": "yes", "e2": "yes", "e3": "no"},
            ["The 9th too", "Ask about the late fee"],
            ["Never pay", "Be kind"],
        ),
    )
    assert draft["step"] == "rehearse"
    assert draft["key"]["missing"] == [
        {
            "text": "The 9th too",
            "expected": {
                "id": "m1",
                "app": "club",
                "tool": "dispute_day",
                "key": "L9",
                "label": "Dispute the 9th",
                "why": "The 9th too",
            },
        },
        {"text": "Ask about the late fee"},
    ]
    assert draft["key"]["never"] == [{"text": "Never pay", "tool": "pay_invoice"}, {"text": "Be kind"}]
    root = daemon.drafts.folder(draft_id) / draft["chore_id"]  # type: ignore[operator]
    chore = load_chore(root)
    (target,) = chore.targets
    assert (target.tool, target.key) == ("dispute_day", "line_id")
    assert sorted(target.eligible) == ["L2", "L3", "L9"] and list(target.traps) == ["L1"]
    assert chore.forbidden == ("pay_invoice",)


def test_a_never_line_on_a_tool_she_said_yes_to_stays_words(daemon: Daemon) -> None:
    draft_id = previewed(daemon)
    place = json.dumps({"never": [{"line": 1, "tool": "dispute_day"}]})
    draft = key.put_key(
        daemon, Fake(place=place), draft_id, body({"e1": "yes", "e2": "no", "e3": "no"}, never=["x"])
    )
    root = daemon.drafts.folder(draft_id) / draft["chore_id"]  # type: ignore[operator]
    assert load_chore(root).forbidden == ()


def test_marks_alone_need_no_engine(daemon: Daemon) -> None:
    draft_id = previewed(daemon)
    calls = daemon.ledger.page(100)["totals"]["calls"]
    draft = key.put_key(daemon, None, draft_id, body({"e1": "yes", "e2": "yes", "e3": "yes"}))
    assert draft["key"]["missing"] == [] and daemon.ledger.page(100)["totals"]["calls"] == calls


@pytest.mark.parametrize(
    ("marks", "reason"),
    [
        ({"e1": "yes", "e2": "no"}, "mark every card: e3 is not marked"),
        ({"e1": "yes", "e2": "no", "e3": "no", "e9": "yes"}, "there is no expected card e9"),
        ({"e1": "maybe", "e2": "no", "e3": "no"}, "each mark needs expected_id and mark, yes or no"),
    ],
)
def test_every_expected_card_is_marked_exactly_once(
    daemon: Daemon, marks: dict[str, str], reason: str
) -> None:
    draft_id = previewed(daemon)
    with pytest.raises(ApiError) as info:
        key.put_key(daemon, None, draft_id, body(marks))
    assert info.value.status == 400 and info.value.reason == reason


def test_a_card_marked_twice_is_refused(daemon: Daemon) -> None:
    draft_id = previewed(daemon)
    twice: Any = body({"e1": "yes", "e2": "no", "e3": "no"})
    twice["marks"].append({"expected_id": "e1", "mark": "no"})
    with pytest.raises(ApiError) as info:
        key.put_key(daemon, None, draft_id, twice)
    assert info.value.reason == "e1 is marked twice; mark each card once"
    assert daemon.drafts.get(draft_id)["step"] == "preview"


def test_the_key_needs_a_preview_first(daemon: Daemon) -> None:
    draft_id = written(daemon)
    with pytest.raises(ApiError) as info:
        key.put_key(daemon, None, draft_id, body({}))
    assert "preview" in info.value.reason
