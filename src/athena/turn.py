"""One turn: frame the memory, call the engine, run the AUTO actions, file a card for the GATED ones."""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Generator, Iterator
from typing import TYPE_CHECKING, Any, TypeVar, cast
from urllib.parse import urlsplit

from athena import clock
from athena.app import Daemon
from athena.apps import tools as apps_tools
from athena.apps.client import is_loopback_url
from athena.browser import actions as browser
from athena.browser.actions import Dispatched
from athena.chores import reads
from athena.chores.portal import SEPARATOR, Portal
from athena.chores.spec import ChoreError, find_chore, load_chore
from athena.clock import mint
from athena.contracts import (
    AGENT_NOTE_MAX,
    APP_LABEL_MAX,
    APPS_MAX,
    BRIEF_MAX,
    CARD_WAIT_MAX_S,
    CATALOG,
    TEXT_MAX,
    TOOL_ROUNDS_MAX,
    ActionName,
    AppNew,
    Card,
    Surface,
    TurnPart,
    tool_event,
)
from athena.engine import Engine, EngineError, McpAccess, TextDelta, ToolCall, Usage
from athena.engine.prices import estimate
from athena.errors import ApiError
from athena.memory import visible_spaces
from athena.records import actions as records
from athena.report import chat as report_parts
from athena.spaces import normalise_origin

if TYPE_CHECKING:
    from athena.drafts.shape import Design

HISTORY_TURNS = 20
#: How long a turn's MCP lease lives: the CLI's own limit and a margin.
AGENT_LEASE_S = 420.0
EPISODE_PART_MAX = 600

LAW = (
    "You are Athena, a desktop companion who works for one person on their own computer. "
    "Be brief and plain. Some actions change things (a project's brief, its apps, what you keep in memory). "
    "Those marked as needing a signature only take effect after the person signs the card you file; "
    "until then say they are waiting, and never claim you did something a card is still waiting on. "
    "Use memory only from the sections below; do not invent what you remember."
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


TOOLS: dict[ActionName, dict[str, Any]] = {
    "recall": _tool(
        "recall", "Search what you remember for this person.", {"query": "What to look for"}, ["query"]
    ),
    "remember": _tool(
        "remember",
        "Keep one short fact for later. Runs at once, no signature needed.",
        {"text": "The fact, in one plain sentence"},
        ["text"],
    ),
    "forget": _tool(
        "forget",
        "Delete one kept memory by its id. Needs the person's signature.",
        {"id": "The memory id shown in the memory list"},
        ["id"],
    ),
    "propose_brief": _tool(
        "propose_brief",
        "Replace this project's brief. Needs the person's signature.",
        {"brief": "The full new brief"},
        ["brief"],
    ),
    "add_app": {
        "type": "function",
        "function": {
            "name": "add_app",
            "description": "Add an app to this project. website: a public site, by its address; it "
            "describes the project only, her browser trusts a site only once a chore's onboarding signs "
            "the person in there. local_page: a page on this computer (localhost). mcp_http: an app on "
            "this computer whose tools answer at a localhost address. mcp_stdio: a tool started from a "
            "command; the command you propose is shown to the person word for word, since signing it "
            "lets it run. Needs the person's signature.",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["website", "local_page", "mcp_http", "mcp_stdio"],
                        "description": "What kind of app it is",
                    },
                    "address": {
                        "type": "string",
                        "description": "website/local_page: the address, like https://example.com; "
                        "mcp_http: the address its tools answer at, like http://127.0.0.1:8080/mcp",
                    },
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "mcp_stdio only: the command and its arguments, one per item",
                    },
                    "label": {"type": "string", "description": "Optional: a short name for the app"},
                },
                "required": ["kind"],
            },
        },
    },
    # An outside agent's own tools (spark agent-leases): offered only on an agent's lease (mcp.py).
    "card_status": {
        "type": "function",
        "function": {
            "name": "card_status",
            "description": "Whether the person signed a card you filed: waiting, approved (with what it "
            "did) or declined. Only your own cards; any other id answers unknown. Can wait a little for "
            "the signature.",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_id": {"type": "string", "description": "The card id a pending call answered"},
                    "wait_seconds": {
                        "type": "number",
                        "description": f"Optional: wait up to this many seconds (at most {CARD_WAIT_MAX_S}) "
                        "for the person to decide",
                    },
                },
                "required": ["card_id"],
            },
        },
    },
    "note_add": _tool(
        "note_add",
        "Leave a short note in this project for the person and for the next agent. Notes are kept; "
        "none can be changed or removed.",
        {"text": f"The note, at most {AGENT_NOTE_MAX} characters"},
        ["text"],
    ),
    "note_list": _tool("note_list", "Read the notes agents left in this project, newest first.", {}, []),
}
#: The kinds `add_app` names (ADR 0025).
APP_KINDS = ("website", "local_page", "mcp_http", "mcp_stdio")


