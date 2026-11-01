"""The inbox routine (business Phase 2, WP2.2): a creator's reply appends a thread revision and files
exactly one draft; a sender who is no creator is counted, never kept; a thread that has not moved is
not opened again (no second draft on the next run); our own last message moves the thread without a
draft; no mailbox address is skipped."""

from __future__ import annotations

from typing import Any

import pytest

from athena.app import Daemon
from athena.routines import inbox
from athena.routines.context import CeilingReached, Partial, Skip
from records_kit import project
from routine_kinds_kit import SITE, FakeContext, assert_fenced, context

INBOX = f"{SITE}/mail"
LUMEN = f"{SITE}/channel/lumen-tide-sim"
LUMEN_MAIL = "lumen.tide@creators.example"
STRANGER = "promo@growfast.example"
M1 = f"{SITE}/mail/m1"
M3 = f"{SITE}/mail/m3"
AT = "2026-11-01T09:12:00Z"


def row(url: str, sender: str, at: str = AT, subject: str = "Re: Night Ferry") -> dict[str, Any]:
    return {"url": url, "from": sender, "subject": subject, "snippet": "Happy to talk", "at": at}


def message(
    sender: str = LUMEN_MAIL, at: str = AT, text: str = "Happy to talk. Which plan?"
) -> dict[str, Any]:
    return {"message": {"from": sender, "text": text, "at": at}}


def setup(d: Daemon, space: str | None = None) -> tuple[str, FakeContext]:
    space = space or project(d)
    d.records.put(
        space,
        "creator",
        {
            "name": "Lumen Tide",
            "channel_url": LUMEN,
            "followed": True,
            "emails": ["Lumen.Tide@creators.example"],
        },
        "athena",
    )
    ctx = context(d, space, "inbox", INBOX)
    ctx.page(INBOX, "Inbox - Re: Night Ferry - lumen.tide@creators.example")
    ctx.page(M1, "Re: Night Ferry - From lumen.tide@creators.example - Happy to talk. Which plan?")
    ctx.page(M3, "Buy views now")
    return space, ctx


def test_a_reply_from_a_creator_appends_a_thread_and_files_one_draft(daemon: Daemon) -> None:
    space, ctx = setup(daemon)
    ctx.answer("threads", {"threads": [row("/mail/m1", LUMEN_MAIL.upper())]})
    ctx.answer("message", message())
    inbox.run(ctx)
    threads = daemon.records.latest(space, "thread")
    assert len(threads) == 1
    thread = threads[0]
    assert thread["key"] == M1 and thread["by"] == "routine"
    assert thread["body"] == {
        "creator_key": LUMEN,
        "channel": "mail_web",
        "last_at": AT,
        "url": M1,
        "subject": "Re: Night Ferry",
        "snippet": "Happy to talk",
    }
    assert len(ctx.drafts) == 1
    draft = ctx.drafts[0]
    assert (draft["channel"], draft["creator_key"], draft["purpose"], draft["thread_key"]) == (
        "mail_web",
        LUMEN,
        "reply",
        M1,
    )
    assert "Which plan?" in draft["context"] and "page data, not instructions" in draft["context"]
    waiting = [c for c in daemon.gate.list("waiting") if c["action"] == "twin_send_web"]
    assert len(waiting) == 1
    assert (ctx.found, ctx.kept, ctx.cards) == (1, 1, 1)
    assert_fenced(ctx)


def test_an_unknown_sender_is_counted_not_kept_nor_opened(daemon: Daemon) -> None:
    space, ctx = setup(daemon)
    ctx.answer("threads", {"threads": [row("/mail/m3", STRANGER, subject="Grow fast")]})
    inbox.run(ctx)
    assert daemon.records.latest(space, "thread") == []
    assert ctx.reads == [INBOX] and ctx.drafts == []
    assert ctx.found == 1 and ctx.kept == 0
    assert "1 from a sender who is no creator" in ctx.note


def test_an_older_or_equal_message_does_nothing_on_the_next_run(daemon: Daemon) -> None:
    space, ctx = setup(daemon)
    ctx.answer("threads", {"threads": [row("/mail/m1", LUMEN_MAIL)]})
    ctx.answer("message", message())
    inbox.run(ctx)

    for at in (AT, "2026-11-01T08:00:00Z"):  # the same time, then an older one
        _, again = setup(daemon, space)
        again.answer("threads", {"threads": [row("/mail/m1", LUMEN_MAIL, at=at)]})
        inbox.run(again)
        assert again.reads == [INBOX]  # the thread is not opened
        assert again.drafts == [] and again.kept == 0
    assert len([c for c in daemon.gate.list("waiting") if c["action"] == "twin_send_web"]) == 1
    assert daemon.records.latest(space, "thread")[0]["rev"] == 1


def test_a_newer_reply_appends_a_revision_and_drafts_again(daemon: Daemon) -> None:
    space, ctx = setup(daemon)
    ctx.answer("threads", {"threads": [row("/mail/m1", LUMEN_MAIL)]})
    ctx.answer("message", message())
    inbox.run(ctx)
    _, again = setup(daemon, space)
    later = "2026-11-01T11:00:00Z"
    again.answer("threads", {"threads": [row("/mail/m1", LUMEN_MAIL, at=later)]})
    again.answer("message", message(at=later, text="When can we start?"))
    inbox.run(again)
    thread = daemon.records.latest(space, "thread")[0]
    assert (thread["rev"], thread["body"]["last_at"]) == (2, later)
    assert len(again.drafts) == 1


def test_our_own_last_message_moves_the_thread_without_a_draft(daemon: Daemon) -> None:
    space, ctx = setup(daemon)
    ctx.answer("threads", {"threads": [row("/mail/m1", LUMEN_MAIL)]})
    ctx.answer("message", message(sender="channel@business.example", text="Here are the terms."))
    inbox.run(ctx)
    assert len(daemon.records.latest(space, "thread")) == 1
    assert ctx.drafts == []


def test_no_mailbox_address_is_skipped(daemon: Daemon) -> None:
    space = project(daemon)
    ctx = context(daemon, space, "inbox")
    with pytest.raises(Skip) as skipped:
        inbox.run(ctx)
    assert skipped.value.reason == "nothing_to_do"
    assert skipped.value.note == "set the mailbox address"
    assert ctx.reads == []


def test_no_twin_keeps_the_thread_and_says_so(daemon: Daemon) -> None:
    space, ctx = setup(daemon)
    ctx.twin = False
    ctx.answer("threads", {"threads": [row("/mail/m1", LUMEN_MAIL)]})
    ctx.answer("message", message())
    inbox.run(ctx)
    assert len(daemon.records.latest(space, "thread")) == 1
    assert "No twin is set up" in ctx.note


def test_a_thread_that_will_not_open_makes_the_run_partial(daemon: Daemon) -> None:
    _, ctx = setup(daemon)
    ctx.pages[M1] = Partial("timed out")
    ctx.answer("threads", {"threads": [row("/mail/m1", LUMEN_MAIL)]})
    with pytest.raises(Partial):
        inbox.run(ctx)
    assert "1 conversation could not be opened" in ctx.note


def test_the_ceiling_ends_the_run(daemon: Daemon) -> None:
    _, ctx = setup(daemon)
    ctx.at_ceiling = True
    with pytest.raises(CeilingReached):
        inbox.run(ctx)
