"""Stage turns: each reply is a frame (her line, sketch ops, at most one ask). Surface `design`.

A design turn is an ordinary turn in the draft's Project (`turn.run_turn` with `design=`), so her
small window shows it. It offers `recall`, `sketch` and `ask` only. Every sketch call applies at once
and streams; nothing is stored until the turn ends with words, an op or an ask. A failed or empty
reply ends with `error` and the draft is left exactly as it was.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any, cast

from athena.app import Daemon
from athena.contracts import (
    ASK_TEXT_MAX,
    FOLLOW_UPS_MAX,
    LABEL_MAX,
    NAME_MAX,
    NEED_MAX,
    SUGGESTIONS_MAX,
    SUGGESTIONS_MIN,
    Ask,
    Draft,
    Sketch,
    SketchNode,
    SketchOp,
    Slot,
    StageView,
)
from athena.drafts import sketch as sketches
from athena.drafts.rubric import SLOTS, coverage
from athena.drafts.sketch import SLOT_NAMES, SketchError
from athena.engine import Engine, ToolCall
from athena.errors import ApiError
from athena.settings import ACTIVE_SPACE_KEY
from athena.turn import run_turn

SUGGESTIONS = (SUGGESTIONS_MIN, SUGGESTIONS_MAX)
QUOTE_WORDS_MIN = 3  # a quote shorter than this proves nothing about whose words a node holds
SUGGESTION_SEPARATOR = "|"
_AUTO_ID = re.compile(r"n(\d+)")
_QUOTE_MARKS = " \t\r\n\"'" + "".join(
    map(chr, (0x201C, 0x201D, 0x2018, 0x2019, 0xAB, 0xBB))
)  # curly, guillemets

SLOT_MEANING: dict[Slot, str] = {
    "need": "the job, in the person's own words",
    "apps": "where it happens (the websites or apps)",
    "inputs": "what she reads (pages, mail, calls, letters)",
    "steps": "the order she works in",
    "hand": "what waits for the person's signature",
    "output": "what the person gets at the end",
    "never": "what she must never do or touch",
}
SLOT_KIND: dict[Slot, str] = {
    "need": "step",
    "apps": "app",
    "inputs": "source",
    "steps": "step",
    "hand": "gate",
    "output": "output",
    "never": "never",
}


def _tool(name: str, description: str, props: dict[str, str], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
                "required": required,
            },
        },
    }


SKETCH_TOOL = _tool(
    "sketch",
    "Change the sketch of the person's process at once: add a node, change one, remove a node or a link, "
    "or link two nodes. Places never move; a new node takes the next place.",
    {
        "op": "add, change, remove or link",
        "id": "The node's id (add: optional, one is given if empty; change and remove: required)",
        "kind": "source, app, step, gate, output or never (add: required)",
        "slot": "need, apps, inputs, steps, hand, output or never (add: required)",
        "label": f"A few plain words, at most {LABEL_MAX} characters (add: required)",
        "detail": "An optional second line",
        "link_from": "link, or remove a link: the id the arrow starts at",
        "link_to": "link, or remove a link: the id the arrow ends at",
        "quote": "add: the person's exact words this node comes from, if it does (3 words or more)",
    },
    ["op"],
)
ASK_TOOL = _tool(
    "ask",
    "Ask the person one question about one slot, with 2 to 4 short suggested answers. At most one per reply.",
    {
        "slot": "need, apps, inputs, steps, hand, output or never",
        "text": f"The question, at most {ASK_TEXT_MAX} characters",
        "suggestions": "2 to 4 short answers, separated by ' | '",
    },
    ["slot", "text", "suggestions"],
)

RULES = (
    "## Drawing the chore with the person\n"
    "The person wants to hand a chore to you. Together you draw a sketch of the process: their "
    "picture of it, not a program. Use `sketch` to draw what they told you and to propose what is "
    "missing; use `ask` for the next useful question.\n"
    "Rules:\n"
    "- At most one `ask` per reply, with 2 to 4 short suggested answers.\n"
    "- Never say or imply the sketch is complete, done or ready. The person decides when it is enough.\n"
    "- Draw the person's own words with `quote` set to their exact words; anything else you add is "
    "your proposal, and the person confirms it on screen.\n"
    "- Keep your line to one or two short sentences. Never mention tools, ids or slots by name."
)


def default_name(need: str) -> str:
    """The Project's first name: the need, cut to NAME_MAX at a word boundary."""
    return _cut(need, NAME_MAX)


def _cut(text: str, n: int) -> str:
    text = " ".join(text.split())
    if len(text) <= n:
        return text
    head = text[: n - 1]
    if " " in head and text[n - 1] != " ":
        head = head.rsplit(" ", 1)[0]
    return head.rstrip(" ,;:.-") + "…"


