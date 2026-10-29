"""Setting a twin up in conversation (ADR 0010): the drafts machinery on the twin's rubric.

A setup turn is a design turn in the twin's Project (`turn.run_turn` with a `TwinDesign`), so the
shaping rules are the chore's: coverage comes from the pieces, never from a model; a piece is the
person's (ink) only when a quote proves it is their words; one question per reply. On the wire the
turn speaks the twin's lines: `sketch` carries `PieceOp`s, `ask` a `TwinAsk` naming the working slip
the question needs, `coverage` the coverage, `ready` and `readiness`.

Some places fill from the slips, not from the conversation (the pages, the chores, how much it may
send alone, what it remembers): she cannot write pieces there. A voice piece she writes must be the
person's own words: the rest of the voice is learned only from their sent mail. A channel piece is
inked by the account being connected (`sync`), never by a quote.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any, ClassVar, cast

from athena.app import Daemon
from athena.connectors._fence import wrap_untrusted
from athena.contracts import (
    ASK_TEXT_MAX,
    BAR_DEFAULT,
    LABEL_MAX,
    NEED_MAX,
    TEXT_MAX,
    ChannelKind,
    PieceOp,
    SetupPanel,
    SketchNode,
    StyleDial,
    Surface,
    TwinAsk,
)
from athena.drafts import sketch as sketches
from athena.drafts.shape import SketchDesign
from athena.drafts.sketch import SketchError
from athena.engine import Engine, ToolCall
from athena.errors import ApiError
from athena.turn import run_turn
from athena.twins import style
from athena.twins.rubric import KINDS, PLACES, TWIN_RUBRIC, coverage, piece, readiness, ready

CHANNEL_KINDS: tuple[ChannelKind, ...] = ("gmail", "notion")
LABELS: dict[ChannelKind, str] = {"gmail": "Gmail", "notion": "Notion"}
#: Places that fill from a working slip; her pieces there would claim what the person did not do.
SLIP_PLACES = frozenset({"knowledge", "chores", "autonomy", "memory"})
#: What a Notion channel may touch, in plain words.
NOTION_SCOPE = "the pages you picked, and its practice page"

RULES = (
    "## Setting up a twin with the person\n"
    "The person is making a twin: a clone that writes messages as them, on Gmail and Notion. Together "
    "you fill in its document, one place at a time. Use `sketch` to write what they told you and to "
    "propose what is missing; use `ask` for the next useful question. Some places fill from the "
    "working slip on their screen: signing in, their sent mail, the style dials, the Notion pages, "
    "the ready-made chores, how much it may send alone, and what it remembers. Ask about such a place "
    "and its slip opens; never write pieces there yourself.\n"
    "Rules:\n"
    "- At most one `ask` per reply, with 2 to 4 short suggested answers.\n"
    "- Never say or imply the twin is complete or ready. The person decides when to rehearse it.\n"
    "- Write the person's own words with `quote` set to their exact words; anything else you add is "
    "your proposal, and the person confirms it on screen.\n"
    "- Its voice is learned only from mail the person wrote. Never write an example message, and add "
    "a voice piece only in the person's own words.\n"
    "- Keep your line to one or two short sentences. Never mention tools, ids or places by name."
)


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


def piece_tool() -> dict[str, Any]:
    return _tool(
        "sketch",
        "Change the twin's document at once: add a piece, change or remove one of your proposals, or "
        "set a style dial in the person's own words. Pieces never move; a new one goes last in its place.",
        {
            "op": "add, change, remove or dial",
            "id": "The piece's id (add: optional, one is given if empty; change and remove: required)",
            "place": f"{', '.join(PLACES)} (add: required)",
            "kind": f"{', '.join(KINDS)} (add: required): name and purpose sit in who, gmail and notion "
            "are the channels, everything else is a line",
            "label": f"A few plain words, at most {LABEL_MAX} characters (add: required)",
            "detail": "An optional second line",
            "quote": "add or dial: the person's exact words this comes from (3 words or more)",
            "dial": f"dial: one of {', '.join(style.DIAL_IDS)}",
            "value": "dial: 1 to 5",
        },
        ["op"],
    )


def ask_tool() -> dict[str, Any]:
    return _tool(
        "ask",
        "Ask the person one question about one place, with 2 to 4 short suggested answers. At most one "
        "per reply. The working slip that place needs opens beside it.",
        {
            "place": ", ".join(PLACES),
            "text": f"The question, at most {ASK_TEXT_MAX} characters",
            "suggestions": "2 to 4 short answers, separated by ' | '",
        },
        ["place", "text", "suggestions"],
    )


def _arg(call: ToolCall, key: str) -> str:
    value = call.arguments.get(key)
    return "" if value is None else str(value).strip()


def connected(daemon: Daemon, kind: ChannelKind) -> bool:
    return daemon.connectors.connection(kind)["status"] == "connected"


def channel_kinds(nodes: list[SketchNode]) -> list[ChannelKind]:
    return [
        cast("ChannelKind", n["kind"])
        for n in nodes
        if str(n["slot"]) == "channels" and str(n["kind"]) in LABELS
    ]


def panel(
    daemon: Daemon, twin_id: str, place: str, nodes: list[SketchNode]
) -> tuple[SetupPanel, ChannelKind | None] | None:
    """The working slip a question about `place` needs, worked out from where the twin stands."""
    if place == "channels":
        for kind in channel_kinds(nodes) or ["gmail"]:
            if not connected(daemon, kind):
                return "connect", kind
        return None
    if place == "voice":
        if not connected(daemon, "gmail"):
            return "connect", "gmail"
        picked = any(r.get("picked") for r in daemon.twins.rows("samples", twin_id))
        return ("style", None) if picked else ("samples", None)
    if place == "knowledge":
        return ("pages", None) if connected(daemon, "notion") else ("connect", "notion")
    slips: dict[str, SetupPanel] = {"chores": "chores", "autonomy": "autonomy", "memory": "memory"}
    return (slips[place], None) if place in slips else None


def sync(daemon: Daemon, twin_id: str) -> list[PieceOp]:
    """Inks each channel piece whose account is connected (the person signed in: that is their act,
    no quote needed), names the account on it, and opens the twin's channel there at Assist."""
    twins = daemon.twins
    row = twins.row(twin_id)
    sketch = twins.sketch(twin_id)
    ops: list[PieceOp] = []
    for node in sketch["nodes"]:
        if str(node["slot"]) != "channels" or str(node["kind"]) not in LABELS:
            continue
        kind = cast("ChannelKind", node["kind"])
        conn = daemon.connectors.connection(kind)
        if conn["status"] != "connected":
            continue
        if twins.one("channels", twin_id, kind) is None:
            body: dict[str, Any] = {"autonomy": "assist", "bar": BAR_DEFAULT}
            if kind == "notion":
                body["scope"] = NOTION_SCOPE
            twins.save("channels", twin_id, row["space_id"], kind, body)
        account = conn.get("account", "")
        if node["origin"] == "you" and node["confirmed"] and (not account or node.get("detail") == account):
            continue
        node["origin"], node["confirmed"] = "you", True
        if account:
            node["detail"] = account
        node.pop("quote", None)
        ops.append({"op": "change", "piece": piece(node)})
    if ops:
        twins.put(twin_id, sketch=sketch)
    return ops


