"""Shared by the mission tests: a Gmail with threads that takes sends, a fake engine that judges and
drafts as a test tells it, and a live twin made through the routes (set up, rehearsed, gone live).

Nothing here reaches a network: `MissionWorld.answer` is the vault's transport, as `twins_kit.World`'s.
Every send is kept, appended to its thread, and answered as Gmail answers one.
"""

from __future__ import annotations

import base64
import email
import json
from collections.abc import Iterator, Mapping
from email import policy
from typing import Any
from urllib.parse import urlsplit

import pytest

from athena import engine as engine_mod
from athena.engine import TextDelta, ToolCall, Usage
from athena.engine.scripted import ScriptedEngine
from athena.twins.missions import JUDGE_RULES
from athena.twins.rehearse import DRAFT_RULES
from twins_kit import ACCOUNT, World

THEM = "lumen@vale.example"
THREAD = "th0123abcd"
GOAL = "Get Lumen Vale's yes to feature 'Glass Harbor'"
FIRST = "Hi Lumen, I'd love to feature 'Glass Harbor' this Friday with a full visualizer. Up for it?"
REPLY = "You'd get a free visualizer and a credit in the description. Shall I go ahead for Friday?"
ASKED = "Sounds great! What would I get out of it, and would it be exclusive to your channel?"


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def message(
    mid: str, sender: str, to: str, text: str, *, subject: str = "Feature on Friday?"
) -> dict[str, Any]:
    """One message of a Gmail thread, in Gmail's own shape."""
    headers = [
        {"name": "From", "value": sender},
        {"name": "To", "value": to},
        {"name": "Subject", "value": subject},
        {"name": "Date", "value": "Thu, 29 Oct 2026 10:00:00 +0000"},
        {"name": "Message-ID", "value": f"<{mid}@mail.example>"},
    ]
    return {
        "id": mid,
        "payload": {"mimeType": "text/plain", "headers": headers, "body": {"data": _b64(text)}},
    }


def mine(mid: str, text: str) -> dict[str, Any]:
    return message(mid, f"Alex <{ACCOUNT}>", f"Lumen Vale <{THEM}>", text)


def theirs(mid: str, text: str) -> dict[str, Any]:
    return message(mid, f"Lumen Vale <{THEM}>", f"Alex <{ACCOUNT}>", text, subject="Re: Feature on Friday?")


class MissionWorld(World):
    """A World whose Gmail holds threads and takes sends. `send_status` answers every send."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.threads: dict[str, list[dict[str, Any]]] = {}
        self.sent: list[dict[str, Any]] = []
        self.send_status = 200

    def answer(self, method: str, address: str, headers: Mapping[str, str], body: bytes | None) -> Any:
        path = urlsplit(address).path
        if urlsplit(address).hostname == "gmail.googleapis.com":
            if method == "GET" and "/threads/" in path:
                tid = path.rsplit("/", 1)[-1]
                if tid not in self.threads:
                    return 404, {"error": {"message": "not found"}}
                return 200, {"id": tid, "messages": self.threads[tid]}
            if method == "POST" and path.endswith("/messages/send"):
                if self.send_status >= 300:
                    return self.send_status, {"error": {"message": "refused"}}
                payload = json.loads(body or b"{}")
                raw = base64.urlsafe_b64decode(payload["raw"] + "=" * (-len(payload["raw"]) % 4))
                sent = email.message_from_bytes(raw, policy=policy.default)
                text = str(sent.get_content()).strip()  # type: ignore[attr-defined]
                tid = payload.get("threadId") or f"thnew{len(self.sent)}"
                mid = f"sent{len(self.sent)}"
                self.sent.append(
                    {
                        "thread": payload.get("threadId", ""),
                        "to": str(sent["To"]),
                        "subject": str(sent["Subject"]),
                        "in_reply_to": str(sent["In-Reply-To"] or ""),
                        "text": text,
                    }
                )
                self.threads.setdefault(tid, []).append(mine(mid, text))
                return 200, {"id": mid, "threadId": tid}
        return super().answer(method, address, headers, body)

    def they_write(self, thread: str, text: str) -> None:
        msgs = self.threads.setdefault(thread, [])
        msgs.append(theirs(f"them{len(msgs)}", text))


class MissionEngine:
    """Judges and drafts a mission as the test says: `judge` and `draft` are the JSON it answers to
    each once the twin is live; until then (the setup, the rehearsal) it is the scripted engine."""

    id = "scripted"
    model = "scripted"
    simulated = True
    cost_estimated = False

    def __init__(self) -> None:
        self.judge: dict[str, Any] = {"state": "open", "note": "They asked two questions.", "confidence": 90}
        self.draft: dict[str, Any] = {"text": REPLY, "confidence": 91, "risks": []}
        self.calls: list[str] = []
        self.live = False  # until the twin is live, every call is the scripted engine's

    def probe(self) -> dict[str, Any]:
        return {"ok": True}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        if not self.live:
            yield from ScriptedEngine().complete(messages, tools)
            return
        system = str(messages[0]["content"])
        if JUDGE_RULES in system:
            self.calls.append("judge")
            answer = self.judge
        elif DRAFT_RULES in system:
            self.calls.append("draft")
            answer = self.draft
        else:
            raise AssertionError("a call a mission never makes")
        yield TextDelta(json.dumps(answer))
        yield Usage(input_tokens=10, output_tokens=5)


def live_twin(world: MissionWorld, engine: MissionEngine | None = None) -> str:
    """A twin set up as the prototype stages it, rehearsed once on the scripted engine, gone live:
    Gmail first messages on Assist, replies on Auto at 80; Notion on Auto at 60."""
    twin_id = world.create()
    world.play(twin_id)
    world.stream(twin_id, "twin_rehearse", {"goal": GOAL})
    assert world.post(twin_id, "twin_golive")["state"] == "live"
    if engine is not None:
        engine.live = True
    return twin_id


def use(monkeypatch: pytest.MonkeyPatch, engine: MissionEngine) -> None:
    """Every route that builds an engine gets this one."""
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: engine)
