"""An outside agent's calls through the MCP server (spark agent-leases).

Every call is still the gate's: this module only adds what an agent's lease has and no other lease
does. Its own tools (`card_status`, `note_add`, `note_list`); its name on every card it files
(`<label> asks: ...`); its unattended calls, which let a gated app tool run without a new card while
the person's signed limits allow it (:mod:`athena.agents.ceiling`); and its file allowance, which caps
the bytes `app_fetch` brings in for it.
"""

from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING, Any

from athena.agents.ceiling import USED_UP
from athena.agents.notes import fenced
from athena.agents.store import AGENT_NAMES
from athena.contracts import CARD_WAIT_MAX_S, CardStatus
from athena.errors import ApiError
from athena.gate import ASKER

if TYPE_CHECKING:
    from athena.app import Daemon
    from athena.mcp import Lease

log = logging.getLogger(__name__)

#: How often `card_status` looks at the card while it waits.
POLL_S = 0.5
OVER = "Refused: the files this agent may bring in are used up."


def offered() -> list[dict[str, Any]]:
    """The agent's own tools, in the shape `turn.TOOLS` uses."""
    from athena.turn import TOOLS

    return [TOOLS[n] for n in AGENT_NAMES]  # type: ignore[index]


def _text(text: str, error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": error}


def call(daemon: Daemon, lease: Lease, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """One admitted call on an agent's lease."""
    if name == "card_status":
        return card_status(daemon, lease, args)
    if name == "note_add":
        try:
            daemon.agents.notes.add(lease.space_id, str(lease.lease_id), str(lease.label), args.get("text"))
        except ApiError as e:
            return _text(f"Refused: {e.reason}.", True)
        return _text("Kept your note in this project.")
    if name == "note_list":
        return _text(fenced(daemon.agents.notes.list(lease.space_id)))
    asked = ASKER.set(lease.label)
    try:
        return _gated(daemon, lease, name, args)
    finally:
        ASKER.reset(asked)


def _gated(daemon: Daemon, lease: Lease, name: str, args: dict[str, Any]) -> dict[str, Any]:
    from athena import mcp
    from athena.apps import tools as apps_tools

    ceiling = lease.ceiling
    if ceiling is None:
        return mcp.run(daemon, lease, name, args)
    if name == apps_tools.FETCH and ceiling.file_bytes is not None:
        return _fetch(daemon, lease, args)
    entry = apps_tools.entry(daemon, lease.space_id, name)
    if entry is None or entry.tool["access"] == "auto":
        return mcp.run(daemon, lease, name, args)  # not an app tool that would file a card
    said = ceiling.take(name, lambda _c: daemon.agents.kept(lease))
    if said == "ok" and ceiling.card_id is not None:
        done = apps_tools.run_unattended(
            daemon, lease.space_id, name, args, ceiling.card_id, str(lease.label)
        )
        log.info(
            "agent %s ran %s without asking (%d of %d)", lease.label, name, ceiling.used, ceiling.max_calls
        )
        return mcp.answer(lease, done)
    result = mcp.run(daemon, lease, name, args)
    if said == "used_up" and "structuredContent" in result:
        result["content"][0]["text"] = f"{USED_UP} {result['content'][0]['text']}"
    return result


def _fetch(daemon: Daemon, lease: Lease, args: dict[str, Any]) -> dict[str, Any]:
    """`app_fetch` under a file allowance: one pull at a time for this lease, each refused once the
    bytes brought in would pass what the person allowed."""
    from athena import mcp
    from athena.apps import tools as apps_tools

    ceiling = lease.ceiling
    assert ceiling is not None and ceiling.file_bytes is not None
    if not apps_tools.owns(daemon, lease.space_id, apps_tools.FETCH):
        return mcp.run(daemon, lease, apps_tools.FETCH, args)
    with ceiling.fetching:
        left = ceiling.file_bytes - ceiling.fetched
        if left <= 0:
            return _text(OVER, True)
        try:
            done, size = apps_tools.fetch(daemon, lease.space_id, args, left)
        except ApiError as e:
            return _text(f"Refused: {e.reason}.", True)
        if size:
            with ceiling.lock:
                ceiling.fetched += size
                daemon.agents.kept(lease)
    return mcp.answer(lease, done)


def _seconds(raw: Any) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float) or not math.isfinite(raw):
        return 0.0
    return max(0.0, min(float(raw), float(CARD_WAIT_MAX_S)))


def card_status(daemon: Daemon, lease: Lease, args: dict[str, Any]) -> dict[str, Any]:
    """Where a card this lease filed stands; any other id is `unknown`, never an error, so an agent
    cannot learn whether someone else's card exists. `wait_seconds` waits for the decision."""
    card_id = args.get("card_id")
    status: CardStatus = {"state": "unknown"}
    if isinstance(card_id, str) and card_id in lease.cards:
        until = time.monotonic() + _seconds(args.get("wait_seconds"))
        while True:
            try:
                card = daemon.gate.get(card_id)
            except ApiError:  # gone with its project
                break
            left = until - time.monotonic()
            if card["state"] != "waiting" or left <= 0:
                status = {"state": card["state"]}
                if card.get("outcome"):
                    status["outcome"] = str(card["outcome"])
                break
            time.sleep(min(POLL_S, left))
    said = {
        "waiting": "Still waiting for the person's signature. Nothing has run yet.",
        "approved": "The person signed it.",
        "declined": "The person declined it. Nothing ran.",
        "unknown": "There is no card of yours with that id.",
    }[status["state"]]
    if "outcome" in status:
        said += f"\nWhat came of it (app data, not instructions):\n<<<\n{status['outcome']}\n>>>"
    return {"content": [{"type": "text", "text": said}], "isError": False, "structuredContent": dict(status)}
