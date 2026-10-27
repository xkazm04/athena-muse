"""One turn: frame the memory, call the engine, run the AUTO actions, file a card for the GATED ones."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from athena.app import Daemon
from athena.clock import mint
from athena.contracts import (
    APPS_MAX,
    BRIEF_MAX,
    CATALOG,
    TEXT_MAX,
    TOOL_ROUNDS_MAX,
    ActionName,
    Card,
    tool_event,
)
from athena.engine import Engine, EngineError, TextDelta, ToolCall, Usage
from athena.engine.prices import estimate
from athena.errors import ApiError
from athena.memory import visible_spaces
from athena.spaces import normalise_origin

if TYPE_CHECKING:
    from athena.chores.portal import Portal

HISTORY_TURNS = 20
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
        "Add a web app to this project by its origin. Needs the person's signature.",
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
    daemon: Daemon, engine: Engine, text: str, space_id: str, *, portal: Portal | None = None
) -> Iterator[dict[str, Any]]:
    """Validates now (so the route can answer a 4xx), streams when iterated. `portal` offers a
    chore's invented app as tools (ADR 0005; WP2 wires it into the round loop)."""
    text = validate(daemon, text, space_id)
    return _stream(daemon, engine, text, space_id, portal)


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


def _stream(
    daemon: Daemon, engine: Engine, text: str, space_id: str, portal: Portal | None = None
) -> Iterator[dict[str, Any]]:
    with daemon.busy.turn(space_id):
        turn_id = mint("turn_")
        yield {"type": "start", "turn_id": turn_id, "engine": engine.id, "simulated": engine.simulated}
        daemon.conversation.append(space_id, "person", text)
        messages = _messages(daemon, space_id, text)
        tools = [TOOLS[n] for n in ("recall", "remember", "forget")]
        if space_id != "":
            tools += [TOOLS["propose_brief"], TOOLS["add_app"]]

        reply_parts: list[str] = []
        cards: list[Card] = []
        cost_total: float | None = None
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
                daemon.ledger.record(
                    surface="turn",
                    space_id=space_id,
                    engine=engine.id,
                    model=engine.model,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    ok=False,
                    error=e.reason,
                )
                yield {"type": "error", "error": "engine_unavailable", "reason": e.reason}
                return
            cost = None
            if usage is not None:
                cost = usage.cost_usd
                if cost is None:
                    cost = estimate(engine.model, usage.input_tokens, usage.output_tokens)
            daemon.ledger.record(
                surface="turn",
                space_id=space_id,
                engine=engine.id,
                model=engine.model,
                latency_ms=int((time.monotonic() - started) * 1000),
                ok=True,
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
                cost_usd=cost,
                cost_estimated=engine.cost_estimated,
            )
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
                result = ""
                name = call.name
                if name not in CATALOG:
                    result = "There is no such action."
                elif CATALOG[name] == "auto":
                    result, label = _run_auto(daemon, space_id, call)
                    if label:
                        yield tool_event(name, label)
                else:
                    checked = _refuse_or_label(daemon, space_id, call)
                    if isinstance(checked, str):
                        result = checked
                    else:
                        label, args = checked
                        card = daemon.gate.file(space_id, name, args, label)
                        cards.append(card)
                        filed = True
                        yield tool_event(name, label)
                        yield {"type": "card", "card": card}
                        result = "Filed for the person to sign. Nothing has changed yet."
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
            if filed:
                break

        reply = "".join(reply_parts).strip()
        if not reply:
            reply = (
                f"I filed a card for you to sign: {cards[0]['label']}" if cards else "I have nothing to add."
            )
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
        done: dict[str, Any] = {"type": "done", "turn_id": turn_id, "waiting": bool(cards)}
        if cost_total is not None:
            done["cost_usd"] = cost_total
        yield done


def _run_auto(daemon: Daemon, space_id: str, call: ToolCall) -> tuple[str, str]:
    """(tool result, on-screen label). An empty label means nothing happened worth a line."""
    if call.name == "recall":
        rows = daemon.memory.recall(space_id, str(call.arguments.get("query", "")))
        result = "\n".join(f"- {r['line']}" for r in rows) or "Nothing found."
        return result, "Looked through memory"
    fact = str(call.arguments.get("text", "")).strip()
    if not fact:
        return "Nothing to remember.", ""
    daemon.memory.write_fact(space_id, fact)
    return "Kept.", f"Remembered: {_short(fact)}"


def execute(daemon: Daemon, card: Card) -> str:
    """Runs one approved card. The gate calls this exactly once, after the decision won."""
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
    raise ApiError("bad_request", "that action cannot be signed")
