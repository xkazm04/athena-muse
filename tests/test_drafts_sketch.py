"""Sketch ops and the rubric: pure functions, places never move, coverage from the sketch alone."""

from __future__ import annotations

from typing import Any, cast

import pytest

from athena.contracts import LABEL_MAX, SKETCH_NODES_MAX, Sketch, SketchOp
from athena.drafts.rubric import agreed, coverage, open_slots
from athena.drafts.sketch import Said, SketchError, apply, confirm, drop, empty

#: What the person typed in these tests: a quote from it inks a node whose words are the quote's.
SAID = Said(["Each month I check the bill against the days they went"])


def add(
    node_id: str, slot: str = "need", kind: str = "step", label: str = "Check the bill", **more: Any
) -> SketchOp:
    node = {"id": node_id, "kind": kind, "slot": slot, "label": label, "origin": "athena", "confirmed": False}
    return cast("SketchOp", {"op": "add", "node": {**node, **more}})


def ink(node_id: str, label: str = "Check the bill", **more: Any) -> SketchOp:
    """An add the sketch draws as the person's own (with SAID): its words are their quote."""
    return add(node_id, label=label, quote="I check the bill against", **more)


def link(a: str, b: str) -> SketchOp:
    return cast("SketchOp", {"op": "link", "edge": {"from": a, "to": b}})


def three() -> Sketch:
    sketch, _ = apply(empty(), [add("a"), add("b", "apps", "app"), add("c", "hand", "gate"), link("a", "b")])
    return sketch


def test_add_change_remove_link_answer_the_ops_as_applied() -> None:
    sketch, ops = apply(
        empty(), [add("a", label="  Check   the bill "), add("b", "apps", "app"), link("a", "b")]
    )
    assert [n["id"] for n in sketch["nodes"]] == ["a", "b"]
    assert ops[0]["node"]["label"] == "Check the bill"  # trimmed, spaces collapsed
    assert ops[2] == {"op": "link", "edge": {"from": "a", "to": "b"}}
    change = cast("SketchOp", {"op": "change", "node": {"id": "a", "label": "Check it", "origin": "you"}})
    sketch, ops = apply(sketch, [change])
    assert ops == [{"op": "change", "node": {**sketch["nodes"][0]}}]
    assert sketch["nodes"][0]["label"] == "Check it" and sketch["nodes"][0]["origin"] == "athena"


def test_places_never_move() -> None:
    sketch = three()
    sketch, _ = apply(sketch, [cast("SketchOp", {"op": "remove", "node": {"id": "b"}}), add("d")])
    assert [n["id"] for n in sketch["nodes"]] == ["a", "c", "d"]
    change = cast("SketchOp", {"op": "change", "node": {"id": "a", "slot": "steps"}})
    sketch, _ = apply(sketch, [change])
    assert [n["id"] for n in sketch["nodes"]] == ["a", "c", "d"]


def test_removing_a_node_takes_its_edges_and_says_so() -> None:
    sketch, ops = apply(three(), [cast("SketchOp", {"op": "remove", "node": {"id": "a"}})])
    assert sketch["edges"] == []
    assert [o["op"] for o in ops] == ["remove", "remove"]
    assert ops[0] == {"op": "remove", "edge": {"from": "a", "to": "b"}}
    assert ops[1]["node"]["id"] == "a" and ops[1]["node"]["label"] == "Check the bill"


def test_removing_one_edge() -> None:
    sketch, ops = apply(three(), [cast("SketchOp", {"op": "remove", "edge": {"from": "a", "to": "b"}})])
    assert sketch["edges"] == [] and len(sketch["nodes"]) == 3
    assert ops == [{"op": "remove", "edge": {"from": "a", "to": "b"}}]