def _plain(text: str) -> str:
    return " ".join(text.split())


def _arg(call: ToolCall, key: str) -> str:
    """A tool argument as trimmed text; absent, null or empty is ""."""
    value = call.arguments.get(key)
    return "" if value is None else str(value).strip()


class Design:
    """One design turn over one draft. `run_turn(..., design=...)` offers its tools, adds its frame,
    hands it the `sketch` and `ask` calls, and asks it to settle when the reply is in."""

    def __init__(
        self,
        daemon: Daemon,
        draft: Draft,
        skipped: frozenset[Slot],
        asked: dict[Slot, int],
        view: StageView | None = None,
    ) -> None:
        self.daemon = daemon
        self.view = view
        self.draft = draft
        self.skipped = skipped
        self.asked = dict(asked)
        self.sketch: Sketch = draft["sketch"]
        self.applied: list[SketchOp] = []
        self.ask: Ask | None = None

    # --- what run_turn asks -----------------------------------------------------------------------

    @staticmethod
    def owns(name: str) -> bool:
        return name in ("sketch", "ask")

    @staticmethod
    def tools() -> list[dict[str, Any]]:
        return [SKETCH_TOOL, ASK_TOOL]

    @property
    def progressed(self) -> bool:
        """The reply changed the sketch or asked something."""
        return bool(self.applied) or self.ask is not None

    def frame(self) -> str:
        cov = coverage(self.sketch, self.skipped)
        parts = [RULES, "### The slots (what the sketch must cover)"]
        parts += [f"- {s}: {SLOT_MEANING[s]} (usual kind: {SLOT_KIND[s]})" for s in SLOTS]
        parts.append(f"### The person's need, in their words\n{self.draft['need']}")
        parts.append("### The sketch now")
        if self.sketch["nodes"]:
            for n in self.sketch["nodes"]:
                whose = "the person's" if n["origin"] == "you" else "your proposal"
                state = "confirmed" if n["confirmed"] else "not confirmed"
                parts.append(f'- [{n["id"]}] {n["kind"]} in {n["slot"]}: "{n["label"]}" ({whose}, {state})')
            parts += [f"- link {e['from']} -> {e['to']}" for e in self.sketch["edges"]]
        else:
            parts.append("- (empty)")
        parts.append(
            "### Coverage now (1 = the person confirmed a node, 0.5 = only your proposals, 0 = empty, "
            "skipped = the person left it open)"
        )
        parts += [f"- {s}: {_value(cov[s])}" for s in SLOTS]
        parts.append(f"### Questions asked per slot (at most {FOLLOW_UPS_MAX + 1} each)")
        parts += [f"- {s} asked {self.asked.get(s, 0)}" for s in SLOTS]
        return "\n".join(parts)

    def call(self, call: ToolCall) -> tuple[str, list[dict[str, Any]]]:
        """(the tool result in plain words, the events to stream)."""
        if call.name == "ask":
            return self._ask(call)
        return self._sketch(call)

    def fallback(self) -> str:
        """Her line when the reply had no words but did change the sketch or ask."""
        return self.ask["text"] if self.ask is not None else "I changed the sketch."

    def record(self, reply: str) -> str:
        """The reply as kept in the conversation: with her question, so the history reads whole."""
        if self.ask is not None and self.ask["text"] not in reply:
            return f"{reply}\n\n{self.ask['text']}"
        return reply

    def settle(self) -> list[dict[str, Any]]:
        """Stores the frame (sketch, the question count, step `shape`) and answers the closing
        `coverage` event. Called only for a reply that counts."""
        asked = dict(self.asked)
        if self.ask is not None:
            asked[self.ask["slot"]] = asked.get(self.ask["slot"], 0) + 1
        draft = cast("Draft", {**self.draft, "sketch": self.sketch, "step": "shape"})
        if self.view is not None:  # the comparison between the stage's views counts only replies that count
            views = dict(self.draft.get("views", {}))
            views[self.view] = views.get(self.view, 0) + 1
            draft["views"] = views
        stored = self.daemon.drafts.put(draft, asked=asked)
        _rename(self.daemon, stored)
        return [{"type": "coverage", "coverage": stored["coverage"], "agreed": stored["agreed"]}]

    # --- the two actions ------------------------------------------------------------------------

    def _ask(self, call: ToolCall) -> tuple[str, list[dict[str, Any]]]:
        if self.ask is not None:
            return "You already asked a question in this reply; ask one at a time.", []
        slot = _arg(call, "slot")
        if slot not in SLOT_NAMES:
            return f"The slot must be one of {', '.join(SLOTS)}.", []
        used = self.asked.get(cast("Slot", slot), 0)
        if used > FOLLOW_UPS_MAX:
            return f"You have asked enough about {slot}; move on or let the person write it.", []
        text = _plain(_arg(call, "text"))
        if not 1 <= len(text) <= ASK_TEXT_MAX:
            return f"Ask one short question, 1 to {ASK_TEXT_MAX} characters.", []
        suggestions: list[str] = []
        for raw in _arg(call, "suggestions").split(SUGGESTION_SEPARATOR):
            s = _plain(raw)
            if s and s.casefold() not in {x.casefold() for x in suggestions}:
                suggestions.append(s)
        low, high = SUGGESTIONS
        if not low <= len(suggestions) <= high:
            return f"Give {low} to {high} different short answers, separated by ' | '.", []
        if any(len(s) > LABEL_MAX for s in suggestions):
            return f"Each suggested answer is at most {LABEL_MAX} characters.", []
        ask: Ask = {"slot": cast("Slot", slot), "text": text, "suggestions": suggestions, "follow_up": used}
        self.ask = ask
        return "Asked. The person sees your question and suggestions; wait for their answer.", [
            {"type": "ask", "ask": ask}
        ]

    def _sketch(self, call: ToolCall) -> tuple[str, list[dict[str, Any]]]:
        op = _arg(call, "op").lower()
        note = ""
        try:
            if op == "add":
                node, note = self._new_node(call)
                ops: list[SketchOp] = [{"op": "add", "node": node}]
            elif op == "change":
                fields = {k: _arg(call, k) for k in ("label", "detail", "kind", "slot") if _arg(call, k)}
                ops = [{"op": "change", "node": cast("SketchNode", {"id": _arg(call, "id"), **fields})}]
            elif op == "remove" and _arg(call, "id"):
                ops = [{"op": "remove", "node": cast("SketchNode", {"id": _arg(call, "id")})}]
            elif op in ("remove", "link"):
                if not _arg(call, "link_from") or not _arg(call, "link_to"):
                    raise SketchError(
                        f"{op} needs an id, or link_from and link_to"
                        if op == "remove"
                        else "link needs link_from and link_to"
                    )
                edge = {"from": _arg(call, "link_from"), "to": _arg(call, "link_to")}
                ops = [cast("SketchOp", {"op": op, "edge": edge})]
            else:
                raise SketchError("the op must be add, change, remove or link")
            self.sketch, applied = sketches.apply(self.sketch, ops)
        except SketchError as e:
            return f"Not drawn: {e}. The sketch is unchanged.", []
        self.applied += applied
        return _done(applied) + note, [{"type": "sketch", "ops": applied}]

    def _new_node(self, call: ToolCall) -> tuple[SketchNode, str]:
        quote = _arg(call, "quote")
        theirs = self._quoted(quote)
        node = cast(
            "SketchNode",
            {
                "id": _arg(call, "id") or self._next_id(),
                "kind": _arg(call, "kind"),
                "slot": _arg(call, "slot"),
                "label": _arg(call, "label"),
                "origin": "you" if theirs else "athena",
                "confirmed": theirs,
            },
        )
        if _arg(call, "detail"):
            node["detail"] = _arg(call, "detail")
        if theirs:
            return node, " It is in the person's own words, so it is theirs."
        if quote:
            return node, " That quote is not in the person's own words, so it stays your proposal."
        return node, " It is your proposal until the person confirms it."

    def _next_id(self) -> str:
        taken = [int(m.group(1)) for n in self.sketch["nodes"] if (m := _AUTO_ID.fullmatch(n["id"]))]
        return f"n{max(taken, default=0) + 1}"

    def _quoted(self, quote: str) -> bool:
        """Whether `quote` (trimmed, case-insensitive, at least QUOTE_WORDS_MIN words) is verbatim in
        one of the person's own messages in this draft: the need, a typed line, a picked answer."""
        q = _plain(quote).strip(_QUOTE_MARKS).casefold()
        if len(q.split()) < QUOTE_WORDS_MIN:
            return False
        said = [self.draft["need"]] + [
            t["text"]
            for t in self.daemon.conversation.list(self.draft["space_id"], 10_000)
            if t["role"] == "person"
        ]
        return any(q in _plain(s).casefold() for s in said)