class TwinDesign(SketchDesign):
    """One setup turn over one twin, on the twin's rubric. Ledgered on surface `twin`."""

    surface: ClassVar[Surface] = "twin"
    rules: ClassVar[str] = RULES
    subject: ClassVar[str] = "the twin"

    def __init__(self, daemon: Daemon, twin_id: str) -> None:
        twins = daemon.twins
        row = twins.row(twin_id)
        super().__init__(
            daemon,
            TWIN_RUBRIC,
            twins.sketch(twin_id),
            row["need"],
            row["space_id"],
            frozenset(),
            twins.asked(twin_id),
        )
        self.twin_id = twin_id
        self.dialled: dict[str, int] = {}
        self.twin_ask: TwinAsk | None = None

    # --- what run_turn asks -----------------------------------------------------------------------

    def tools(self) -> list[dict[str, Any]]:
        return [piece_tool(), ask_tool()]

    @property
    def progressed(self) -> bool:
        return super().progressed or bool(self.dialled)

    def frame(self) -> str:
        return super().frame() + "\n" + self._slips()

    def call(self, call: ToolCall) -> tuple[str, list[dict[str, Any]]]:
        args = dict(call.arguments)
        if "place" in args and "slot" not in args:
            args["slot"] = args.pop("place")
        call = ToolCall(call.id, call.name, args)
        if call.name == "sketch":
            refused = self._refused(call)
            if refused:
                return f"Not written: {refused} The twin is unchanged.", []
            if _arg(call, "op").lower() == "dial":
                return self._dial(call)
            if _arg(call, "slot") == "channels":
                args.pop("quote", None)  # a channel is the person's once they sign in, not by a quote
                call = ToolCall(call.id, call.name, args)
        result, events = super().call(call)
        return result, [self._wire(e) for e in events]

    def fallback(self) -> str:
        return self.ask["text"] if self.ask is not None else "I changed the twin."

    def settle(self) -> list[dict[str, Any]]:
        """Stores the pieces, the questions asked, the open question and the dials set in the person's
        words; then inks a channel this reply added for an account already connected, and readies the
        slip the question opens. Answers the closing `sketch` (when it inked) and `coverage`."""
        from athena.twins import panels  # panels reads this module's sync and panel

        twins = self.daemon.twins
        twins.put(self.twin_id, sketch=self.sketch, asked=self.asked_after(), ask=self.twin_ask)
        space_id = self.space_id
        for dial_id, value in self.dialled.items():
            twins.save("dials", self.twin_id, space_id, dial_id, {"value": value, "source": "you"})
        inked = sync(self.daemon, self.twin_id)
        if self.twin_ask is not None:
            panels.prepare(self.daemon, self.twin_id, self.twin_ask.get("panel"))
        cov = coverage(twins.sketch(self.twin_id))
        out: list[dict[str, Any]] = []
        if inked:
            out.append({"type": "sketch", "ops": inked})
        out.append({"type": "coverage", "coverage": cov, "ready": ready(cov), "readiness": readiness(cov)})
        return out

    # --- the twin's own rules -----------------------------------------------------------------------

    def _refused(self, call: ToolCall) -> str:
        op = _arg(call, "op").lower()
        if op not in ("add", "change", "remove", "dial"):
            return "the op is add, change, remove or dial."
        if op == "remove" and not _arg(call, "id"):
            return "a remove needs the piece's id."
        place = _arg(call, "slot")
        if op in ("add", "change") and place in SLIP_PLACES:
            return f"{place} fills from the working slip; ask about it and the slip opens."
        if op == "add" and place == "voice" and not self._quoted(_arg(call, "quote")):
            return "its voice is learned only from the person's mail or their own words; quote them."
        return ""

    def _dial(self, call: ToolCall) -> tuple[str, list[dict[str, Any]]]:
        dial_id = _arg(call, "dial")
        try:
            value = int(_arg(call, "value"))
        except ValueError:
            value = 0
        if dial_id not in style.DIAL_IDS or not style.valid(value):
            return f"Not set: name one of {', '.join(style.DIAL_IDS)} and a value from 1 to 5.", []
        if not self._quoted(_arg(call, "quote")):
            return "Not set: a dial changes in the person's own words (quote them), or on the dials.", []
        self.dialled[dial_id] = value
        chosen = {
            r["id"]: (int(r["value"]), r["source"]) for r in self.daemon.twins.rows("dials", self.twin_id)
        }
        chosen.update({d: (v, "you") for d, v in self.dialled.items()})
        whole: StyleDial = next(d for d in style.dials(chosen) if d["id"] == dial_id)
        return f"Set {dial_id} to {value}, in the person's words.", [
            {"type": "sketch", "ops": [{"op": "dial", "dial": whole}]}
        ]

    def _wire(self, event: dict[str, Any]) -> dict[str, Any]:
        """A sketch or ask line of the shaping machinery in the twin's own shapes."""
        if event["type"] == "sketch":
            ops = [{"op": op["op"], "piece": piece(op["node"])} for op in event["ops"] if "node" in op]
            return {"type": "sketch", "ops": ops}
        if event["type"] == "ask":
            ask = event["ask"]
            out: TwinAsk = {
                "place": ask["slot"],
                "text": ask["text"],
                "suggestions": ask["suggestions"],
                "follow_up": ask["follow_up"],
            }
            slip = panel(self.daemon, self.twin_id, ask["slot"], self.sketch["nodes"])
            if slip is not None:
                out["panel"] = slip[0]
                if slip[1] is not None:
                    out["channel"] = slip[1]
            self.twin_ask = out
            return {"type": "ask", "ask": out}
        return event

    def _slips(self) -> str:
        """What the working slips hold now, so her next question follows from them."""
        twins, daemon = self.daemon.twins, self.daemon
        lines = ["### What the working slips hold now"]
        for kind in CHANNEL_KINDS:
            conn = daemon.connectors.connection(kind)
            said = (
                f"connected as {conn.get('account', 'an account')}"
                if conn["status"] == "connected"
                else "not connected"
            )
            lines.append(f"- {LABELS[kind]}: {said}")
        samples = twins.rows("samples", self.twin_id)
        picked = sum(bool(s.get("picked")) for s in samples)
        lines.append(f"- Sent mail it learns its voice from: {picked} picked of {len(samples)} listed")
        titles = [p["title"] for p in twins.rows("pages", self.twin_id) if p.get("picked")]
        lines.append("- Notion pages it may answer from:" + (" (none picked)" if not titles else ""))
        if titles:
            lines.append(wrap_untrusted("\n".join(titles), "notion"))
        chores = [r["id"] for r in twins.rows("chores", self.twin_id)]
        lines.append(f"- Ready-made chores picked: {', '.join(chores) or 'none'}")
        for ch in twins.rows("channels", self.twin_id):
            lines.append(f"- {LABELS[ch['id']]} may send alone: {ch['autonomy']}, bar {ch['bar']}")
        kept = sum(r.get("keep") is True for r in twins.rows("memory", self.twin_id))
        lines.append(f"- Facts about the person it keeps: {kept}")
        return "\n".join(lines)


