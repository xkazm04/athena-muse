"""A fake shell for her browser: answers the relay the way the desktop does, over in-memory tabs."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from athena.browser.relay import Relay

ORIGIN = "http://127.0.0.1:8781"


class FakeShell:
    """Polls `relay.next` on a thread. Each tab is `{url, title, load, text, links}`; `page_find`
    answers from `controls`, `page_click` on a ref in `navigates` moves the tab to that url."""

    def __init__(self, relay: Relay) -> None:
        self.relay = relay
        self.tabs: dict[int, dict[str, Any]] = {}
        self.calls: list[dict[str, Any]] = []
        self.refuse: dict[str, dict[str, Any]] = {}  # hand -> the answer to give instead
        self.download_bytes = b"RIFF simulated wav"
        # url -> {"final": where the page ends after its redirects, "password": a password field shows}
        self.pages: dict[str, dict[str, Any]] = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def __enter__(self) -> FakeShell:
        self._thread.start()
        for _ in range(200):
            if self.relay.connected():
                break
            threading.Event().wait(0.005)
        return self

    def __exit__(self, *_: Any) -> None:
        self._stop.set()
        self._thread.join(2)

    def _loop(self) -> None:
        while not self._stop.is_set():
            call = self.relay.next(0.05)
            if call is not None:
                self.calls.append(call)
                self.relay.done(call["id"], self.answer(call))

    def info(self, tab: int) -> dict[str, Any]:
        t = self.tabs[tab]
        return {"id": tab, "url": t["url"], "title": t["title"], "load": t["load"]}

    def answer(self, call: dict[str, Any]) -> dict[str, Any]:
        hand, args = call["hand"], call["args"]
        if hand in self.refuse:
            return self.refuse[hand]
        if hand == "open":
            tab = len(self.tabs) + 1
            page = self.pages.get(args["url"], {})
            self.tabs[tab] = {
                "url": page.get("final", args["url"]),
                "title": "A page",
                "load": 1,
                "text": "Night Drive in Glass",
                "password": page.get("password", False),
                "links": page.get("links", []),
                "hidden": bool(args.get("hidden")),
            }
            return {"ok": True, "output": f"opened tab {tab}", "tab": self.info(tab)}
        if hand == "tabs":
            return {"ok": True, "output": "\n".join(f"tab {t}  {v['url']}" for t, v in self.tabs.items())}
        tab = call.get("tab")
        if tab not in self.tabs:
            return {"ok": False, "reason": "no_tab", "output": "that tab is not open"}
        now = self.info(tab)
        if ("load" in call and call["load"] != now["load"]) or ("url" in call and call["url"] != now["url"]):
            return {"ok": False, "reason": "moved", "output": "the page has changed since this was asked"}
        if hand == "tab":
            return {"ok": True, "output": f"tab {tab}", "tab": now}
        if hand == "page_read":
            return {"ok": True, "output": self.tabs[tab]["text"], "tab": now}
        if hand == "page_links":
            links = self.tabs[tab].get("links") or []
            return {"ok": True, "output": "\n".join(links) if links else "no links", "tab": now}
        if hand == "page_find" and args.get("role") == "password":
            found = "ref_p_1  password  Password\n(showing 1 of 1)" if self.tabs[tab]["password"] else ""
            return {"ok": True, "output": found or "nothing matched", "tab": now}
        if hand == "close":
            self.tabs[tab]["closed"] = True
            return {"ok": True, "output": f"closed tab {tab}"}
        if hand == "page_find":
            return {"ok": True, "output": "ref_a_1  button  Comment\n(showing 1 of 1)", "tab": now}
        if hand == "page_click":
            self.tabs[tab]["load"] += 1
            return {"ok": True, "output": "clicked Comment", "tab": now}
        if hand == "download":
            target = Path(args["dir"]) / f"{call['id']}-track.wav"
            target.write_bytes(self.download_bytes)
            return {
                "ok": True,
                "output": "downloaded track.wav",
                "file": {"path": str(target), "name": "track.wav"},
            }
        if hand == "upload":
            data = Path(args["file"]["path"]).read_bytes()
            return {
                "ok": True,
                "output": f"gave the page {args['file']['name']} ({len(data)} bytes)",
                "measured": {"bytes": len(data), "parts": 1, "staged_ms": 1, "total_ms": 2},
            }
        return {"ok": True, "output": f"{hand} done", "tab": now}


def trust(daemon: Any, space_id: str, origin: str = ORIGIN, access: str = "signed_in") -> None:
    """Makes `origin` one of the project's sites, as a chore's onboarding would (ADR 0014), and
    stores a fresh look at it, so no hand looks again before acting."""
    daemon.sites.add(space_id, origin, "Fixture", f"{origin}/account", "A test chore")
    daemon.sites.looked(space_id, origin, access, "set up by the test")
