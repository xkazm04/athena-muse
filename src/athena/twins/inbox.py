"""The task inbox (the `task-inbox` preset): new missions the person writes on a Notion page.

While the daemon runs, the poller reads the page each live twin with the preset picked has chosen (a
page the twin may read) and takes each new line of the form "<who or thread>: <goal>":

- who: one address (the newest recent conversation with them, else a first message to them), the id
  of one of its recent Gmail conversations, or a name or subject that names exactly one of them;
- goal: the person's own words, as the mission's goal.

Each line is taken once (known by its block and by its words) and starts a mission (`source: notion`)
that the same pass of the poller works. A line it cannot place is left alone and reported on the twin
with why; the report is the last read's, so a line placed later leaves it. Lines not of that form are
not tasks and are passed over.

It writes nothing to the page but one short "Taken:" note per line it took, ruled by `decide()` on the
Notion channel: written at once when the rule lets it go alone, else a `twin_note` card the person
signs. The note is the code's own words, never a model's, so it is as sure as a note can be; the
channel's level still decides. Its own notes are never read back as tasks.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from athena.app import Daemon
from athena.clock import mint, now_iso
from athena.connectors.addresses import one_address
from athena.contracts import DETAIL_MAX, LABEL_MAX
from athena.errors import ApiError
from athena.twins import missions
from athena.twins.catalogue import INBOX
from athena.twins.decide import DraftFacts, decide, level
from athena.twins.reach import Unreachable, page_lines
from athena.twins.setup import cut
from athena.twins.threads import Recent, plain_subject, recent

log = logging.getLogger(__name__)

TAKEN = "Taken:"  # how its own notes begin
UNPLACED_MAX = 10  # lines one report names
NAME_MIN = 3  # the fewest letters a name or subject is matched on in part
_LINE = re.compile(r"^(?P<who>[^:]{1,120}):\s*(?P<goal>\S.*)$")


def _same(text: str) -> str:
    return " ".join(text.lower().split())


def check(daemon: Daemon) -> int:
    """One read of every live twin's inbox page: answers how many missions it started. A twin whose
    read fails is logged (its kind of failure, never a value) and the others go on."""
    started = 0
    for twin_id in daemon.twins.ids():
        try:
            row = daemon.twins.one("chores", twin_id, INBOX)
            if row is None or not row.get("page") or daemon.twins.row(twin_id)["state"] != "live":
                continue
            started += read(daemon, twin_id)
        except Exception as e:  # one twin never stops the others
            log.warning("the task inbox of %s was not read this time (%s)", twin_id, type(e).__name__)
    return started


def read(daemon: Daemon, twin_id: str) -> int:
    """Reads the twin's inbox page once and takes its new lines: answers how many missions it started."""
    twins = daemon.twins
    space_id = str(twins.row(twin_id)["space_id"])
    row = twins.one("chores", twin_id, INBOX)
    if row is None or not row.get("page"):
        return 0
    page_id, title = str(row["page"]), str(row.get("title") or "its inbox page")
    report: dict[str, Any] = {k: v for k, v in row.items() if k != "problem"}
    report["checked_at"] = now_iso()
    lines: list[tuple[str, str]] = []
    if not any(p["id"] == page_id and p.get("picked") for p in twins.rows("pages", twin_id)):
        report["problem"] = f"'{title}' is no longer a page it may read; choose its inbox again."
    else:
        try:
            lines = page_lines(daemon.connectors, page_id)
        except (Unreachable, ValueError) as e:
            report["problem"] = cut(f"It could not read '{title}': {e}", DETAIL_MAX)
    taken: list[dict[str, Any]] = list(row.get("taken", []))
    blocks = {str(t["block"]) for t in taken}
    words = {_same(str(t["text"])) for t in taken}
    unplaced: list[str] = []
    known: list[Recent] | None = None
    started = 0
    for block, text in lines:
        found = _LINE.match(text)
        if text.startswith(TAKEN) or found is None or block in blocks or _same(text) in words:
            continue
        if known is None:
            known = _recent(daemon, twin_id)
        target, why = place(found["who"].strip(), known)
        if target is None:
            unplaced.append(_said(text, why))
            continue
        try:
            mission_id = missions.create(
                daemon, twin_id, {"thread": target, "goal": found["goal"]}, source="notion"
            )
        except ApiError as e:
            unplaced.append(_said(text, e.reason))
            continue
        taken.append({"block": block, "text": text, "mission": mission_id})
        blocks.add(block)
        words.add(_same(text))
        report["taken"] = taken
        twins.save("chores", twin_id, space_id, INBOX, report)  # kept at once: a line is taken once
        started += 1
        _mark(daemon, twin_id, space_id, report, text, mission_id)
    report["unplaced"] = unplaced[:UNPLACED_MAX]
    twins.save("chores", twin_id, space_id, INBOX, report)
    if started == 0 and (report.get("unplaced") != row.get("unplaced") or "problem" in report):
        daemon.events.publish({"type": "space_changed", "space_id": space_id})
    return started