def _value(v: object) -> str:
    return "skipped" if v == "skipped" else ("0.5" if v == 0.5 else str(int(cast("float", v))))


def _done(applied: list[SketchOp]) -> str:
    lines: list[str] = []
    for op in applied:
        if "node" in op:
            n = op["node"]
            verb = {"add": "Added", "change": "Changed", "remove": "Removed"}.get(op["op"], op["op"])
            lines.append(f'{verb} [{n["id"]}] {n["kind"]} in {n["slot"]}: "{n["label"]}".')
        elif "edge" in op:
            e = op["edge"]
            verb = "Linked" if op["op"] == "link" else "Removed the link"
            lines.append(f"{verb} {e['from']} -> {e['to']}.")
    return " ".join(lines)


def _rename(daemon: Daemon, draft: Draft) -> None:
    """The Project takes the first need node's label while it still has its first name."""
    space = daemon.spaces.get(draft["space_id"])
    if space["name"] != default_name(draft["need"]):
        return
    first = next((n for n in draft["sketch"]["nodes"] if n["slot"] == "need"), None)
    if first is None:
        return
    name = _cut(first["label"], NAME_MAX)
    if name != space["name"]:
        daemon.spaces.update(space["id"], {"name": name})
        daemon.events.publish({"type": "space_changed", "space_id": space["id"]})