def _short(text: str, n: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def validate(daemon: Daemon, text: str, space_id: str) -> str:
    text = text.strip()
    if not text or len(text) > TEXT_MAX:
        raise ApiError("bad_request", f"say something between 1 and {TEXT_MAX} characters")
    if not daemon.spaces.exists(space_id):
        raise ApiError("unknown_ref", "that project is not there")
    return text


def run_turn(
    daemon: Daemon,
    engine: Engine,
    text: str,
    space_id: str,
    *,
    portal: Portal | None = None,
    design: Design | None = None,
) -> Iterator[dict[str, Any]]:
    """Validates now (so the route can answer a 4xx), streams when iterated. `portal` offers a
    chore's invented app as tools (ADR 0005): its READ tools answer at once, every other files a
    `portal_act` card without ending the round loop, so one reply can file a pile. `design` makes it
    a design turn (ADR 0007, 0010): ledgered on the design's surface, offering `recall` and the
    design's own tools only, and a reply with no words that changed and asked nothing ends in `error`."""
    text = validate(daemon, text, space_id)
    return _stream(daemon, engine, text, space_id, portal, design)


def _frame(daemon: Daemon, space_id: str, text: str) -> str:
    parts = [LAW]
    kept = daemon.memory.kept(space_id)
    if space_id != "":
        space = daemon.spaces.get(space_id)
        parts.append(f"## Project: {space['name']}")
        if space["brief"]:
            parts.append(space["brief"])
        if space["apps"]:
            hosts = [urlsplit(a).netloc or a for a in space["apps"]]
            parts.append("Apps in this project: " + ", ".join(hosts))
        sites = daemon.sites.list(space_id)
        if sites:  # ADR 0014: the sites her browser opens on its own here, and what the last look found
            said = {"signed_in": "signed in", "signed_out": "not signed in", "unknown": "not checked yet"}
            listed = [f"{urlsplit(s['origin']).netloc} ({said[s['access']]})" for s in sites]
            parts.append("Sites your browser opens on its own here: " + ", ".join(listed))
    if kept:
        parts.append("### Kept for this project" if space_id else "### Kept")
        parts.extend(f"- [{r['id']}] {r['line']}" for r in kept)
    kept_ids = {r["id"] for r in kept}
    recalled = [r for r in daemon.memory.recall(space_id, text) if r["id"] not in kept_ids]
    if recalled:
        parts.append("### From memory")
        parts.extend(f"- [{r['id']}] {r['line']}" for r in recalled)
    return "\n\n".join(parts)


def _messages(daemon: Daemon, space_id: str, text: str) -> list[dict[str, Any]]:
    # The person turn is already stored, so it closes the history.
    system = _frame(daemon, space_id, text)
    history = daemon.conversation.said(space_id, HISTORY_TURNS)
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for t in history:
        out.append({"role": "user" if t["role"] == "person" else "assistant", "content": t["text"]})
    return out


def _refuse_or_label(daemon: Daemon, space_id: str, call: ToolCall) -> tuple[str, dict[str, Any]] | str:
    """For a GATED call: (label, clean args) or a plain-words refusal to hand back as the tool result."""
    args = call.arguments
    if call.name in ("propose_brief", "add_app") and space_id == "":
        return "That needs a project; there is none open."
    if call.name == "propose_brief":
        brief = str(args.get("brief", "")).strip()
        if not brief or len(brief) > BRIEF_MAX:
            return f"A brief must be between 1 and {BRIEF_MAX} characters."
        return f"Change this project's brief to: {_short(brief, 100)}", {"brief": brief}
    if call.name == "add_app":
        return _add_app(daemon, space_id, args)
    mem_id = str(args.get("id", ""))
    try:
        row = daemon.memory.get(mem_id)
    except ApiError:
        return "There is no such memory."
    if row["space_id"] not in visible_spaces(space_id):
        return "There is no such memory."
    return f"Forget: {_short(row['line'], 100)}", {"id": mem_id}


def _command(argv: list[str]) -> str:
    """A command as the card shows it, word for word: a part with a space or a quote is quoted."""
    plain = [a if a and not any(c.isspace() or c in "\"'" for c in a) else json.dumps(a) for a in argv]
    return " ".join(plain)


def _add_app(daemon: Daemon, space_id: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]] | str:
    """An app she proposes, by kind (ADR 0025); the old `{origin}` form is a website or a local page
    by its host. The signed card adds it through `daemon.apps.add`, which checks it all again."""
    kind = args.get("kind")
    address = args.get("origin") if kind is None and "origin" in args else args.get("address")
    label = args.get("label")
    if label is not None and (not isinstance(label, str) or len(label) > APP_LABEL_MAX):
        return f"A name for the app is text of at most {APP_LABEL_MAX} characters."
    clean: dict[str, Any]
    if kind is None or kind in ("website", "local_page"):
        try:
            origin = normalise_origin(str(address or ""))
        except ApiError as e:
            return f"That is not an app address: {e.reason}"
        local = is_loopback_url(origin)
        if kind == "website" and local:
            return "That address is a page on this computer: propose it as a local_page."
        if kind == "local_page" and not local:
            return "A page on this computer has an address on localhost or 127.0.0.1."
        apps = daemon.spaces.get(space_id)["apps"]
        if origin in apps:
            return "That app is already in this project."
        if len(apps) >= APPS_MAX:
            return "This project has as many apps as it can hold."
        clean = {"kind": kind or ("local_page" if local else "website"), "address": origin}
        said = f"Add {origin} to this project"
    elif kind == "mcp_http":
        if not isinstance(address, str) or not is_loopback_url(address.strip()):
            return "An app's tools are reached only at an address on this computer (localhost)."
        clean = {"kind": kind, "address": address.strip()}
        said = f"Add the app answering at {address.strip()} to this project"
    elif kind == "mcp_stdio":
        argv = args.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            return "A tool she starts needs its command, as a list of its parts."
        if not argv[0].strip():
            return "A tool she starts needs its command, as a list of its parts."
        clean = {"kind": kind, "argv": list(argv)}
        said = f"Let this project start a tool with the command: {_command(argv)}"
    else:
        return f"Choose what kind of app it is: {', '.join(APP_KINDS)}."
    if isinstance(label, str) and label.strip():
        clean["label"] = label.strip()
    return said, clean


