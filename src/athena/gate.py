"""The gate: GATED actions file a card; a card resolves exactly once.

A twin's draft (ADR 0009) is a card whose text the person may edit before signing: the edited copy
is stored on the card, the original kept beside it as `drafted`. An executor that fails returns the
card to `waiting` and its problem is the answer, so a card never reads as signed when nothing ran
and the person can sign it again once the problem is fixed.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable
from typing import Any

from athena.clock import mint, now_iso
from athena.contracts import TEXT_MAX, ActionName, Card, CardState, Verdict
from athena.errors import ApiError
from athena.events import Events
from athena.store import Store

log = logging.getLogger(__name__)

# Runs an approved action and returns a plain-words outcome. Registered by the turn package (WP3).
# It raises (ApiError, in plain words) when the action did not happen.
Executor = Callable[[Card], str]

#: The actions whose text the person may edit when signing, and how long that text may be: one
#: Gmail message, one Notion note (as the practice page's lines are cut).
EDITABLE: dict[str, int] = {"twin_send": TEXT_MAX, "twin_note": 4000}


def _card(r: sqlite3.Row) -> Card:
    c: Card = {
        "id": r["id"],
        "space_id": r["space_id"],
        "action": r["action"],
        "label": r["label"],
        "args": json.loads(r["args"]),
        "state": r["state"],
        "created": r["created"],
    }
    if r["resolved"] is not None:
        c["resolved"] = r["resolved"]
    return c


class Gate:
    def __init__(self, store: Store, events: Events) -> None:
        self._store = store
        self._events = events
        self._executor: Executor | None = None

    def set_executor(self, executor: Executor) -> None:
        self._executor = executor

    def file(self, space_id: str, action: ActionName, args: dict[str, Any], label: str) -> Card:
        """Publishes `card_filed`."""
        card_id = mint("card_")
        self._store.run(
            "INSERT INTO cards(id, space_id, action, label, args, state, created) "
            "VALUES (?,?,?,?,?,'waiting',?)",
            (card_id, space_id, action, label, json.dumps(args), now_iso()),
        )
        card = self.get(card_id)
        self._events.publish({"type": "card_filed", "card": card})
        return card

    def resolve(self, card_id: str, verdict: Verdict, edited: str | None = None) -> Card:
        """One conditional UPDATE (`WHERE state = 'waiting'`); the loser of a race gets
        ApiError("bad_request", "already decided"). Approve runs the executor once, after the
        UPDATE won; while it runs the card is signed, so a second signature loses the race. An
        executor that raises returns the card to `waiting` and raises its problem in plain words.
        `edited` is the person's text for a twin's draft: checked for the action, then stored on
        the card in place of the draft's (which stays as `drafted`). Publishes `card_resolved`."""
        before = self.get(card_id)  # unknown_ref when absent
        args = _edit(before, edited) if edited is not None and verdict == "approve" else before["args"]
        state = "approved" if verdict == "approve" else "declined"
        changed = self._store.run(
            "UPDATE cards SET state = ?, resolved = ?, args = ? WHERE id = ? AND state = 'waiting'",
            (state, now_iso(), json.dumps(args), card_id),
        )
        card = self.get(card_id)
        if changed == 0:
            raise ApiError("bad_request", "already decided")
        if verdict == "approve" and self._executor is not None:
            try:
                self._executor(card)
            except Exception as e:
                self._store.run(
                    "UPDATE cards SET state = 'waiting', resolved = NULL WHERE id = ?", (card_id,)
                )
                if isinstance(e, ApiError):
                    raise
                log.warning("a signed %s card did not run (%s)", card["action"], type(e).__name__)
                raise ApiError(
                    "bad_request", "It could not be done, so nothing changed. Try again."
                ) from None
        self._events.publish({"type": "card_resolved", "card": card})
        return card

    def get(self, card_id: str) -> Card:
        rows = self._store.query("SELECT * FROM cards WHERE id = ?", (card_id,))
        if not rows:
            raise ApiError("unknown_ref", "no such card")
        return _card(rows[0])

    def list(self, state: CardState | None = None) -> list[Card]:
        if state is None:
            rows = self._store.query("SELECT * FROM cards ORDER BY rowid DESC")
        else:
            rows = self._store.query("SELECT * FROM cards WHERE state = ? ORDER BY rowid DESC", (state,))
        return [_card(r) for r in rows]


def _edit(card: Card, edited: str) -> dict[str, Any]:
    """The card's args with the person's text, checked for its action. The same text is no edit."""
    limit = EDITABLE.get(card["action"])
    if limit is None:
        raise ApiError("bad_request", "only a twin's draft can be edited before it is signed")
    text = edited.strip()
    if not 1 <= len(text) <= limit:
        raise ApiError("bad_request", f"write the text in 1 to {limit} characters")
    args = dict(card["args"])
    if text == str(args.get("text", "")).strip():
        return args
    drafted = str(args.pop("drafted", args.get("text", "")))
    if text != drafted.strip():  # back to the draft's own words is no edit either
        args["drafted"] = drafted
    args["text"] = text
    return args
