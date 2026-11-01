"""The watch routine (business Phase 2, WP2.2): a followed creator's new upload becomes one track, a
known one appends nothing, a page that fails makes the run partial with the right denominator, an
unfollowed creator is never read, and a project that follows no one is skipped."""

from __future__ import annotations

import pytest

from athena.app import Daemon
from athena.routines import watch
from athena.routines.context import CeilingReached, Partial, Skip
from records_kit import project
from routine_kinds_kit import SITE, FakeContext, assert_fenced, context, fenced_text

LUMEN = f"{SITE}/channel/lumen-tide-sim"
PAPER = f"{SITE}/channel/paper-orbit-sim"
QUIET = f"{SITE}/channel/quiet-sim"


def follow(d: Daemon, space: str, url: str, name: str, followed: bool = True) -> None:
    d.records.put(space, "creator", {"name": name, "channel_url": url, "followed": followed}, "athena")


def uploads(*items: tuple[str, str]) -> dict[str, object]:
    return {"tracks": [{"url": u, "title": t, "published": "2026-10-28"} for u, t in items]}


def setup(d: Daemon) -> tuple[str, FakeContext]:
    space = project(d)
    follow(d, space, LUMEN, "Lumen Tide")
    ctx = context(d, space, "watch")
    ctx.page(f"{LUMEN}/videos", "Lumen Tide - Videos - Glass Harbour")
    return space, ctx


def test_a_new_upload_becomes_one_track_found_now_by_its_creator(daemon: Daemon) -> None:
    space, ctx = setup(daemon)
    ctx.answer("tracks", uploads(("/watch?v=lt2", "Glass Harbour")))
    watch.run(ctx)
    tracks = daemon.records.latest(space, "track")
    assert [t["body"]["title"] for t in tracks] == ["Glass Harbour"]
    body = tracks[0]["body"]
    assert body["url"] == f"{SITE}/watch?v=lt2"  # a relative link is resolved against the page
    assert body["creator_key"] == LUMEN
    assert body["found_at"].endswith("Z") and "published" not in body
    assert tracks[0]["by"] == "routine"
    assert (ctx.found, ctx.of, ctx.kept) == (1, 1, 1)
    assert ctx.reads == [f"{LUMEN}/videos"]
    assert_fenced(ctx)
    assert "Glass Harbour" in fenced_text(ctx.calls[0])


def test_a_known_track_appends_nothing_and_keeps_the_verdict(daemon: Daemon) -> None:
    space, ctx = setup(daemon)
    ctx.answer("tracks", uploads(("/watch?v=lt2", "Glass Harbour")))
    watch.run(ctx)
    kept = daemon.records.latest(space, "track")[0]
    daemon.records.verdict(kept["id"], {"verdict": "keep"})

    again = context(daemon, space, "watch")
    again.pages = ctx.pages
    again.answer("tracks", uploads(("HTTP://127.0.0.1:8781/watch?v=lt2", "Glass Harbour (renamed)")))
    watch.run(again)
    latest = daemon.records.latest(space, "track")
    assert len(latest) == 1 and latest[0]["rev"] == 2  # the verdict's revision, nothing after it
    assert latest[0]["body"]["verdict"] == "keep" and latest[0]["body"]["title"] == "Glass Harbour"
    assert (again.found, again.kept) == (1, 0)


def test_a_failing_creator_page_is_skipped_and_the_run_is_partial(daemon: Daemon) -> None:
    space, ctx = setup(daemon)
    follow(daemon, space, PAPER, "Paper Orbit")
    ctx.pages[f"{PAPER}/videos"] = Partial("the page did not load")
    ctx.answer("tracks", uploads(("/watch?v=lt2", "Glass Harbour")))
    with pytest.raises(Partial) as stopped:
        watch.run(ctx)
    assert ctx.of == 2
    assert "Read 1 of 2 followed creators" in ctx.note and "1 creator page could not be read" in ctx.note
    assert str(stopped.value) == ctx.note
    assert len(daemon.records.latest(space, "track")) == 1  # the page that loaded still counted


def test_an_unfollowed_creator_is_not_read(daemon: Daemon) -> None:
    space, ctx = setup(daemon)
    follow(daemon, space, QUIET, "Quiet", followed=False)
    ctx.answer("tracks", uploads())
    watch.run(ctx)
    assert ctx.reads == [f"{LUMEN}/videos"]
    assert ctx.of == 1


def test_no_followed_creator_is_skipped_with_nothing_to_do(daemon: Daemon) -> None:
    space = project(daemon)
    follow(daemon, space, QUIET, "Quiet", followed=False)
    ctx = context(daemon, space, "watch")
    with pytest.raises(Skip) as skipped:
        watch.run(ctx)
    assert skipped.value.reason == "nothing_to_do"
    assert ctx.reads == []


def test_the_ceiling_ends_the_run(daemon: Daemon) -> None:
    _, ctx = setup(daemon)
    ctx.at_ceiling = True
    with pytest.raises(CeilingReached):
        watch.run(ctx)


def test_a_signed_out_page_skips_the_run(daemon: Daemon) -> None:
    _, ctx = setup(daemon)
    ctx.page(f"{LUMEN}/videos", "Sign in", signed_out=True)
    with pytest.raises(Skip) as skipped:
        watch.run(ctx)
    assert skipped.value.reason == "signed_out"
