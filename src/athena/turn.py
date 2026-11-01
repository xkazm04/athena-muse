"""One turn: frame the memory, call the engine, run the AUTO actions, file a card for the GATED ones."""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Generator, Iterator
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from athena.app import Daemon
from athena.browser import actions as browser
from athena.browser.actions import Dispatched
from athena.chores import reads
from athena.chores.portal import SEPARATOR, Portal
from athena.chores.spec import ChoreError, find_chore, load_chore
from athena.clock import mint
from athena.contracts import (
    APPS_MAX,
    BRIEF_MAX,
    CATALOG,
    TEXT_MAX,
    TOOL_ROUNDS_MAX,
    ActionName,
    Card,
    Surface,
    tool_event,
)
from athena.engine import Engine, EngineError, McpAccess, TextDelta, ToolCall, Usage
from athena.engine.prices import estimate
from athena.errors import ApiError
from athena.memory import visible_spaces
from athena.records import actions as records
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
    "add_app": _tool(
        "add_app",
        "Name a web app this project is about, by its address. It describes the project only: her "
        "browser trusts a site only once a chore's onboarding signs the person in there. Needs the "
        "person's signature.",
        {"origin": "The app's address, like https://example.com"},
        ["origin"],
    ),
}


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
    history = daemon.conversation.list(space_id, HISTORY_TURNS)
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
        try:
            origin = normalise_origin(str(args.get("origin", "")))
        except ApiError as e:
            return f"That is not an app address: {e.reason}"
        apps = daemon.spaces.get(space_id)["apps"]
        if origin in apps:
            return "That app is already in this project."
        if len(apps) >= APPS_MAX:
            return "This project has as many apps as it can hold."
        return f"Add {origin} to this project", {"origin": origin}
    mem_id = str(args.get("id", ""))
    try:
        row = daemon.memory.get(mem_id)
    except ApiError:
        return "There is no such memory."
    if row["space_id"] not in visible_spaces(space_id):
        return "There is no such memory."
    return f"Forget: {_short(row['line'], 100)}", {"id": mem_id}


NOT_OFFERED = "That action is not offered here."


def dispatch(daemon: Daemon, space_id: str, call: ToolCall) -> Dispatched:
    """One catalog call, from a turn's round or from the MCP server (ADR 0015): an AUTO action runs
    and answers, a GATED one files a card. Her browser's actions decide with per-origin trust too."""
    name = call.name
    if name in browser.NAMES:
        return browser.act(daemon, space_id, name, call.arguments)
    if name in records.NAMES:  # a put of a non-find files a card whatever the class says
        return records.act(daemon, space_id, name, call.arguments)
    if name not in CATALOG:
        return Dispatched("There is no such action.")
    if CATALOG[name] == "auto":
        result, label = _run_auto(daemon, space_id, call)
        return Dispatched(result, [tool_event(name, label)] if label else [])
    if name not in ("propose_brief", "add_app", "forget"):
        return Dispatched("That action is not offered here.")
    checked = _refuse_or_label(daemon, space_id, call)
    if isinstance(checked, str):
        return Dispatched(checked)
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
        try:
            for chunk in engine.complete(messages, tools):
                if isinstance(chunk, TextDelta):
                    round_text.append(chunk.text)
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
        if filed:
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
        if portal is not None:
            tools += portal.tools()
            messages[0]["content"] += (
                "\n\n" + portal.frame() + reads.frame(daemon, space_id) + _waiting(daemon, space_id)
            )

        agentic = design is None and portal is None and daemon.mcp_url is not None
        if agentic and getattr(engine, "tools_on", False):
            outcome = yield from _agent(daemon, engine, messages, tools, space_id, surface)
        else:
            outcome = yield from _rounds(daemon, engine, messages, tools, space_id, surface, portal, design)
        if outcome is None:
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
            yield {"type": "text", "delta": reply}
        daemon.conversation.append(
            space_id,
            "athena",
            reply,
            cost_usd=cost_total,
            card_id=cards[0]["id"] if cards else None,
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


def _run_auto(daemon: Daemon, space_id: str, call: ToolCall) -> tuple[str, str]:
    """(tool result, on-screen label). An empty label means nothing happened worth a line."""
    if call.name == "recall":
        rows = daemon.memory.recall(space_id, str(call.arguments.get("query", "")))
        result = "\n".join(f"- {r['line']}" for r in rows) or "Nothing found."
        return result, "Looked through memory"
    if call.name != "remember":  # an AUTO action this turn did not offer (the stage's sketch, ask)
        return "That action is not offered here.", ""
    fact = str(call.arguments.get("text", "")).strip()
    if not fact:
        return "Nothing to remember.", ""
    daemon.memory.write_fact(space_id, fact)
    return "Kept.", f"Remembered: {_short(fact)}"


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
        existing = list(daemon.spaces.get(space_id)["apps"])
        if args["origin"] not in existing:
            existing.append(args["origin"])
            daemon.spaces.update(space_id, {"apps": existing})
        return f"Added {args['origin']} to the project."
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