NOT_OFFERED = "That action is not offered here."


def dispatch(daemon: Daemon, space_id: str, call: ToolCall) -> Dispatched:
    """One catalog call, from a turn's round or from the MCP server (ADR 0015): an AUTO action runs
    and answers, a GATED one files a card. Her browser's actions decide with per-origin trust too."""
    name = call.name
    if name in browser.NAMES:
        return browser.act(daemon, space_id, name, call.arguments)
    if name in records.NAMES:  # a put of a non-find files a card whatever the class says
        return records.act(daemon, space_id, name, call.arguments)
    if name in report_parts.NAMES:  # report parts in the reply (ADR 0022): reads, never a card
        return report_parts.act(daemon, space_id, call.arguments)
    if (name not in CATALOG or name == apps_tools.FETCH) and apps_tools.owns(daemon, space_id, name):
        return apps_tools.act(daemon, space_id, name, call.arguments)  # a project's app tools (ADR 0025)
    if name not in CATALOG:
        return Dispatched("There is no such action.", refused=True)
    if CATALOG[name] == "auto":
        return _run_auto(daemon, space_id, call)
    if name not in ("propose_brief", "add_app", "forget"):
        return Dispatched("That action is not offered here.", refused=True)
    checked = _refuse_or_label(daemon, space_id, call)
    if isinstance(checked, str):
        return Dispatched(checked, refused=True)
    label, args = checked
    card = daemon.gate.file(space_id, name, args, label)
    return Dispatched(
        "Filed for the person to sign. Nothing has changed yet.",
        [tool_event(name, label), {"type": "card", "card": card}],
        card,
    )


