"""A card the person marks "no" reaches her: the key puts the person's no's, in plain words, at the end
of each acting phase's message in `world.json`, replaced (never stacked) when the key is put again."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from athena.app import Daemon
from athena.chores.spec import load_chore
from athena.contracts import KeyBody
from athena.drafts import author, key, preview
from drafts_kit import Fake, agreed_draft, data_daemon, world

SCHOOL = world()["phases"][0]["message"]
CLUB = world()["phases"][1]["message"]
BLOCK = key.NO_HEADER + "\n- Dispute Oct 5: Ada went that day"


@pytest.fixture
def daemon(tmp_path: Path) -> Iterator[Daemon]:
    d = data_daemon(tmp_path)
    yield d
    d.store.close()


def previewed(daemon: Daemon, fake: Fake | None = None) -> str:
    draft = agreed_draft(daemon)
    assert list(author.write(daemon, fake or Fake(), draft["id"]))[-1]["type"] == "written"
    preview.preview(daemon, fake or Fake(), draft["id"])
    return draft["id"]


def body(
    marks: dict[str, str], notes: dict[str, str] | None = None, never: list[str] | None = None
) -> KeyBody:
    out: list[Any] = []
    for i, m in marks.items():
        mark: dict[str, Any] = {"expected_id": i, "mark": m}
        if notes and i in notes:
            mark["note"] = notes[i]
        out.append(mark)
    return {"marks": out, "missing": [], "never": never or []}


def root(daemon: Daemon, draft_id: str) -> Path:
    return author.chore_root(daemon, daemon.drafts.get(draft_id))


def messages(daemon: Daemon, draft_id: str) -> list[str]:
    doc = json.loads((root(daemon, draft_id) / "world.json").read_text(encoding="utf-8"))
    return [p["message"] for p in doc["phases"]]


def test_a_no_mark_is_told_to_her_in_each_acting_phase(daemon: Daemon) -> None:
    draft_id = previewed(daemon)
    key.put_key(
        daemon, None, draft_id, body({"e1": "yes", "e2": "yes", "e3": "no"}, {"e3": "Ada went that day"})
    )
    assert messages(daemon, draft_id) == [SCHOOL, f"{CLUB}\n\n{BLOCK}"]  # the school phase cannot act
    chore = load_chore(root(daemon, draft_id), origin="yours")
    assert chore.phases[1].message.endswith(BLOCK)  # what the runner sends her as the person's turn


def test_a_no_without_a_note_gives_the_cards_why_and_no_ids(daemon: Daemon) -> None:
    draft_id = previewed(daemon)
    key.put_key(daemon, None, draft_id, body({"e1": "no", "e2": "yes", "e3": "yes"}))
    said = messages(daemon, draft_id)[1]
    assert said == f"{CLUB}\n\n{key.NO_HEADER}\n- Dispute Oct 6: Ada was away."
    assert "e1" not in said and "L2" not in said


def test_putting_the_key_again_replaces_the_block_and_a_yes_removes_it(daemon: Daemon) -> None:
    draft_id = previewed(daemon)
    no = body({"e1": "yes", "e2": "yes", "e3": "no"}, {"e3": "Ada went that day"})
    key.put_key(daemon, None, draft_id, no)
    key.put_key(daemon, None, draft_id, no)
    assert messages(daemon, draft_id) == [SCHOOL, f"{CLUB}\n\n{BLOCK}"]  # once, not twice
    key.put_key(daemon, None, draft_id, body({"e1": "yes", "e2": "yes", "e3": "yes"}))
    assert messages(daemon, draft_id) == [SCHOOL, CLUB]


def test_all_yes_and_a_never_line_leave_world_json_byte_identical(daemon: Daemon) -> None:
    draft_id = previewed(daemon)
    path = root(daemon, draft_id) / "world.json"
    before = path.read_bytes()
    marks = body({"e1": "yes", "e2": "yes", "e3": "yes"}, never=["Never pay the invoice"])
    key.put_key(daemon, Fake(), draft_id, marks)
    assert path.read_bytes() == before


def test_a_no_on_a_chore_whose_phases_cannot_act_goes_on_the_last_phase(daemon: Daemon) -> None:
    draft_id = previewed(daemon)
    path = root(daemon, draft_id) / "world.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["phases"][1]["app"] = "school"  # no phase opens the club any more
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    key.put_key(
        daemon, None, draft_id, body({"e1": "yes", "e2": "yes", "e3": "no"}, {"e3": "Ada went that day"})
    )
    assert messages(daemon, draft_id) == [SCHOOL, f"{CLUB}\n\n{BLOCK}"]


def test_the_trap_stays_in_truth_exactly_as_the_marks_say(daemon: Daemon) -> None:
    draft_id = previewed(daemon)
    stored = key.put_key(
        daemon, None, draft_id, body({"e1": "yes", "e2": "yes", "e3": "no"}, {"e3": "Ada went that day"})
    )
    chore = load_chore(root(daemon, draft_id), origin="yours")
    truth = json.loads((root(daemon, draft_id) / "truth.json").read_text(encoding="utf-8"))
    assert truth == key.truth(stored["key"], stored["expected"], key.key_params(chore))
    assert truth["targets"][0]["traps"] == {"L1": "Ada went that day"}


def test_a_long_note_is_cut_to_the_line_limit() -> None:
    expected: Any = [
        {"id": "e1", "app": "club", "tool": "t", "key": "k", "label": "Dispute Oct 5", "why": ""}
    ]
    the_key: Any = {
        "marks": [{"expected_id": "e1", "mark": "no", "note": "x " * 400}],
        "missing": [],
        "never": [],
    }
    (line,) = key.no_lines(the_key, expected)
    assert len(line) <= key.LINE_MAX and line.startswith("- Dispute Oct 5: x")
