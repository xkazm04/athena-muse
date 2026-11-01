"""The outreach routine (business Phase 2, WP2.2): an offer goes by mail when the creator has an email,
else by bio message, else as a comment on the kept track; one per creator, never while a thread, an
agreement or a waiting offer exists; at most five a run; no twin is skipped no_twin, nothing to offer
is skipped nothing_to_do."""

from __future__ import annotations

from typing import Any

import pytest

from athena.app import Daemon
from athena.routines import outreach
from athena.routines.context import Skip
from records_kit import project
from routine_kinds_kit import SITE, context

WHEN = "2026-11-01T12:00:00Z"


def creator(d: Daemon, space: str, n: int, **extra: Any) -> str:
    url = f"{SITE}/channel/c{n}"
    d.records.put(
        space, "creator", {"name": f"Creator {n}", "channel_url": url, "followed": True, **extra}, "athena"
    )
    return url


def kept_track(d: Daemon, space: str, who: str, n: int, verdict: str = "keep") -> str:
    url = f"{SITE}/watch?v={who.rsplit('/', 1)[-1]}-{n}"
    found = d.records.put(
        space, "track", {"url": url, "title": f"Song {n}", "creator_key": who, "found_at": WHEN}, "athena"
    )
    d.records.verdict(found["id"], {"verdict": verdict})  # type: ignore[typeddict-item]
    return url


def test_the_channel_is_mail_then_bio_then_comment(daemon: Daemon) -> None:
    space = project(daemon)
    mail = creator(daemon, space, 1, emails=["c1@creators.example"], bio_links=["https://links.example/c1"])
    bio = creator(daemon, space, 2, bio_links=["https://links.example/c2"])
    comment = creator(daemon, space, 3)
    tracks = {who: kept_track(daemon, space, who, 1) for who in (mail, bio, comment)}
    ctx = context(daemon, space, "outreach")
    outreach.run(ctx)
    chosen = {d["creator_key"]: d for d in ctx.drafts}
    assert {k: d["channel"] for k, d in chosen.items()} == {mail: "mail_web", bio: "bio", comment: "comment"}
    assert all(d["purpose"] == "offer" and d["thread_key"] is None for d in ctx.drafts)
    assert "c1@creators.example" in chosen[mail]["context"]
    assert "https://links.example/c2" in chosen[bio]["context"]
    assert f"comment under the song at {tracks[comment]}" in chosen[comment]["context"]
    assert "Song 1" in chosen[mail]["context"] and "Creator 1" in chosen[mail]["context"]
    assert "Our channel: Music channel." in chosen[mail]["context"]
    assert ctx.cards == 3


def test_one_offer_per_creator_and_an_open_card_blocks_the_next(daemon: Daemon) -> None:
    space = project(daemon)
    who = creator(daemon, space, 1, emails=["c1@creators.example"])
    kept_track(daemon, space, who, 1)
    kept_track(daemon, space, who, 2)
    first = context(daemon, space, "outreach")
    outreach.run(first)
    assert len(first.drafts) == 1  # two kept songs, one creator: one offer

    again = context(daemon, space, "outreach")
    with pytest.raises(Skip) as skipped:
        outreach.run(again)  # the first offer is still waiting for the person
    assert skipped.value.reason == "nothing_to_do" and again.drafts == []


def test_a_thread_or_an_agreement_means_they_were_written_to(daemon: Daemon) -> None:
    space = project(daemon)
    talking = creator(daemon, space, 1)
    agreed = creator(daemon, space, 2)
    passed = creator(daemon, space, 3)
    fresh = creator(daemon, space, 4)
    for who in (talking, agreed, fresh):
        kept_track(daemon, space, who, 1)
    kept_track(daemon, space, passed, 1, verdict="pass")
    daemon.records.put(
        space, "thread", {"key": "t", "creator_key": talking, "channel": "bio", "last_at": WHEN}, "person"
    )
    daemon.records.put(
        space, "agreement", {"creator_key": agreed, "state": "proposed", "thread_key": "t"}, "person"
    )
    ctx = context(daemon, space, "outreach")
    outreach.run(ctx)
    assert [d["creator_key"] for d in ctx.drafts] == [fresh]


def test_at_most_five_a_run(daemon: Daemon) -> None:
    space = project(daemon)
    for n in range(7):
        kept_track(daemon, space, creator(daemon, space, n), 1)
    ctx = context(daemon, space, "outreach")
    outreach.run(ctx)
    assert len(ctx.drafts) == 5 and ctx.found == 7
    assert "2 more creators wait for the next run" in ctx.note
    after = context(daemon, space, "outreach")
    outreach.run(after)
    assert len(after.drafts) == 2  # the five waiting cards block their creators


def test_no_twin_is_skipped_no_twin(daemon: Daemon) -> None:
    space = project(daemon)
    kept_track(daemon, space, creator(daemon, space, 1), 1)
    ctx = context(daemon, space, "outreach")
    ctx.twin = False
    with pytest.raises(Skip) as skipped:
        outreach.run(ctx)
    assert skipped.value.reason == "no_twin"


def test_nothing_kept_is_skipped_nothing_to_do(daemon: Daemon) -> None:
    space = project(daemon)
    kept_track(daemon, space, creator(daemon, space, 1), 1, verdict="later")
    with pytest.raises(Skip) as skipped:
        outreach.run(context(daemon, space, "outreach"))
    assert skipped.value.reason == "nothing_to_do"


def test_another_projects_waiting_card_does_not_block(daemon: Daemon) -> None:
    space = project(daemon)
    who = creator(daemon, space, 1)
    kept_track(daemon, space, who, 1)
    other = daemon.spaces.create({"name": "Other"})["id"]
    daemon.gate.file(other, "twin_send_web", {"creator_key": who}, "Send: offer")
    ctx = context(daemon, space, "outreach")
    outreach.run(ctx)
    assert len(ctx.drafts) == 1
