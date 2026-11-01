"""The fixture's business pages (business Phase 2, WP2.2), served on a free port: every new page
answers 200 under the simulated banner; a new upload appears after its POST; a reply and a composed
message land in the journal's `sent`; the locked inbox asks to sign in first."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import pytest

from athena.browser import fixture


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_: object, **__: object) -> None:
        return None


@pytest.fixture
def site() -> Iterator[tuple[str, fixture.Journal]]:
    server, journal = fixture.serve(0)
    yield f"http://127.0.0.1:{server.server_address[1]}", journal
    _stop(server)


def _stop(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


def get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as r:
        assert r.status == 200
        return str(r.read().decode("utf-8"))


def post(url: str, form: dict[str, str] | None = None) -> int:
    data = urlencode(form or {}).encode()
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, data=data, method="POST"), timeout=5) as r:
            return int(r.status)
    except urllib.error.HTTPError as e:
        return int(e.code)


def test_every_new_page_answers_under_the_banner(site: tuple[str, fixture.Journal]) -> None:
    base, _ = site
    pages = [
        *(f"/channel/{h}/videos" for h, _, _ in fixture.CREATORS),
        f"/@{fixture.CREATORS[1][0]}/videos",
        "/mail",
        "/mail/m1",
        "/mail/new",
        "/studio/analytics",
        "/",
    ]
    for path in pages:
        text = get(base + path)
        assert "Simulated test page - not a real site" in text, path
        assert "not YouTube" not in text


def test_the_pages_say_what_the_routines_read(site: tuple[str, fixture.Journal]) -> None:
    base, _ = site
    videos = get(f"{base}/channel/lumen-tide-sim/videos")
    assert "Glass Harbour (simulated)" in videos and "Published 2026-10-28" in videos
    inbox = get(f"{base}/mail")
    for _, _, address in fixture.CREATORS:
        assert address in inbox
    assert fixture.STRANGER_EMAIL in inbox and "1 Nov 2026, 09:12 UTC" in inbox
    thread = get(f"{base}/mail/m1")
    assert 'aria-label="Reply"' in thread and ">Send</button>" in thread
    analytics = get(f"{base}/studio/analytics")
    assert all(label in analytics for label, _ in fixture.ANALYTICS)
    assert f"Last updated {fixture.ANALYTICS_CLAIMED}" in analytics


def test_a_new_upload_appears_after_its_post(site: tuple[str, fixture.Journal]) -> None:
    base, _ = site
    title = fixture.NEW_UPLOAD[1]
    assert title not in get(f"{base}/channel/lumen-tide-sim/videos")
    assert post(f"{base}/fixture/new-upload") == 200
    assert title in get(f"{base}/channel/lumen-tide-sim/videos")
    assert title not in get(f"{base}/channel/paper-orbit-sim/videos")
    assert title in get(f"{base}/watch?v={fixture.NEW_UPLOAD[0]}")


def test_a_reply_lands_in_the_journal_and_the_thread(site: tuple[str, fixture.Journal]) -> None:
    base, journal = site
    assert post(f"{base}/mail/m1/reply", {"body": "Here are our terms."}) == 303
    sent = journal.snapshot()["sent"]
    assert sent == [
        {
            "thread": "m1",
            "to": fixture.CREATORS[0][2],
            "subject": fixture.THREADS["m1"]["subject"],
            "text": "Here are our terms.",
        }
    ]
    assert "Here are our terms." in get(f"{base}/mail/m1")
    state = json.loads(get(f"{base}/state"))
    assert state["sent"] == sent


def test_a_composed_message_lands_in_the_journal(site: tuple[str, fixture.Journal]) -> None:
    base, journal = site
    assert post(f"{base}/mail/new", {"to": "a@x.example", "subject": "Hello", "body": "An offer"}) == 302
    assert journal.snapshot()["sent"] == [{"to": "a@x.example", "subject": "Hello", "text": "An offer"}]


def test_a_new_reply_moves_its_thread(site: tuple[str, fixture.Journal]) -> None:
    base, journal = site
    assert post(f"{base}/fixture/new-reply?thread=m2") == 200
    last = journal.snapshot()["threads"]["m2"]["messages"][-1]
    assert last[0] == fixture.CREATORS[1][2] and last[1] > "2026-11-01"
    assert post(f"{base}/fixture/new-reply?thread=nope") == 404


def test_the_locked_inbox_asks_to_sign_in(site: tuple[str, fixture.Journal]) -> None:
    base, _ = site
    opener = urllib.request.build_opener(_NoRedirect)
    with pytest.raises(urllib.error.HTTPError) as moved:
        opener.open(f"{base}/mail?locked=1", timeout=5)
    assert moved.value.code == 302
    assert moved.value.headers["Location"] == "/signin?next=/mail?locked=1"