def _record(
    daemon: Daemon,
    engine: Engine,
    surface: Surface,
    space_id: str,
    started: float,
    usage: Usage | None,
    error: str | None = None,
) -> float | None:
    """One ledger row for one engine call; answers its cost when there is one."""
    latency = int((time.monotonic() - started) * 1000)
    if error is not None:
        daemon.ledger.record(
            surface=surface,
            space_id=space_id,
            engine=engine.id,
            model=engine.model,
            latency_ms=latency,
            ok=False,
            error=error,
        )
        return None
    cost = None
    if usage is not None:
        cost = usage.cost_usd
        # A plan-billed engine (Muse Code) is never priced from the list: no figure is not $0.
        if cost is None and engine.cost_estimated:
            cost = estimate(engine.model, usage.input_tokens, usage.output_tokens)
    daemon.ledger.record(
        surface=surface,
        space_id=space_id,
        engine=engine.id,
        model=engine.model,
        latency_ms=latency,
        ok=True,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        cost_usd=cost,
        cost_estimated=engine.cost_estimated,
    )
    return cost


#: What a turn's rounds hand back: the reply's parts, the cards filed, the cost; None after an error
#: event was streamed.
Rounds = tuple[list[str], list[Card], float | None] | None

_R = TypeVar("_R")


