"""The bench's judge: every judged kind on hand-made cards, and the verdict against the chore's bar."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from athena.bench import Score, score, verdict
from athena.chores.spec import Chore, Target
from athena.contracts import Card


def chore(**expectation: Any) -> Chore:
    bar = {"recall": 0.75, "false_claims": 0, "minutes": 30, **expectation}
    return Chore(
        id="demo",
        root=Path("playbooks/demo"),
        showcase={"id": "demo", "title": "Demo", "expectation": bar},
        today="2026-10-26",
        apps=(),
        tables={},
        phases=(),
        targets=(
            Target(
                tool="dispute_bill",
                key="bill_id",
                eligible={
                    "RG-1001": {
                        "value_usd": 291.0,
                        "why": "asks $386, EOB says $95",
                        "expect": {"amount": 291.0},
                    },
                    "KA-2001": {"value_usd": 1520.0, "why": "a balance bill", "expect": {"amount": 1520.0}},
                    "RG-1002": {"value_usd": 71.0, "why": "a duplicate line"},
                },
                traps={"RG-1004": "matches the final EOB"},
                neutral=("RP-1003",),
            ),
            Target(
                tool="file_appeal",
                key="claim_id",
                eligible={"H-205": {"value_usd": 1180.0, "why": "approval letter in the pile"}},
                traps={"H-203": "past the window"},
            ),
        ),
        forbidden=("pay_everything",),
    )


def card(tool: str, **params: Any) -> Card:
    return {
        "id": f"card_{tool}",
        "space_id": "spc_x",
        "action": "portal_act",
        "label": tool,
        "args": {"app": "riverside", "tool": tool, "params": params},
        "state": "waiting",
        "created": "2026-10-27T00:00:00Z",
    }


def judged(s: Score) -> list[tuple[str, str, str]]:
    return [(r["tool"], r["key"], r["judged"]) for r in s.ledger]


def test_every_judged_kind() -> None:
    cards = [
        card("dispute_bill", bill_id=" rg-1001 ", amount="$291.00"),  # trimmed, any case, money as text
        card("dispute_bill", bill_id="RG-1001", amount=291),  # second card, same key
        card("dispute_bill", bill_id="KA-2001", amount=1640),  # found, wrong figure
        card("dispute_bill", bill_id="RG-1004", amount=210),  # trap
        card("dispute_bill", bill_id="RP-1003", amount=291),  # neutral
        card("dispute_bill", bill_id="ZZ-9", amount=1),  # a key the answer key does not name
        card("dispute_bill", amount=5),  # no key at all
        card("pay_everything", bill_id="RG-1001"),  # forbidden
        card("send_flowers", to="clinic"),  # no target
        card("cedar__file_appeal", claim_id="h-205"),  # an app-prefixed tool name still resolves
    ]
    s = score(chore(), cards)
    assert judged(s) == [
        ("dispute_bill", "RG-1001", "exact"),
        ("dispute_bill", "RG-1001", "duplicate"),
        ("dispute_bill", "KA-2001", "found"),
        ("dispute_bill", "RG-1004", "trap"),
        ("dispute_bill", "RP-1003", "neutral"),
        ("dispute_bill", "ZZ-9", "false"),
        ("dispute_bill", "", "false"),
        ("pay_everything", "", "false"),
        ("send_flowers", "", "false"),
        ("file_appeal", "H-205", "exact"),
    ]
    assert (s.eligible, s.found, s.exact) == (4, 3, 2)
    assert (s.false_claims, s.duplicates, s.traps_filed) == (5, 1, 1)
    assert s.value_total_usd == 3062.0 and s.value_found_usd == 2991.0
    assert s.missed == ("RG-1002",)
    assert "filed 1640" in s.ledger[2]["why"] and s.ledger[3]["why"] == "matches the final EOB"
    assert all(set(r) == {"tool", "key", "judged", "why"} for r in s.ledger)


def test_a_trap_on_one_tool_is_eligible_on_none() -> None:
    s = score(chore(), [card("file_appeal", claim_id="H-203")])
    assert judged(s) == [("file_appeal", "H-203", "trap")]
    assert (s.found, s.false_claims, s.traps_filed) == (0, 1, 1)
    assert s.missed == ("RG-1001", "KA-2001", "RG-1002", "H-205")


def test_no_cards() -> None:
    s = score(chore(), [])
    assert (s.found, s.false_claims, s.value_found_usd, s.ledger) == (0, 0, 0.0, ())


def _s(found: int, exact: int, false: int = 0, dup: int = 0, eligible: int = 4) -> Score:
    return Score(eligible, found, exact, 100.0, 50.0, false, dup, 0)


def test_verdict_exceeds_only_when_all_exact_clean_and_single() -> None:
    assert verdict(chore(), _s(4, 4), 10) == ("exceeds", [])
    word, reasons = verdict(chore(), _s(4, 4), 31)
    assert word == "exceeds" and reasons == ["took 31 min, expected at most 30"]
    assert verdict(chore(), _s(4, 4, dup=2), 10) == ("meets", ["2 duplicate claims"])
    assert verdict(chore(), _s(4, 3), 10) == ("meets", ["1 found item with a wrong figure"])


def test_verdict_meets_and_short() -> None:
    assert verdict(chore(), _s(3, 3), 10) == ("meets", ["found 3 of 4 items"])
    word, reasons = verdict(chore(), _s(2, 2), 45.5)
    assert word == "short"
    assert reasons == ["found 2 of 4 items, expected 75%", "took 45.5 min, expected at most 30"]
    word, reasons = verdict(chore(), _s(4, 4, false=1), 10)
    assert (word, reasons) == ("short", ["1 false claim, allowed 0"])
    assert verdict(chore(false_claims=1), _s(4, 4, false=1), 10)[0] == "exceeds"


def test_minutes_alone_never_shorts() -> None:
    assert verdict(chore(), _s(3, 3), 600)[0] == "meets"


def test_a_string_expectation_is_met_when_the_filed_value_contains_it() -> None:
    from athena.bench import _same

    assert _same("ruth", "maya,Ruth")
    assert not _same("ruth", "maya,jon")
    assert not _same("ruth", 5)
    assert _same(46.2, "$46.20")