@pytest.mark.parametrize(
    "op",
    [
        add("a"),  # duplicate id
        add("x", slot="nowhere"),
        add("x", kind="cloud"),
        add("x", label="   "),
        add("x", label="w" * (LABEL_MAX + 1)),
        add("bad id!"),
        cast("SketchOp", {"op": "change", "node": {"id": "zz", "label": "x"}}),
        cast("SketchOp", {"op": "change", "node": {"id": "a"}}),  # nothing to change
        cast("SketchOp", {"op": "remove", "node": {"id": "zz"}}),
        cast("SketchOp", {"op": "remove", "edge": {"from": "b", "to": "a"}}),
        link("a", "b"),  # duplicate
        link("a", "a"),  # self-loop
        link("a", "zz"),  # dangling
        cast("SketchOp", {"op": "move"}),
    ],
)
def test_a_bad_op_raises_and_leaves_the_sketch_untouched(op: SketchOp) -> None:
    sketch = three()
    before = repr(sketch)
    with pytest.raises(SketchError):
        apply(sketch, [add("d"), op])  # the good op before it does not land either
    assert repr(sketch) == before


def test_the_node_cap() -> None:
    sketch, _ = apply(empty(), [add(f"n{i}") for i in range(SKETCH_NODES_MAX)])
    with pytest.raises(SketchError, match=str(SKETCH_NODES_MAX)):
        apply(sketch, [add("one-more")])


def test_confirm_marks_proposals_and_answers_change_ops() -> None:
    sketch, ops = confirm(three(), ["a", "c"])
    assert [(n["id"], n["confirmed"], n["origin"]) for n in sketch["nodes"]] == [
        ("a", True, "athena"),
        ("b", False, "athena"),
        ("c", True, "athena"),
    ]
    assert [o["node"]["id"] for o in ops] == ["a", "c"]
    again, ops = confirm(sketch, ["a"])
    assert ops == [] and again == sketch
    with pytest.raises(SketchError):
        confirm(sketch, ["zz"])


def test_coverage_from_the_sketch_alone() -> None:
    sketch = three()
    cov = coverage(sketch)
    assert cov == {"need": 0.5, "apps": 0.5, "inputs": 0, "steps": 0, "hand": 0.5, "output": 0, "never": 0}
    sketch, _ = confirm(sketch, ["a"])
    assert coverage(sketch)["need"] == 1
    assert coverage(sketch, frozenset({"inputs", "need"}))["inputs"] == "skipped"
    assert coverage(sketch, frozenset({"need"}))["need"] == 1  # a confirmed node beats a skip
    assert open_slots(coverage(sketch, frozenset({"inputs"}))) == ["apps", "steps", "hand", "output", "never"]


def test_agreed_is_the_contract_rule() -> None:
    base: dict[str, Any] = {"need": 1, "apps": 1, "inputs": 0.5, "steps": "skipped", "hand": 1, "output": 1}
    assert agreed(cast("Any", {**base, "never": 1}))
    assert agreed(cast("Any", {**base, "never": "skipped"}))
    assert not agreed(cast("Any", {**base, "never": 0}))
    assert not agreed(cast("Any", {**base, "hand": 0.5, "never": 1}))
    assert not agreed(cast("Any", {**base, "hand": "skipped", "never": 1}))


def test_the_persons_own_words_cannot_be_reworded_or_removed() -> None:
    sketch, _ = apply(empty(), [ink("a"), add("b", "apps", "app")], said=SAID)
    assert (sketch["nodes"][0]["origin"], sketch["nodes"][0]["confirmed"]) == ("you", True)
    reword = cast("SketchOp", {"op": "change", "node": {"id": "a", "label": "Pay the club"}})
    with pytest.raises(SketchError, match="own words"):
        apply(sketch, [reword])
    with pytest.raises(SketchError, match="own words"):
        apply(sketch, [cast("SketchOp", {"op": "remove", "node": {"id": "a"}})])
    # her detail on their node would read as theirs (ADR 0028)
    detail = cast("SketchOp", {"op": "change", "node": {"id": "a", "detail": "every month"}})
    with pytest.raises(SketchError, match="own words"):
        apply(sketch, [detail])


