"""The pure rules under the senses: normalising, packet hashes, vague changes, whose yes, spotting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from athena.senses.backends import FixtureReader, Fixtures, FixtureSegmenter
from athena.senses.call import packet_sha256, plain, sources, unsupported
from athena.senses.circle import claims, runs, whose_yes
from athena.senses.contract import Media
from athena.senses.normalise import agree, comparable, iso_date, money, stored
from athena.senses.walk import classify, vague_change

PLAYBOOKS = Path(__file__).resolve().parents[1] / "playbooks"


def test_money_and_dates_normalise() -> None:
    assert money("$1,640.00") == 1640.0 and money("1640.00") == 1640.0 and money("$ 0.00") == 0.0
    assert money("small upcharge") is None
    assert iso_date("August 3, 2026") == iso_date("08/03/2026") == iso_date("3 August 2026") == "2026-08-03"
    assert iso_date("2026-10-29 10:30") is None and iso_date("02/30/2026") is None
    assert agree("amount_due_usd", "$1,640.00", "1640.00")
    assert not agree("amount_due_usd", "$10,400.00", "$10,100.00")
    assert agree("strength", "5 mg", "5mg") and agree("name", "LISINOPRIL", "Lisinopril")
    assert not agree("directions", "Take 1 capsule daily", "Take 1 capsule weekly")
    assert stored("amount_due_usd", "$386.00") == 386.0 and stored("dos", "May 20, 2026") == "2026-05-20"
    assert comparable("plan_year", 2027.0) == comparable("plan_year", "2027")


def test_packet_hash_binds_exact_sentences() -> None:
    world = json.loads((PLAYBOOKS / "prior-auth-denial-appeal" / "world.json").read_text(encoding="utf-8"))
    drafts = world["tables"]["drafts"]
    for d in drafts:
        assert packet_sha256(d["sentences"]) == d["packet_sha256"], d["packet_id"]
    s = [dict(x) for x in drafts[0]["sentences"]]
    shuffled = [dict(x, cites=list(reversed(x["cites"])) + x["cites"][:1], extra=1) for x in s]
    assert packet_sha256(shuffled) == drafts[0]["packet_sha256"], "cite order, duplicates, other keys"
    s[0]["text"] += " "
    assert packet_sha256(s) != drafts[0]["packet_sha256"], "one changed character breaks the binding"


def test_a_sentence_needs_a_kept_source() -> None:
    tables = {
        "sheet_fields": [
            {"sheet_id": "s01", "field": "member", "status": "read"},
            {"sheet_id": "s03", "field": "amount_due_usd", "status": "asked"},
        ],
        "call_turns": [{"turn_id": "call-1#5"}],
    }
    known = sources(tables)
    sentences = [
        {"text": "a", "cites": ["s01.member", "call-1#5"]},
        {"text": "b", "cites": []},
        {"text": "c", "cites": ["s03.amount_due_usd"]},
        {"text": "d", "cites": ["call-2#4"]},
    ]
    assert unsupported(sentences, known) == [1, 2, 3]
    assert (
        plain("Hi, before we start: THIS call is being transcribed!")
        == "hi before we start this call is being transcribed"
    )


def test_vague_change_names_each_missing_term() -> None:
    assert vague_change({"price_usd": 120.0, "days": 0, "quote_line": "Q-07"}) == []
    assert vague_change({"price_usd": "small upcharge", "quote_line": "Q-11"}) == [
        "price not a number",
        "no days",
    ]
    assert vague_change({"price_usd": 165.0, "days": 1}) == ["no quote line"]
    assert vague_change({"price_usd": 95.0, "days": "as needed", "quote_line": "Q-07"}) == ["no days"]
    assert vague_change({}) == ["no price", "no days", "no quote line"]


def test_promise_classifier_explains_itself() -> None:
    p = classify("I'll swap the dimmers for the smart ones for $180, half a day.")
    assert p is not None and p.mentions_price and p.mentions_days and p.mentions_change
    assert p.why == "commits, names a price, names a time"
    no_charge = classify("Sure, moving that outlet is no charge.")
    assert no_charge is not None and no_charge.mentions_price and not no_charge.mentions_days
    assert classify("Can we move the island outlet to the end panel?") is None
    assert classify("We added a nail plate behind the sink, code thing.") is None
    assert classify("Cabinets are in, doors are going on today, about fourteen hung so far.") is None


SIGNERS = json.loads((PLAYBOOKS / "care-circle" / "senses" / "signers.json").read_text(encoding="utf-8"))


def test_whose_yes_exact_subject_beats_star_and_no_rule_refuses() -> None:
    rules = SIGNERS["rules"]
    assert whose_yes("share_record", "medication", rules) == {"needs": "parent", "parent_veto": True}
    assert whose_yes("share_record", "password", rules) == {"needs": "role:primary", "parent_veto": True}
    assert whose_yes("export_record", "record", rules) == {"needs": "refuse"}


@pytest.mark.parametrize(
    ("action", "subject", "proposer", "yes", "no", "expect"),
    [
        ("change_appointment", "appointment", "maya", ["maya", "maya"], [], False),  # own yes, twice
        ("change_appointment", "appointment", "maya", ["jon", "ruth"], [], True),
        ("change_appointment", "appointment", "jon", ["jon", "maya", "ruth"], ["ruth"], False),  # veto
        ("pay_bill", "equipment", "maya", ["jon", "ruth"], ["ruth"], False),  # yes and no is no
        ("share_record", "medication", "jon", ["dad", "Ruth"], [], False),  # not a member's id
        ("pay_bill", "pharmacy", "maya", ["maya"], [], True),
    ],
)
def test_runs_counts_only_the_yeses_the_rule_allows(
    action: str, subject: str, proposer: str, yes: list[str], no: list[str], expect: bool
) -> None:
    rule = whose_yes(action, subject, SIGNERS["rules"])
    assert runs(rule, proposer, yes, no, SIGNERS["members"]) is expect


def test_claim_spotter_skips_negated_hedged_and_questions() -> None:
    assert claims("If they move it to Tuesday, I can take her. I'll call the clinic tomorrow to ask.") == [
        "If they move it to Tuesday, I can take her.",
        "I'll call the clinic tomorrow to ask.",
    ]
    assert claims("The cardiology visit is Thursday and I can't do Thursday.") == []
    assert claims("Maybe I will look at the bills on the weekend.") == []
    assert claims("Who's going to sort out the shower chair?") == []
    assert claims("I can hear you all fine now.") == []


def test_fixture_roles_filter_and_restrict(tmp_path: Path) -> None:
    (tmp_path / "m.json").write_text(
        json.dumps(
            {
                "segments": [
                    {"label": "pill bottle", "score": 0.9, "box": [0, 0, 1, 1], "frame": 0, "track_id": "B1"},
                    {"label": "coffee mug", "score": 0.7, "box": [0, 0, 1, 1], "frame": 0},
                ],
                "reads": [
                    {"attempt": 0, "fields": [{"name": "a", "value": "1"}, {"name": "b", "value": "2"}]}
                ],
            }
        ),
        encoding="utf-8",
    )
    fx = Fixtures(tmp_path)
    item = Media(id="m", kind="photo", sense="circle")
    segs, usage = FixtureSegmenter(fx).segment(item, "Pill Bottle")
    assert [s.track_id for s in segs] == ["B1"] and usage.cost_usd == 0.0
    assert len(FixtureSegmenter(fx).segment(item, "")[0]) == 2
    read, _ = FixtureReader(fx).read(item, ["a", "c"], 1)  # no attempt 1: reads[0] answers
    assert [f.name for f in read.fields] == ["a"] and read.unreadable == ("c",)
