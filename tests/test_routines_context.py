"""A routine's four doors (business Phase 2, WP2.1): `read` a page in a hidden tab with no turn,
`extract` with one tool-less model call on surface routine, `put` through the records' own door, and
`draft` through the twin's web channel."""

from __future__ import annotations

from typing import Any

import pytest

from athena.app import Daemon
from athena.browser import sites
from athena.contracts import RecordKind, Routine
from athena.routines.context import Partial, RunContext, Skip
from athena.twins import web
from browser_kit import ORIGIN, FakeShell, trust
from records_kit import CREATOR, creator, track
from routines_kit import PricedEngine, project

PAGE = f"{ORIGIN}/@lumen/videos"


@pytest.fixture(autouse=True)
def _no_settle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sites, "SETTLE_S", 0.0)


def _ctx(daemon: Daemon, kinds: list[RecordKind] | None = None, engine: Any = None) -> RunContext:
    space = project(daemon, kinds)
    routine: Routine = next(r for r in daemon.routines.ensure_defaults(space) if r["kind"] == "watch")
    built = engine if engine is not None else PricedEngine()
    return RunContext(daemon, space, routine, engine_of=lambda: built)


# --- read -------------------------------------------------------------------------------------------


def test_read_with_no_browser_skips_no_browser(daemon: Daemon) -> None:
    ctx = _ctx(daemon)
    trust(daemon, ctx.space_id)
    with pytest.raises(Skip) as e:
        ctx.read(PAGE)
    assert e.value.reason == "no_browser"


def test_read_gives_the_text_of_a_kept_site_and_closes_its_hidden_tab(daemon: Daemon) -> None:
    ctx = _ctx(daemon)
    trust(daemon, ctx.space_id)
    with FakeShell(daemon.relay) as shell:
        page = ctx.read(PAGE)
    assert (page.url, page.text, page.signed_out) == (PAGE, "Night Drive in Glass", False)
    opened = next(c for c in shell.calls if c["hand"] == "open")
    assert opened["args"] == {"url": PAGE, "hidden": True}
    assert all(t.get("closed") for t in shell.tabs.values())
    assert daemon.conversation.list(ctx.space_id) == []  # no turn: nothing in the conversation


def test_read_carries_the_pages_links_with_their_addresses(daemon: Daemon) -> None:
    """Page text has no addresses; an upload or a thread is only kept with one (found on the built
    shell by the routines seam: four uploads seen, none kept)."""
    ctx = _ctx(daemon)
    trust(daemon, ctx.space_id)
    with FakeShell(daemon.relay) as shell:
        shell.pages[PAGE] = {"links": [f"Night Drive in Glass  {ORIGIN}/watch?v=nd1"]}
        page = ctx.read(PAGE)
    assert page.text.startswith("Night Drive in Glass")
    assert (
        f"Links on the page (label, then address):\nNight Drive in Glass  {ORIGIN}/watch?v=nd1" in page.text
    )


@pytest.mark.parametrize(
    "page",
    [
        {"password": True},  # a password field shows
        {"final": "https://accounts.example/signin?next=videos"},  # it ended on a sign-in host
        {"final": f"{ORIGIN}/login"},  # it ended on the site's own sign-in route
    ],
)
def test_read_of_a_sign_in_page_skips_signed_out(daemon: Daemon, page: dict[str, Any]) -> None:
    ctx = _ctx(daemon)
    trust(daemon, ctx.space_id)
    with FakeShell(daemon.relay) as shell:
        shell.pages[PAGE] = page
        with pytest.raises(Skip) as e:
            ctx.read(PAGE)
    assert e.value.reason == "signed_out" and e.value.note
    assert all(t.get("closed") for t in shell.tabs.values())


def test_read_of_a_site_the_project_does_not_keep_is_partial_and_opens_nothing(daemon: Daemon) -> None:
    ctx = _ctx(daemon)
    with FakeShell(daemon.relay) as shell, pytest.raises(Partial) as e:
        ctx.read(PAGE)
    assert "not one of this project's sites" in str(e.value)
    assert not any(c["hand"] == "open" for c in shell.calls)


class _LongShell(FakeShell):
    """A page whose text comes in three packets, as her browser's hands send a long one."""

    def answer(self, call: dict[str, Any]) -> dict[str, Any]:
        if call["hand"] != "page_read":
            return super().answer(call)
        cursor = call["args"].get("cursor", "")
        if not cursor:
            return {
                "ok": True,
                "output": "cursor: cur_ab_1_5 (chars 1-5 of 15; pass it)\nfirst\n(showing 5 of 15)",
            }
        if cursor == "cur_ab_1_5":
            return {
                "ok": True,
                "output": "cursor: cur_ab_1_10 (chars 6-10 of 15; pass it)\nsecnd\n(showing 5 of 15)",
            }
        return {"ok": True, "output": "chars 11-15 of 15, the end\nthird\n(showing 5 of 15)"}