class _Parts:
    """An Athena turn's parts as they stream past: text runs, tool lines and cards, in emitted order
    (inline-structured-rows: position is meaning). The settled turn keeps them, so her window draws it
    after a reload exactly as it drew it live. Each part keeps its moment, `at_ms` from the turn's start
    (ADR 0024), and an error's reason is kept as `stopped`."""

    def __init__(self) -> None:
        self.parts: list[TurnPart] = []
        self.started = clock.monotonic_ms()
        self.stopped: str | None = None

    def elapsed(self) -> int:
        return max(0, clock.monotonic_ms() - self.started)

    def see(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "text":
            delta = str(event.get("delta", ""))
            last = self.parts[-1] if self.parts else None
            if not delta:
                return
            if last is not None and last["kind"] == "text":
                last["text"] += delta
            else:
                self.parts.append({"kind": "text", "text": delta, "at_ms": self.elapsed()})
        elif kind == "tool":
            self.parts.append(
                {
                    "kind": "tool",
                    "name": event["name"],
                    "label": event["label"],
                    "class": event["class"],
                    "at_ms": self.elapsed(),
                }
            )
        elif kind == "card":
            self.parts.append({"kind": "card", "card_id": event["card"]["id"], "at_ms": self.elapsed()})
        elif kind == "blocks":  # kept with the figures they showed then (ADR 0022)
            self.parts.append({"kind": "blocks", "shown": event["shown"], "at_ms": self.elapsed()})
        elif kind == "error":
            self.stopped = str(event.get("reason", "")) or "The reply stopped before it finished"

    def watch(self, stream: Generator[dict[str, Any], None, _R]) -> Generator[dict[str, Any], None, _R]:
        """Passes `stream` through, seeing each event, and answers what it returned."""
        try:
            while True:
                try:
                    event = next(stream)
                except StopIteration as stop:
                    return cast("_R", stop.value)
                self.see(event)
                yield event
        finally:
            stream.close()


def _rounds(
    daemon: Daemon,
    engine: Engine,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    space_id: str,
    surface: Surface,
    portal: Portal | None,
    design: Design | None,
) -> Generator[dict[str, Any], None, Rounds]:
    """Up to TOOL_ROUNDS_MAX model calls; the turn runs each call's tools between them."""
    reply_parts: list[str] = []
    cards: list[Card] = []
    cost_total: float | None = None
    # A round runs only what it was offered: a model naming any other catalog action is refused.
    offered = {t.get("function", {}).get("name") for t in tools}
    for _ in range(TOOL_ROUNDS_MAX):
        started = time.monotonic()
        round_text: list[str] = []
        calls: list[ToolCall] = []
        usage: Usage | None = None
        # A design turn shows one line per frame: once a round has words, later rounds' words (the
        # model restating itself after its tools ran) are not shown or kept. Measured: joined rounds
        # repeated her line on both CLI engines (onboarding parity, no-repeats ~1.8 of 5).
        quiet = design is not None and design.one_line and any(part.strip() for part in reply_parts)
        try:
            for chunk in engine.complete(messages, tools):
                if isinstance(chunk, TextDelta):
                    round_text.append(chunk.text)
                    if not quiet:
                        yield {"type": "text", "delta": chunk.text}
                elif isinstance(chunk, ToolCall):
                    calls.append(chunk)
                else:
                    usage = chunk
        except EngineError as e:
            _record(daemon, engine, surface, space_id, started, None, e.reason)
            yield {"type": "error", "error": "engine_unavailable", "reason": e.reason}
            return None
        cost = _record(daemon, engine, surface, space_id, started, usage)
        if cost is not None:
            cost_total = (cost_total or 0.0) + cost
        if not quiet:
            reply_parts.append("".join(round_text))
        if not calls:
            break

        messages.append(
            {
                "role": "assistant",
                "content": "".join(round_text) or None,
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                    }
                    for c in calls
                ],
            }
        )
        filed = False
        for call in calls:
            name = call.name
            if design is not None and design.owns(name):
                result, events = design.call(call)
                yield from events
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
                continue
            if portal is not None and portal.owns(name):
                (answer, events), filed_card = _run_portal(daemon, space_id, portal, call)
                yield from events
                if filed_card is not None:
                    cards.append(filed_card)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": answer})
                continue
            if name not in offered:
                messages.append({"role": "tool", "tool_call_id": call.id, "content": NOT_OFFERED})
                continue
            done = dispatch(daemon, space_id, call)
            yield from done.events
            if done.card is not None:
                cards.append(done.card)
                filed = True
            messages.append({"role": "tool", "tool_call_id": call.id, "content": done.result})
        if filed or (design is not None and design.round_done()):
            break
    return reply_parts, cards, cost_total