def _recent(daemon: Daemon, twin_id: str) -> list[Recent]:
    """Its recent conversations, or none when Gmail cannot list them: an address still places a line."""
    try:
        return recent(daemon, twin_id)
    except ApiError:
        return []


def _said(text: str, why: str) -> str:
    return cut(f"'{cut(text, LABEL_MAX)}': {why}", DETAIL_MAX)


def place(who: str, known: list[Recent]) -> tuple[str | None, str]:
    """Where a line's mission lives: (a thread id or one address, "") or (None, why in plain words).
    `known` is newest first, so an address goes on its newest conversation with them."""
    if "@" in who:
        address = one_address(who)
        if address is None:
            return None, "write one address before the colon"
        with_them = [r for r in known if r.address == address]
        return (with_them[0].id if with_them else address), ""
    if any(r.id == who for r in known):
        return who, ""
    low = _same(who)
    named = [r.id for r in known if low in (_same(r.who), _same(plain_subject(r.subject)))]
    if not named and len(low) >= NAME_MIN:
        named = [r.id for r in known if low in _same(r.who) or low in _same(plain_subject(r.subject))]
    if len(set(named)) == 1:
        return named[0], ""
    if named:
        return None, f"'{who}' names {len(set(named))} of your conversations; write their address instead"
    return None, f"no recent conversation with '{who}'; write their address instead"


def _mark(daemon: Daemon, twin_id: str, space_id: str, report: dict[str, Any], line: str, mid: str) -> None:
    """The one write it makes on the page: a "Taken:" note, ruled on the Notion channel."""
    try:
        channel = missions.channel_of(daemon, twin_id, "notion")
    except ApiError:
        return  # it has no Notion channel: nothing is written
    where = f"Notion: {report.get('title') or 'its inbox page'}"
    text = missions.cut_note(f"{TAKEN} {cut(line, DETAIL_MAX)} (a mission started {now_iso()[:10]})")
    live = daemon.twins.row(twin_id)["state"] == "live"
    ruling = decide(channel, DraftFacts(kind="reply", confidence=100, risks=()), twin_live=live)
    if ruling.decision == "sent_alone":
        problem = missions.write_note(daemon, str(report["page"]), text)
        if problem:
            log.info("a taken note for %s did not go", mid)
        return
    args: dict[str, Any] = {
        "twin_id": twin_id,
        "mission": mid,
        "draft": mint(missions.DRAFT_PREFIX),
        "page": report["page"],
        "where": where,
        "subject": cut(f"{TAKEN} {line}", LABEL_MAX),
        "text": text,
        "taken": True,
        "confidence": 100,
        "risks": [],
        "reason": ruling.reason,
    }
    if level(channel, "reply") == "auto":
        args["bar"] = channel["bar"]
    daemon.gate.file(space_id, "twin_note", args, cut(f"Mark a line taken on {where}", LABEL_MAX))
