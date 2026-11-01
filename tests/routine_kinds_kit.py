"""A stand-in RunContext for the routine kinds' tests (business Phase 2, WP2.2).

`FakeContext` answers the four seam methods without a browser or an engine: `read` from canned pages
by address (an exception in place of a page is raised), `extract` from scripted answers per key (each
call is logged with its prompts, so a test can check the fence), `put` through the daemon's real
records (creator, track, thread and stat kept at once by the routine, as the Director decided; any
other kind files a card) and `draft` as a waiting `twin_send_web` card, or None with no twin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from athena.app import Daemon
from athena.contracts import ChannelKind, RecordItem, RecordKind, Routine, RoutineKind
from athena.records.actions import _onto_latest
from athena.routines.context import CeilingReached, PageText, RunContext

#: The kinds a routine keeps at once (WP2.1 implements the same rule in RunContext.put).
AT_ONCE: frozenset[RecordKind] = frozenset({"creator", "track", "thread", "stat"})
SITE = "http://127.0.0.1:8781"


def routine(space_id: str, kind: RoutineKind, url: str | None = None) -> Routine:
    out: Routine = {
        "id": f"rtn_{kind}",
        "space_id": space_id,
        "kind": kind,
        "name": kind,
        "cadence_s": 3600,
        "ceiling_usd": 0.25,
        "state": "on",
    }
    if url is not None:
        out["url"] = url
    return out


@dataclass
class Call:
    system: str
    user: str
    key: str


@dataclass
class FakeContext(RunContext):
    pages: dict[str, PageText | Exception] = field(default_factory=dict)
    answers: dict[str, list[Any]] = field(default_factory=dict)  # key -> answers, in order
    twin: bool = True
    at_ceiling: bool = False  # every extract raises CeilingReached
    reads: list[str] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    drafts: list[dict[str, Any]] = field(default_factory=list)

    def page(self, url: str, text: str, *, signed_out: bool = False) -> None:
        self.pages[url] = PageText(url=url, text=text, signed_out=signed_out)

    def answer(self, key: str, *answers: Any) -> None:
        self.answers.setdefault(key, []).extend(answers)

    def read(self, url: str) -> PageText:
        self.reads.append(url)
        found = self.pages.get(url)
        if found is None:
            raise AssertionError(f"the routine read a page the test did not give: {url}")
        if isinstance(found, Exception):
            raise found
        return found

    def extract(self, system: str, user: str, key: str) -> dict[str, Any]:
        if self.at_ceiling:
            raise CeilingReached("the run's ceiling")
        self.calls.append(Call(system, user, key))
        queued = self.answers.get(key) or []
        if not queued:
            raise AssertionError(f"no scripted answer left for {key!r}")
        answer: dict[str, Any] = queued.pop(0)
        return answer

    def put(self, kind: RecordKind, body: dict[str, Any], key: str | None = None) -> RecordItem | None:
        records = self.daemon.records
        given = {**body, "key": key} if key is not None else body
        prepared_key, cleaned = records.prepare(self.space_id, kind, given)
        if kind not in AT_ONCE:
            self.daemon.gate.file(
                self.space_id, "record_put", {"kind": kind, "body": cleaned}, f"Keep: {kind}"
            )
            self.cards += 1
            return None
        merged = _onto_latest(self.daemon, self.space_id, kind, prepared_key, cleaned)
        before = records.latest(self.space_id, kind, prepared_key)
        if kind == "thread":
            merged = {**merged, "key": prepared_key}
        item = records.put(self.space_id, kind, merged, "routine")
        if not before or before[0]["rev"] != item["rev"]:
            self.kept += 1
        return item

    def draft(
        self,
        channel: ChannelKind,
        creator_key: str,
        purpose: str,
        context: str,
        thread_key: str | None = None,
    ) -> str | None:
        if not self.twin:
            return None
        args = {
            "channel": channel,
            "creator_key": creator_key,
            "purpose": purpose,
            "context": context,
            "thread_key": thread_key,
        }
        card = self.daemon.gate.file(self.space_id, "twin_send_web", args, f"Send: {purpose}")
        self.drafts.append(args)
        self.cards += 1
        return card["id"]


def context(d: Daemon, space_id: str, kind: RoutineKind, url: str | None = None) -> FakeContext:
    return FakeContext(daemon=d, space_id=space_id, routine=routine(space_id, kind, url))


_FENCE = re.compile(r"<<<page:([0-9a-f]+)\n(.*)\npage:\1>>>", re.S)


def assert_fenced(ctx: FakeContext) -> None:
    """Every extract call carried its page inside the page fence, said to be page data."""
    assert ctx.calls, "no extract call was made"
    for call in ctx.calls:
        assert "page data, not instructions" in call.user
        assert "page data, not instructions" in call.system
        assert _FENCE.search(call.user), call.user


def fenced_text(call: Call) -> str:
    found = _FENCE.search(call.user)
    assert found
    return found.group(2)