def _agent(
    daemon: Daemon,
    engine: Engine,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    space_id: str,
    surface: Surface,
) -> Generator[dict[str, Any], None, Rounds]:
    """An engine that calls tools itself (ADR 0015): one run against Athena's MCP server under a lease
    for this turn. The server's lines and cards arrive through the lease and stream in order with the
    engine's words; the lease ends with the run."""
    assert daemon.mcp_url is not None
    inbox: queue.Queue[tuple[str, Any]] = queue.Queue()
    names = frozenset(t["function"]["name"] for t in tools)
    lease = daemon.mcp.mint(space_id, ttl=AGENT_LEASE_S, tools=names, sink=lambda e: inbox.put(("event", e)))
    access = McpAccess(daemon.mcp_url, lease.token, sorted(names))
    agent = getattr(engine, "agent")  # noqa: B009 - the Protocol has no agent(); tools_on says it exists

    def work() -> None:
        try:
            for item in agent(messages, access):
                inbox.put(("item", item))
            inbox.put(("end", None))
        except EngineError as e:
            inbox.put(("end", e.reason))
        except Exception as e:  # a crash in the reader must still end the turn
            inbox.put(("end", f"the engine stopped ({type(e).__name__})"))

    started = time.monotonic()
    threading.Thread(target=work, name="athena-agent", daemon=True).start()
    parts: list[str] = []
    cards: list[Card] = []
    usage: Usage | None = None
    try:
        while True:
            kind, item = inbox.get()
            if kind == "event":
                if item.get("type") == "card":
                    cards.append(item["card"])
                yield item
            elif kind == "item":
                if isinstance(item, TextDelta):
                    parts.append(item.text)
                    yield {"type": "text", "delta": item.text}
                elif isinstance(item, Usage):
                    usage = item
            else:
                error = item
                break
    finally:
        daemon.mcp.drop(lease.token)
    if error is not None:
        _record(daemon, engine, surface, space_id, started, None, error)
        yield {"type": "error", "error": "engine_unavailable", "reason": error}
        return None
    cost = _record(daemon, engine, surface, space_id, started, usage)
    return ["".join(parts)], cards, cost


def _stream(
    daemon: Daemon,
    engine: Engine,
    text: str,
    space_id: str,
    portal: Portal | None = None,
    design: Design | None = None,
) -> Iterator[dict[str, Any]]:
    surface: Surface = design.surface if design is not None else "turn"
    with daemon.busy.turn(space_id), daemon.busy.chat(space_id):
        turn_id = mint("turn_")
        seen = _Parts()  # the turn's clock starts here
        yield {"type": "start", "turn_id": turn_id, "engine": engine.id, "simulated": engine.simulated}
        daemon.conversation.append(space_id, "person", text)
        messages = _messages(daemon, space_id, text)
        if design is not None:
            tools = [TOOLS["recall"], *design.tools()]
            messages[0]["content"] += "\n\n" + design.frame()
        else:
            tools = [TOOLS[n] for n in ("recall", "remember", "forget")]
            if space_id != "":
                tools += [TOOLS["propose_brief"], TOOLS["add_app"]]
            if portal is None:
                tools += browser.offered(daemon, space_id) + records.offered(daemon, space_id)
                tools += report_parts.offered(daemon, space_id) + apps_tools.offered(daemon, space_id)
        if portal is not None:
            tools += portal.tools()
            messages[0]["content"] += (
                "\n\n" + portal.frame() + reads.frame(daemon, space_id) + _waiting(daemon, space_id)
            )

        agentic = design is None and portal is None and daemon.mcp_url is not None
        if agentic and getattr(engine, "tools_on", False):
            outcome = yield from seen.watch(_agent(daemon, engine, messages, tools, space_id, surface))
        else:
            outcome = yield from seen.watch(
                _rounds(daemon, engine, messages, tools, space_id, surface, portal, design)
            )
        if outcome is None:
            if design is None and portal is None and seen.stopped is not None:
                # ADR 0024: the stopped turn is kept, with what streamed before it and why it stopped,
                # so a reload shows the try and its reason instead of a question standing alone.
                daemon.conversation.append(
                    space_id,
                    "athena",
                    "",
                    parts=seen.parts,
                    duration_ms=seen.elapsed(),
                    stopped=seen.stopped,
                )
                daemon.events.publish({"type": "turn_done", "space_id": space_id, "turn_id": turn_id})
            return
        reply_parts, cards, cost_total = outcome

        reply = "".join(reply_parts).strip()
        closing: list[dict[str, Any]] = []
        if design is not None:
            if not reply and not design.progressed:
                # Not a frame: nothing is stored, the draft is left as it was.
                yield {
                    "type": "error",
                    "error": "engine_unavailable",
                    "reason": "She did not answer; try again.",
                }
                return
            if not reply:
                reply = design.fallback()
                yield {"type": "text", "delta": reply}
            closing = design.settle()
            reply = design.record(reply)
        elif not reply:
            if len(cards) > 1:
                reply = f"I filed {len(cards)} cards for you to sign."
            elif cards:
                reply = f"I filed a card for you to sign: {cards[0]['label']}"
            else:
                reply = "I have nothing to add."
            said: dict[str, Any] = {"type": "text", "delta": reply}
            seen.see(said)
            yield said
        daemon.conversation.append(
            space_id,
            "athena",
            reply,
            cost_usd=cost_total,
            card_id=cards[0]["id"] if cards else None,
            # A design turn's words are re-recorded by the stage (`design.record`); its frames are not
            # chat parts, so it keeps the plain text.
            parts=seen.parts if design is None else None,
            duration_ms=seen.elapsed() if design is None else None,
        )
        daemon.memory.append_episode(
            space_id, f"Person: {text[:EPISODE_PART_MAX]}\nAthena: {reply[:EPISODE_PART_MAX]}"
        )
        daemon.events.publish({"type": "turn_done", "space_id": space_id, "turn_id": turn_id})
        yield from closing
        done: dict[str, Any] = {"type": "done", "turn_id": turn_id, "waiting": bool(cards)}
        if cost_total is not None:
            done["cost_usd"] = cost_total
        yield done