def test_read_follows_a_long_pages_parts(daemon: Daemon) -> None:
    ctx = _ctx(daemon)
    trust(daemon, ctx.space_id)
    with _LongShell(daemon.relay):
        assert ctx.read(PAGE).text == "first\nsecnd\nthird"


# --- extract ----------------------------------------------------------------------------------------


def test_extract_is_one_tool_less_call_on_surface_routine(daemon: Daemon) -> None:
    engine = PricedEngine(cost=0.02, answer={"items": [{"url": "x"}], "of": 1})
    ctx = _ctx(daemon, engine=engine)
    assert ctx.extract("Find the tracks.", "<<<page>>>", "items") == {"items": [{"url": "x"}], "of": 1}
    assert ctx.spent_usd == pytest.approx(0.02)
    rows = daemon.ledger.page(5, ctx.space_id)["rows"]
    assert [(r["surface"], r.get("cost_usd")) for r in rows] == [("routine", 0.02)]


def test_extract_that_answers_in_another_shape_is_partial(daemon: Daemon) -> None:
    ctx = _ctx(daemon, engine=PricedEngine(answer={"something": "else"}))
    with pytest.raises(Partial):
        ctx.extract("Find the tracks.", "<<<page>>>", "items")


# --- put --------------------------------------------------------------------------------------------


def test_put_keeps_the_finds_at_once_by_the_routine(daemon: Daemon) -> None:
    ctx = _ctx(daemon)
    assert ctx.put("creator", creator()) is not None
    found = ctx.put("track", track())
    assert found is not None and found["by"] == "routine"
    thread = ctx.put(
        "thread",
        {"creator_key": CREATOR, "channel": "mail_web", "last_at": "2026-11-01T12:00:00Z"},
        key="offer",
    )
    assert thread is not None and thread["key"] == "offer"
    stat = ctx.put("stat", {"metric": "views", "value": 12, "measured_at": "2026-11-01T12:00:00Z"})
    assert stat is not None
    assert ctx.put("track", track()) is not None  # the same find again appends nothing
    assert (ctx.kept, ctx.cards) == (4, 0)


def test_put_keeps_the_persons_verdict_on_a_new_find(daemon: Daemon) -> None:
    ctx = _ctx(daemon)
    first = ctx.put("track", track())
    assert first is not None
    daemon.records.verdict(first["id"], {"verdict": "keep", "genre": "synthwave"})
    again = ctx.put("track", track(title="Night Ferry (remaster)"))
    assert again is not None and again["body"]["verdict"] == "keep" and again["body"]["genre"] == "synthwave"


def test_put_of_any_other_kind_files_a_card(daemon: Daemon) -> None:
    ctx = _ctx(daemon)
    ctx.put("creator", creator())
    assert (
        ctx.put(
            "agreement", {"creator_key": CREATOR, "state": "agreed", "thread_key": "offer", "plan": "pro"}
        )
        is None
    )
    assert ctx.cards == 1 and ctx.kept == 1
    cards = daemon.gate.list("waiting")
    assert [(c["action"], c["args"]["kind"]) for c in cards] == [("record_put", "agreement")]
    assert daemon.records.latest(ctx.space_id, "agreement") == []


def test_put_of_a_kind_the_project_does_not_keep_is_refused(daemon: Daemon) -> None:
    ctx = _ctx(daemon, ["creator", "track"])
    assert ctx.put("stat", {"metric": "views", "value": 1, "measured_at": "2026-11-01T12:00:00Z"}) is None
    assert (ctx.kept, ctx.cards, ctx.extra["refused"]) == (0, 0, 1)


# --- draft ------------------------------------------------------------------------------------------


def test_draft_files_the_twins_card_or_answers_none(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _ctx(daemon)
    ctx.put("creator", creator())
    asked: list[dict[str, Any]] = []

    def draft(d: Daemon, engine: Any, space_id: str, channel: str, to: dict[str, Any], *rest: Any) -> Any:
        asked.append({"channel": channel, "to": to, "rest": rest})
        return {"id": "card_000000000001"}

    monkeypatch.setattr(web, "draft", draft)
    assert ctx.draft("mail_web", CREATOR, "offer", "They make synthwave.") == "card_000000000001"
    assert ctx.cards == 1
    assert asked[0]["channel"] == "mail_web" and asked[0]["to"]["name"] == "Lumen"
    assert asked[0]["rest"] == ("offer", "They make synthwave.", None)
    monkeypatch.setattr(web, "draft", lambda *a, **k: None)
    assert ctx.draft("bio", CREATOR, "offer", "") is None and ctx.cards == 1