# --- the flow -------------------------------------------------------------------------------------


def _busy(daemon: Daemon, draft: Draft) -> None:
    if daemon.busy.running(draft["space_id"]):
        raise ApiError("space_busy", "Athena is still answering; try again when she is done")


def _shaping(draft: Draft) -> None:
    if draft["step"] not in ("describe", "shape"):
        raise ApiError("bad_request", "this draft is past the sketch; go back to the sketch first")


def start(daemon: Daemon, need: str) -> Draft:
    """Creates the Project and the draft at `describe` and makes the Project active. Nothing runs:
    the first `say` with empty text runs the first stage turn on the need. Validates first."""
    if not isinstance(need, str) or not 1 <= len(need.strip()) <= NEED_MAX:
        raise ApiError("bad_request", f"describe the need in 1 to {NEED_MAX} characters")
    need = need.strip()
    if daemon.busy.any_running():
        raise ApiError("space_busy", "Athena is working; try again when she is done")
    space = daemon.spaces.create({"name": default_name(need)})
    daemon.events.publish({"type": "space_changed", "space_id": space["id"]})
    daemon.settings.set(ACTIVE_SPACE_KEY, space["id"])
    daemon.events.publish({"type": "active_space", "space_id": space["id"]})
    return daemon.drafts.create(space["id"], need)


def say(
    daemon: Daemon,
    engine: Engine,
    draft_id: str,
    text: str,
    choice: str | None,
    view: StageView | None = None,
) -> Iterator[dict[str, Any]]:
    """One stage turn: TurnEvents plus `sketch`, `ask` and `coverage`. Validates before returning.

    On a `describe` draft with nothing said, the need is the person's words. Afterwards the person
    types `text` or picks a suggestion (`choice`, kept as their words); one of the two, not both.
    """
    draft = daemon.drafts.get(draft_id)
    _shaping(draft)
    text, picked = text.strip(), (choice or "").strip()
    if text and picked:
        raise ApiError("bad_request", "send what you typed or the answer you picked, not both")
    words = text or picked
    if not words:
        if draft["step"] != "describe":
            raise ApiError("bad_request", "say something, or pick one of her suggestions")
        words = draft["need"]
    _busy(daemon, draft)
    asked, skipped = daemon.drafts.asked(draft_id), daemon.drafts.skipped(draft_id)
    design = Design(daemon, draft, skipped, asked, view)
    return run_turn(daemon, engine, words, draft["space_id"], design=design)


def confirm(daemon: Daemon, draft_id: str, node_ids: list[str]) -> Draft:
    """The person accepts Athena's proposed nodes; coverage is recomputed."""
    draft = daemon.drafts.get(draft_id)
    _shaping(draft)
    _busy(daemon, draft)
    try:
        sketch, _ = sketches.confirm(draft["sketch"], node_ids)
    except SketchError as e:
        raise ApiError("bad_request", str(e)) from e
    return daemon.drafts.put(cast("Draft", {**draft, "sketch": sketch}))


def drop(daemon: Daemon, draft_id: str, node_ids: list[str]) -> Draft:
    """The person rubs out Athena's unconfirmed guesses (and their links); coverage is recomputed."""
    draft = daemon.drafts.get(draft_id)
    _shaping(draft)
    _busy(daemon, draft)
    try:
        sketch, _ = sketches.drop(draft["sketch"], node_ids)
    except SketchError as e:
        raise ApiError("bad_request", str(e)) from e
    return daemon.drafts.put(cast("Draft", {**draft, "sketch": sketch}))


def abandon(daemon: Daemon, draft_id: str) -> None:
    """Deletes the draft's row and folder; its Project stays."""
    _busy(daemon, daemon.drafts.get(draft_id))
    daemon.drafts.delete(draft_id)
