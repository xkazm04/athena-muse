"""Shared by the web channel tests: a live twin on a project with the web channels, a fake engine that
answers a twin's draft and keeps what it was asked, and a fake shell whose pages hold labelled controls.

Nothing here reaches a network. `WebShell` answers her browser's hands the way `hands.js` does: a
`page_find` lists each control whose label contains the query as `ref  role  label`, a fill or a click
is refused with `moved` when the page has left the load it was found on, and a click on a control in
`navigates` takes the tab to another page.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from athena.app import Daemon
from athena.browser.relay import Relay
from athena.engine import TextDelta, Usage
from athena.twins import setup
from browser_kit import ORIGIN, FakeShell, trust

MAILBOX = "http://127.0.0.1:8790"  # the simulated business mailbox, one of the project's sites
COMPOSE = f"{MAILBOX}/mail/new"
INBOX = f"{MAILBOX}/mail"
THREAD_URL = f"{MAILBOX}/mail/thread/t1"
TRACK_URL = "https://www.youtube.com/watch?v=t1"
BIO_URL = "https://linktr.ee/miravale"
ADDRESS = "mira.vale@example.com"

CREATOR: dict[str, Any] = {
    "name": "Mira Vale",
    "channel_url": "https://www.youtube.com/@miravale",
    "followed": True,
    "bio_links": [BIO_URL],
    "emails": [ADDRESS],
}
TRACK: dict[str, Any] = {
    "url": TRACK_URL,
    "title": "Night Drive in Glass",
    "creator_key": "https://www.youtube.com/@miravale",
    "found_at": "2026-11-01T10:00:00Z",
}
DRAFTED = "Hi Mira, 'Night Drive in Glass' has been on repeat here. Would you be open to a visualizer?"

#: The controls a page shows, by its address: (role, label).
PAGES: dict[str, list[tuple[str, str]]] = {
    COMPOSE: [("email", "To"), ("textbox", "Subject"), ("textbox", "Message"), ("button", "Send")],
    INBOX: [("button", "New message"), ("link", "Today's mail")],
    THREAD_URL: [("button", "Reply"), ("button", "Forward")],
    f"{THREAD_URL}#reply": [("textbox", "Reply"), ("button", "Send"), ("button", "Send later")],
    TRACK_URL: [("textbox", "Add a comment"), ("button", "Comment"), ("button", "Cancel")],
    BIO_URL: [("link", "Email Mira"), ("link", "Instagram")],
}
#: A click that takes the tab to another page: (page, label) -> the page it lands on.
NAVIGATES: dict[tuple[str, str], str] = {
    (THREAD_URL, "Reply"): f"{THREAD_URL}#reply",
    (INBOX, "New message"): COMPOSE,
}


class WebShell(FakeShell):
    """A fake shell over pages of labelled controls. `acts` keeps every fill and click, in order, as
    (hand, page, label, value)."""

    def __init__(self, relay: Relay) -> None:
        super().__init__(relay)
        self.controls: dict[str, list[tuple[str, str]]] = {k: list(v) for k, v in PAGES.items()}
        self.navigates = dict(NAVIGATES)
        self.acts: list[tuple[str, str, str, str]] = []
        self._refs: dict[str, tuple[int, int, str]] = {}  # ref -> (tab, load, label)

    def answer(self, call: dict[str, Any]) -> dict[str, Any]:
        hand, args = call["hand"], call["args"]
        if hand in self.refuse or hand not in ("page_find", "page_fill", "page_click"):
            return super().answer(call)
        tab = call.get("tab")
        if tab not in self.tabs:
            return {"ok": False, "reason": "no_tab", "output": "that tab is not open"}
        page = self.tabs[tab]
        if ("load" in call and call["load"] != page["load"]) or (
            "url" in call and call["url"] != page["url"]
        ):
            return {"ok": False, "reason": "moved", "output": "the page has changed since this was asked"}
        if hand == "page_find":
            query = str(args.get("query", "")).lower()
            rows = []
            for i, (role, label) in enumerate(self.controls.get(page["url"], [])):
                if query in label.lower():
                    ref = f"ref_{tab}{page['load']}_{i}"
                    self._refs[ref] = (tab, page["load"], label)
                    rows.append(f"{ref}  {role}  {label}")
            if not rows:
                return {"ok": True, "output": "nothing matched"}
            return {"ok": True, "output": "\n".join([*rows, f"(showing {len(rows)} of {len(rows)})"])}
        held = self._refs.get(str(args.get("ref")))
        if held is None or held[:2] != (tab, page["load"]):
            return {
                "ok": False,
                "reason": "unknown_ref",
                "output": "that ref belongs to a page that has been left",
            }
        label = held[2]
        if args.get("expect") and args["expect"].lower() != label.lower():
            return {"ok": False, "reason": "moved", "output": f'that element now reads "{label}"'}
        if hand == "page_fill":
            self.acts.append(("fill", page["url"], label, str(args.get("value", ""))))
            return {"ok": True, "output": f"filled {label}"}
        self.acts.append(("click", page["url"], label, ""))
        moved = self.navigates.get((page["url"], label))
        if moved is not None:
            page["url"] = moved
        page["load"] += 1
        return {"ok": True, "output": f"clicked {label}"}


class DraftEngine:
    """Answers every call with one twin draft and keeps the messages it was given."""

    id = "scripted"
    model = "scripted"
    simulated = True
    cost_estimated = False

    def __init__(self, text: str = DRAFTED, **extra: Any) -> None:
        self.answer = {"text": text, "confidence": 81, "risks": [], **extra}
        self.asked: list[list[dict[str, Any]]] = []

    def probe(self) -> dict[str, Any]:
        return {"ok": True, "model": "scripted", "latency_ms": 0}

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[Any]:
        self.asked.append(messages)
        yield TextDelta(json.dumps(self.answer))
        yield Usage(input_tokens=100, output_tokens=20)


def piece(kind: str, *, confirmed: bool = True) -> dict[str, Any]:
    origin = "you" if confirmed else "athena"
    label = setup.CHANNEL_LABELS[kind]
    return {
        "id": f"ch-{kind}",
        "kind": kind,
        "slot": "channels",
        "label": label,
        "origin": origin,
        "confirmed": confirmed,
    }


def web_twin(
    daemon: Daemon,
    kinds: tuple[str, ...] = ("mail_web", "bio", "comment"),
    *,
    state: str = "live",
    space_id: str | None = None,
) -> tuple[str, str]:
    """(space_id, twin_id): a twin holding `kinds`, inked, its channels open, at `state`."""
    space = space_id or daemon.spaces.create({"name": "Night Drive Visuals"})["id"]
    twin_id = daemon.twins.create(space)
    sketch: Any = {"nodes": [piece(k) for k in kinds], "edges": []}
    daemon.twins.put(twin_id, sketch=sketch, state=state)  # type: ignore[arg-type]
    setup.sync(daemon, twin_id)
    return space, twin_id


def mailbox(daemon: Daemon, space_id: str, access: str = "signed_in") -> None:
    """The project keeps the simulated mailbox among its sites, looked at just now."""
    daemon.sites.add(space_id, MAILBOX, "Proton Mail (simulated)", INBOX, "Business mail")
    daemon.sites.looked(space_id, MAILBOX, access, "set up by the test")  # type: ignore[arg-type]


def thread(daemon: Daemon, space_id: str, subject: str = "Your track 'Night Drive in Glass'") -> str:
    """A kept conversation with Mira on the mailbox; answers its key."""
    body = {
        "key": "mira-offer",
        "creator_key": CREATOR["channel_url"],
        "channel": "mail_web",
        "last_at": "2026-11-01T09:00:00Z",
        "subject": subject,
        "url": THREAD_URL,
    }
    return str(daemon.records.put(space_id, "thread", body, "routine")["key"])


__all__ = ["ORIGIN", "trust"]
