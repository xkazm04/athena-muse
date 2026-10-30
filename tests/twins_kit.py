"""Shared by the twin tests: a fake Gmail and Notion behind the real vault, a daemon over them, and the
prototype's staged setup played through the routes on the scripted engine.

Nothing here reaches a network: `FakeProvider` is the vault's transport. The sent mail is invented and
long enough that a stored excerpt is visibly shorter than the mail itself.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from starlette.testclient import TestClient

from athena.app import Daemon
from athena.contracts import ROUTES
from connectors_kit import ACCOUNT, NOTION_KEY, FakeProvider, Seen, connectors_over

__all__ = [
    "ACCOUNT",
    "FRAMES",
    "INBOX_PAGE",
    "NEED",
    "PAGES",
    "SENT",
    "World",
    "events",
    "prototype",
    "url",
]

PROTOTYPE = Path(__file__).resolve().parents[1] / "docs/concepts/twin-module/prototypes/shared/twin-data.json"
NEED = (
    "I want a twin that writes to Suno creators whose tracks I'd like to feature on my channel, and keeps "
    "each conversation going until we agree."
)
TAIL = " ".join(["I keep a running list of tracks I love and I write to the people behind them."] * 6)

# (id, To, subject, date, the person's own words). The last two are a forward and team mail.
SENT = (
    (
        "s1",
        "Mira Soleil <mira@soleil.example>",
        "Your track 'Salt Lines'",
        "Tue, 03 Mar 2026 10:00:00 +0000",
        "Hi Mira, 'Salt Lines' has been on repeat here since Tuesday; that bridge at 2:10 is something else. "
        + TAIL,
    ),
    (
        "s2",
        "Odd Weather <hello@oddweather.example>",
        "Re: visualizer draft",
        "Tue, 19 May 2026 10:00:00 +0000",
        "Hey! Glad you liked it. I can push the colour a bit warmer and send a new cut by Thursday. "
        "Does that work?",
    ),
    (
        "s3",
        "Kite & Copper <band@kitecopper.example>",
        "Feature on Friday?",
        "Thu, 02 Jul 2026 10:00:00 +0000",
        "Hi both, I'd love to feature 'Low Orbit' this Friday with a full visualizer. "
        "Would you be up for it?",
    ),
    (
        "s4",
        "Juno Park <juno@park.example>",
        "Re: credits",
        "Fri, 21 Aug 2026 10:00:00 +0000",
        "All sorted, your name and link are in the description now. "
        "Thanks again for letting me use it. cheers",
    ),
    (
        "s5",
        "Marlow <marlow@ledger.example>",
        "Fwd: invoice",
        "Thu, 11 Jun 2026 10:00:00 +0000",
        "See below. Can you check this?",
    ),
    (
        "s6",
        "Team <team@example.test>",
        "Weekly notes",
        "Wed, 30 Sep 2026 10:00:00 +0000",
        "Notes for the week: render queue, the Friday feature, invoices.",
    ),
)
# (id, object, title). Notion ids are 32 hex characters.
PAGES = (
    ("a" * 32, "page", "Partnership offer"),
    ("b" * 32, "page", "Channel stats"),
    ("c" * 32, "database", "Track shortlist"),
    ("d" * 32, "page", "Journal"),
    ("9" * 32, "page", "Twin inbox"),
)
INBOX_PAGE = "9" * 32
PRACTICE_PAGE = "e" * 32


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def _mail(mail_id: str, to: str, subject: str, date: str, text: str) -> dict[str, Any]:
    quoted = "\n\nOn Mon, 2 Mar 2026, someone wrote:\n> an earlier message the person did not write"
    headers = [
        {"name": "From", "value": f"Me <{ACCOUNT}>"},
        {"name": "To", "value": to},
        {"name": "Subject", "value": subject},
        {"name": "Date", "value": date},
    ]
    return {
        "id": mail_id,
        "snippet": text[:40],
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": headers,
            "parts": [{"mimeType": "text/plain", "body": {"data": _b64(text + quoted)}}],
        },
    }


class World:
    """A daemon whose Gmail and Notion are fakes. `connect_gmail` and `connect_notion` admit a
    credential the way a finished sign-in or a pasted key does."""

    def __init__(self, daemon: Daemon, client: TestClient, *, notion_create: int = 200) -> None:
        self.daemon = daemon
        self.client = client
        self.notion_create = notion_create
        self.provider = FakeProvider(script=self.answer)
        daemon.connectors = connectors_over(None, self.provider)

    # -- the fakes ----------------------------------------------------------------------------------

    def answer(self, method: str, address: str, headers: Mapping[str, str], body: bytes | None) -> Any:
        parts = urlsplit(address)
        path = parts.path
        if parts.hostname == "api.notion.com":
            if path == "/v1/users/me":
                return 200, {"id": "0123456789abcdef0123456789abcdef", "name": "Low Tide studio"}
            if path == "/v1/search":
                results = [
                    {
                        "object": kind,
                        "id": pid,
                        "properties": {"title": {"type": "title", "title": [{"plain_text": t}]}},
                    }
                    for pid, kind, t in PAGES
                ]
                return 200, {"results": results}
            if path == "/v1/pages" and method == "POST":
                return self.notion_create, {"id": PRACTICE_PAGE}
            if path.startswith("/v1/blocks/") and method == "PATCH":
                return 200, {"results": []}
            return 404, {"message": "not found"}
        if path.endswith("/profile"):
            return 200, {"emailAddress": ACCOUNT}
        if path.endswith("/messages") and method == "GET":
            assert parse_qs(parts.query)["q"] == ["in:sent"]
            return 200, {"messages": [{"id": m[0]} for m in SENT]}
        for mail in SENT:
            if path.endswith(f"/messages/{mail[0]}"):
                return 200, _mail(*mail)
        return 404, {"error": {"message": "not found"}}

    def connect_gmail(self) -> None:
        vault = self.daemon.connectors.vault
        vault._admit(
            vault.specs["gmail"], "ya29.test_access", refresh="1//r", expires_in=3600, client=("c", "s")
        )

    def connect_notion(self) -> None:
        self.daemon.connectors.vault.connect_token("notion", NOTION_KEY)

    def seen(self, host: str, method: str | None = None) -> list[Seen]:
        return [
            s for s in self.provider.seen if urlsplit(s.url).hostname == host and method in (None, s.method)
        ]

    # -- the routes ---------------------------------------------------------------------------------

    def create(self) -> str:
        space = self.client.post(ROUTES["spaces"], json={"name": "Partnerships"}).json()["id"]
        r = self.client.post(ROUTES["twins"], json={"space_id": space})
        assert r.status_code == 201, r.text
        return str(r.json()["id"])

    def post(self, twin_id: str, key: str, body: Any = None, status: int = 200) -> dict[str, Any]:
        r = self.client.post(url(key, twin_id), json=body if body is not None else {})
        assert r.status_code == status, r.text
        return r.json()  # type: ignore[no-any-return]

    def get(self, twin_id: str) -> dict[str, Any]:
        r = self.client.get(url("twin", twin_id))
        assert r.status_code == 200, r.text
        return r.json()  # type: ignore[no-any-return]

    def say(self, twin_id: str, text: str = "", choice: str | None = None) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"text": text}
        if choice is not None:
            body["choice"] = choice
        r = self.client.post(url("twin_say", twin_id), json=body)
        assert r.status_code == 200, r.text
        return events(r.text)

    def stream(self, twin_id: str, key: str, body: Any) -> list[dict[str, Any]]:
        r = self.client.post(url(key, twin_id), json=body)
        assert r.status_code == 200, r.text
        return events(r.text)

    def pieces(self, twin_id: str, prefix: str) -> list[str]:
        return [p["id"] for p in self.get(twin_id)["pieces"] if p["id"].startswith(prefix)]

    # -- the prototype's staged setup ---------------------------------------------------------------

    def play(self, twin_id: str, frames: int = 12) -> list[dict[str, Any]]:
        """Plays the staged answers frame by frame, as the person would: the slip first, then the
        answer, then her proposals they ink. Answers the twin after each frame."""
        after: list[dict[str, Any]] = []
        steps = [
            lambda: self.say(twin_id, NEED),
            lambda: (
                self.say(twin_id, choice="As Alex from Low Tide Visuals"),
                self.confirm(twin_id, ["p_name"]),
            ),
            lambda: (self.connect_gmail(), self.say(twin_id, choice="Sign in with Google")),
            lambda: (
                self.post(twin_id, "twin_samples", {"ids": ["s1", "s2", "s3", "s4"]}),
                self.say(twin_id, choice="The ones you marked"),
            ),
            lambda: (
                self.confirm(twin_id, self.pieces(twin_id, "v-")),
                self.say(twin_id, choice="A little more formal at first contact"),
            ),
            lambda: (self.connect_notion(), self.say(twin_id, choice="I've pasted it")),
            lambda: (
                self.post(twin_id, "twin_pages", {"ids": [p[0] for p in PAGES[:3]]}),
                self.say(twin_id, choice="The ones you marked"),
            ),
            lambda: (
                self.post(twin_id, "twin_chores", {"ids": ["file-outcome", "task-inbox", "practice-page"]}),
                self.say(twin_id, choice="All it can run"),
            ),
            lambda: (
                self.confirm(twin_id, ["p_n0", "p_n1", "p_n2", "p_n3"]),
                self.say(twin_id, choice="Also: never write after 9 pm their time"),
            ),
            lambda: (
                self.post(
                    twin_id,
                    "twin_autonomy",
                    {
                        "channel": "gmail",
                        "autonomy": "auto",
                        "bar": 80,
                        "split": {"first_message": "assist", "reply": "auto"},
                    },
                ),
                self.post(twin_id, "twin_autonomy", {"channel": "notion", "autonomy": "auto", "bar": 60}),
                self.say(twin_id, choice="First message Assist, replies Auto"),
            ),
            lambda: (
                self.post(twin_id, "twin_memory", {"id": "f1", "keep": True}),
                self.post(twin_id, "twin_memory", {"id": "f2", "keep": True}),
                self.say(twin_id, choice="Yes to the ones you marked"),
            ),
            lambda: (
                self.confirm(twin_id, ["p_mtype"]),
                self.say(twin_id, choice="Get Lumen Vale's yes to feature 'Glass Harbor'"),
            ),
        ]
        for step in steps[:frames]:
            step()
            after.append(self.get(twin_id))
        return after

    def confirm(self, twin_id: str, pieces: list[str]) -> dict[str, Any]:
        return self.post(twin_id, "twin_confirm", {"pieces": pieces})


def url(key: str, twin_id: str) -> str:
    return ROUTES[key].format(id=twin_id)


def events(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def prototype() -> dict[str, Any]:
    return json.loads(PROTOTYPE.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


FRAMES = prototype()["setup"]["frames"]