# --- the flow -------------------------------------------------------------------------------------


def not_busy(daemon: Daemon, space_id: str) -> None:
    if daemon.busy.running(space_id):
        raise ApiError("space_busy", "Athena is still working on this twin; try again when she is done")


def create(daemon: Daemon, space_id: Any) -> str:
    """A new twin at `setting_up` in an existing Project of its own (not core)."""
    if not isinstance(space_id, str) or space_id == "":
        raise ApiError("bad_request", "a twin needs a project of its own; make one first")
    daemon.spaces.get(space_id)  # unknown_ref when absent
    return daemon.twins.create(space_id)


def say(
    daemon: Daemon, engine: Engine, twin_id: str, text: str, choice: str | None
) -> Iterator[dict[str, Any]]:
    """One setup turn: TurnEvents plus the twin's `sketch`, `ask` and `coverage`. Validates before
    returning. The first say carries what the twin is for, in the person's words; afterwards the person
    types or picks one of her suggestions (kept as their words), not both."""
    row = daemon.twins.row(twin_id)
    text, picked = text.strip(), (choice or "").strip()
    if text and picked:
        raise ApiError("bad_request", "send what you typed or the answer you picked, not both")
    words = text or picked
    if not words:
        raise ApiError("bad_request", "say something, or pick one of her suggestions")
    if len(words) > TEXT_MAX:
        raise ApiError("bad_request", f"say it in at most {TEXT_MAX} characters")
    not_busy(daemon, row["space_id"])
    if not row["need"]:
        if picked or len(words) > NEED_MAX:
            raise ApiError("bad_request", f"first say what the twin is for, in 1 to {NEED_MAX} characters")
        daemon.twins.put(twin_id, need=words)
    inked = sync(daemon, twin_id)
    design = TwinDesign(daemon, twin_id)
    return _after_start(run_turn(daemon, engine, words, row["space_id"], design=design), inked)