def _portal_for(daemon: Daemon, args: dict[str, Any]) -> Portal:
    """The Portal a signed `portal_act` card was filed through, rebuilt from its args. The chore is
    found in the library or among the person's own (ADR 0007)."""
    chore_id = str(args.get("chore", ""))
    found = find_chore(chore_id, daemon.data_dir)
    if found is None:
        raise ApiError("unknown_ref", "the chore that card belongs to is not in the library")
    root, origin = found
    try:
        chore = load_chore(root, origin=origin)
    except ChoreError as e:
        raise ApiError("bad_request", f"the chore {chore_id} cannot be loaded: {e}") from e
    return Portal(chore, str(args.get("app", "")))


#: How many waiting cards the frame lists; more are counted, not listed.
WAITING_LISTED = 40


def _waiting(daemon: Daemon, space_id: str) -> str:
    """The portal cards already filed in this space and still unsigned, so a later turn (a nudge,
    the next phase) does not file one again: the history carries her words, not her cards."""
    waiting = [
        c for c in daemon.gate.list("waiting") if c["space_id"] == space_id and c["action"] == "portal_act"
    ]
    if not waiting:
        return ""
    lines = [
        "",
        "",
        "## Already filed, waiting for the person's signature",
        "Do not file these again; file only what is not on this list.",
    ]
    lines += [f"- {c['label']}" for c in waiting[:WAITING_LISTED]]
    if len(waiting) > WAITING_LISTED:
        lines.append(f"- and {len(waiting) - WAITING_LISTED} more")
    return "\n".join(lines)


def _sign_add_app(daemon: Daemon, space_id: str, args: dict[str, Any]) -> str:
    """A signed `add_app`: `daemon.apps.add` checks and writes it (raising returns the card to
    waiting). A card filed in the old `{origin}` form is a website or a local page by its host."""
    if "kind" not in args and "origin" in args:
        origin = str(args["origin"])
        if origin in daemon.spaces.get(space_id)["apps"]:
            return f"Added {origin} to the project."
        args = {"kind": "local_page" if is_loopback_url(origin) else "website", "address": origin}
    body: AppNew = {"kind": args["kind"]}
    if "address" in args:
        body["address"] = args["address"]
    if "argv" in args:
        body["argv"] = args["argv"]
    if "label" in args:
        body["label"] = args["label"]
    app = daemon.apps.add(space_id, body)
    if app["kind"] in ("website", "local_page"):
        return f"Added {app['address']} to the project."
    return f"Added {app['label']} to the project."