def test_the_caller_never_decides_whose_a_node_is() -> None:
    # ADR 0028: origin, confirmed and quote on an add are ignored; only a proven quote inks
    claimed = add("a", origin="you", confirmed=True, quote="my own words here")
    sketch, ops = apply(empty(), [claimed], said=Said(["these are my own words here"]))
    node = sketch["nodes"][0]
    assert (node["origin"], node["confirmed"]) == ("athena", False) and "quote" not in node
    assert ops[0]["node"] == node


def test_a_quote_inks_only_the_words_it_holds() -> None:
    # ADR 0028: the quote proves the label and detail only when they are its own words
    sketch, _ = apply(
        empty(),
        [
            ink("a"),  # the label runs inside the quote
            ink("b", label="Pay every invoice at once"),  # a true quote under her own label
            ink("c", detail="and pay it"),  # her own detail under a true quote
            ink("d", label="the BILL against", detail="check"),  # case ignored, both inside
            add("e", quote="the bill against the days"),  # a true quote that lacks "Check"
        ],
        said=SAID,
    )
    assert [(n["origin"], n["confirmed"], "quote" in n) for n in sketch["nodes"]] == [
        ("you", True, True),
        ("athena", False, False),
        ("athena", False, False),
        ("you", True, True),
        ("athena", False, False),
    ]


def test_an_answer_she_wrote_and_the_person_picked_is_agreed_not_theirs() -> None:
    # ADR 0028: a picked answer confirms her words; it never makes them the person's
    said = Said(["Each month I check the bill"], picked=["Each dispute waits for my yes"])
    picked = add(
        "g", "hand", "gate", label="Each dispute waits for my yes", quote="each dispute waits for my yes"
    )
    sketch, _ = apply(empty(), [picked], said=said)
    node = sketch["nodes"][0]
    assert (node["origin"], node["confirmed"]) == ("athena", True) and "quote" not in node
    typed = Said([*said.typed, "Each dispute waits for my yes"], said.picked)  # they typed it too
    sketch, _ = apply(empty(), [picked], said=typed)
    assert (sketch["nodes"][0]["origin"], sketch["nodes"][0]["confirmed"]) == ("you", True)


def test_rewriting_a_confirmed_proposals_detail_asks_for_confirmation_again() -> None:
    sketch, _ = apply(empty(), [add("b", "apps", "app", detail="billing page")])
    sketch, _ = confirm(sketch, ["b"])
    detail = cast("SketchOp", {"op": "change", "node": {"id": "b", "detail": "pays the bill"}})
    sketch, ops = apply(sketch, [detail])
    assert sketch["nodes"][0]["confirmed"] is False and ops[0]["node"]["confirmed"] is False


def test_rewording_a_confirmed_proposal_asks_for_confirmation_again() -> None:
    sketch, _ = apply(empty(), [add("b", "apps", "app")])
    sketch, _ = confirm(sketch, ["b"])
    reword = cast("SketchOp", {"op": "change", "node": {"id": "b", "label": "The school portal"}})
    sketch, ops = apply(sketch, [reword])
    assert sketch["nodes"][0]["confirmed"] is False and ops[0]["node"]["confirmed"] is False


def test_drop_rubs_out_her_guesses_and_their_links_only() -> None:
    sketch, _ = apply(empty(), [ink("a"), add("b", "apps", "app"), add("c"), link("a", "b")], said=SAID)
    out, ops = drop(sketch, ["b"])
    assert [n["id"] for n in out["nodes"]] == ["a", "c"] and out["edges"] == []
    assert [o["op"] for o in ops] == ["remove", "remove"] and "edge" in ops[0] and ops[1]["node"]["id"] == "b"
    with pytest.raises(SketchError, match="not a guess"):
        drop(sketch, ["a"])
    inked, _ = confirm(sketch, ["c"])
    with pytest.raises(SketchError, match="not a guess"):
        drop(inked, ["c"])
    with pytest.raises(SketchError):
        drop(sketch, ["zz"])
    assert [n["id"] for n in sketch["nodes"]] == ["a", "b", "c"]  # untouched on a refusal