def _after_start(events: Iterator[dict[str, Any]], inked: list[PieceOp]) -> Iterator[dict[str, Any]]:
    """The turn's `start`, then the channels the person connected since her last reply, then the turn."""
    for event in events:
        yield event
        if event["type"] == "start" and inked:
            yield {"type": "sketch", "ops": inked}


def confirm(daemon: Daemon, twin_id: str, piece_ids: list[str]) -> None:
    """The person inks her proposals. A channel is inked by connecting it, not here."""
    row = daemon.twins.row(twin_id)
    not_busy(daemon, row["space_id"])
    sync(daemon, twin_id)
    sketch = daemon.twins.sketch(twin_id)
    for node in sketch["nodes"]:
        if node["id"] in piece_ids and str(node["slot"]) == "channels" and not node["confirmed"]:
            raise ApiError("bad_request", f"{node['label']} is yours once you connect it")
    try:
        inked, _ = sketches.confirm(sketch, piece_ids)
    except SketchError as e:
        raise ApiError("bad_request", str(e)) from e
    daemon.twins.put(twin_id, sketch=inked)


def drop(daemon: Daemon, twin_id: str, piece_ids: list[str]) -> None:
    """The person rubs out her unconfirmed proposals."""
    row = daemon.twins.row(twin_id)
    not_busy(daemon, row["space_id"])
    try:
        kept, _ = sketches.drop(daemon.twins.sketch(twin_id), piece_ids)
    except SketchError as e:
        raise ApiError("bad_request", str(e)) from e
    daemon.twins.put(twin_id, sketch=kept)