def _run_auto(daemon: Daemon, space_id: str, call: ToolCall) -> Dispatched:
    """One of the turn's own AUTO actions: it runs and streams its line, or it is refused."""
    if call.name == "recall":
        rows = daemon.memory.recall(space_id, str(call.arguments.get("query", "")))
        result = "\n".join(f"- {r['line']}" for r in rows) or "Nothing found."
        return Dispatched(result, [tool_event("recall", "Looked through memory")])
    if call.name != "remember":  # an AUTO action this turn did not offer (the stage's sketch, ask)
        return Dispatched("That action is not offered here.", refused=True)
    fact = str(call.arguments.get("text", "")).strip()
    if not fact:
        return Dispatched("Nothing to remember.", refused=True)
    daemon.memory.write_fact(space_id, fact)
    return Dispatched("Kept.", [tool_event("remember", f"Remembered: {_short(fact)}")])


def _run_portal(
    daemon: Daemon, space_id: str, portal: Portal, call: ToolCall
) -> tuple[tuple[str, list[dict[str, Any]]], Card | None]:
    """((tool result, events to stream), the card filed if any) for a call the portal owns."""
    if portal.is_read(call.name):
        result, label = portal.read(call.name, call.arguments)
        tool = call.name.split(SEPARATOR, 1)[-1]
        reads.record(daemon, space_id, portal.app_id, tool, dict(call.arguments), result)
        return (result, [tool_event("portal_read", label)] if label else []), None
    checked = portal.check(call.name, call.arguments)
    if isinstance(checked, str):
        return (checked, []), None
    label, args = checked
    card = daemon.gate.file(space_id, "portal_act", args, label)
    events = [tool_event("portal_act", label), {"type": "card", "card": card}]
    return ("Filed for the person to sign. Nothing has changed yet.", events), card


def execute(daemon: Daemon, card: Card) -> str:
    """Runs one approved card. The gate calls this exactly once, after the decision won; raising
    returns the card to waiting."""
    space_id = card["space_id"]
    args = card["args"]
    if card["action"] == "propose_brief":
        daemon.spaces.update(space_id, {"brief": args["brief"]})
        return "The project's brief is changed."
    if card["action"] == "add_app":
        return _sign_add_app(daemon, space_id, args)
    if card["action"] == "app_act":
        return apps_tools.execute(daemon, card)
    if card["action"] == "agent_grant":  # an outside agent's unattended calls (spark agent-leases)
        return daemon.agents.sign(card)
    if card["action"] == "forget":
        daemon.memory.forget(args["id"])
        return "Forgotten."
    if card["action"] == "portal_act":
        return _portal_for(daemon, args).execute(args)
    if card["action"] in browser.NAMES:
        return browser.execute(daemon, card)
    if card["action"] == "record_put":
        return records.execute(daemon, card)
    if card["action"] == "setup_act":
        from athena.peer import setup  # a machine-changing step of the setup conversation (ADR 0017)

        return setup.sign(daemon, card)
    if card["action"] == "twin_send_web":
        # A twin's message on a web channel, sent through her browser (business Phase 2).
        from athena.twins import web

        return web.sign(daemon, card)
    if card["action"] in ("twin_send", "twin_note"):
        # One Gmail message in-thread, or one Notion note (ADR 0009). Imported here: the twins
        # package runs its setup turn through this module.
        from athena.twins import missions

        return missions.sign(daemon, card)
    raise ApiError("bad_request", "that action cannot be signed")