# --- pieces a slip owns ------------------------------------------------------------------------------


def own_pieces(daemon: Daemon, twin_id: str, place: str, prefix: str, wanted: list[dict[str, Any]]) -> None:
    """The pieces in `place` whose id starts with `prefix` become `wanted` (each `{id, label, detail?,
    evidence?}`, the person's): a piece no longer wanted goes, a new one goes last, one kept stays
    where it is with its words brought up to date. A slip is the person's own act, so its pieces are ink."""
    sketch = daemon.twins.sketch(twin_id)
    want = {w["id"]: w for w in wanted}
    nodes: list[SketchNode] = []
    for node in sketch["nodes"]:
        if node["slot"] != place or not node["id"].startswith(prefix):
            nodes.append(node)
        elif node["id"] in want:
            nodes.append(_node(place, want[node["id"]]))
    have = {n["id"] for n in nodes}
    sketch = {"nodes": nodes, "edges": []}
    for w in wanted:
        if w["id"] in have:
            continue
        try:
            sketch, _ = sketches.apply(sketch, [{"op": "add", "node": _node(place, w)}], TWIN_RUBRIC)
        except SketchError as e:  # a bug in the slip's own words, not the person's
            raise ApiError("bad_request", str(e)) from e
        if w.get("evidence"):
            cast("dict[str, Any]", sketch["nodes"][-1])["evidence"] = list(w["evidence"])
    daemon.twins.put(twin_id, sketch=sketch)


def _node(place: str, w: dict[str, Any]) -> SketchNode:
    node = cast(
        "SketchNode",
        {
            "id": w["id"],
            "kind": "line",
            "slot": place,
            "label": cut(w["label"], LABEL_MAX),
            "origin": "you",
            "confirmed": True,
        },
    )
    if w.get("detail"):
        node["detail"] = w["detail"]
    if w.get("evidence"):
        cast("dict[str, Any]", node)["evidence"] = list(w["evidence"])
    return copy.deepcopy(node)


def cut(text: str, n: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= n else flat[: n - 1].rstrip(" ,;:.-") + "…"
