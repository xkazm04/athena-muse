"""Op lines: a text grammar for tool calls, for engines that have no function-calling API to bind.

The tools are written into the system message as instructions; the model calls one by writing a line
`OP: {"tool": "<name>", "args": {...}}`. Everything else it writes is what the person reads. The whole
conversation is rendered back as one prompt, so every call to such an engine is stateless.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from athena.engine import ToolCall

PREFIX = "OP:"
SHOWN_MAX = 80  # characters of a broken line quoted back to the model

RULE = (
    'To call a tool, write a line `OP: {"tool": "<name>", "args": {...}}` on its own line, in compact '
    "JSON, one line per call. You may write as many OP lines as there are calls. Everything else you write "
    "is what the person reads, so never mention OP lines to them."
)

_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_BARE_KEY = re.compile(r"([{,]\s*)([A-Za-z_][\w-]*)\s*:")


@dataclass(frozen=True)
class Parsed:
    visible: str
    calls: list[ToolCall]
    #: One plain-words note per OP line that could not be read, to hand back to the model.
    broken: list[str]


def render_tools(tools: list[dict[str, Any]]) -> str:
    """The OpenAI function list as instructions to append to the system message. Empty when no tools."""
    if not tools:
        return ""
    parts = ["## Tools", RULE, ""]
    for tool in tools:
        fn = tool.get("function") or {}
        name = str(fn.get("name") or "")
        if not name:
            continue
        parts.append(f"### {name}")
        if fn.get("description"):
            parts.append(str(fn["description"]))
        params = fn.get("parameters") or {}
        props = params.get("properties") or {}
        required = set(params.get("required") or [])
        for key, spec in props.items():
            kind = str(spec.get("type") or "string") if isinstance(spec, dict) else "string"
            desc = str(spec.get("description") or "") if isinstance(spec, dict) else ""
            need = "required" if key in required else "optional"
            parts.append(f"- `{key}` ({kind}, {need}){': ' + desc if desc else ''}")
        example = {k: "..." for k in props if k in required}
        parts.append("Call: OP: " + json.dumps({"tool": name, "args": example}, separators=(",", ":")))
        parts.append("")
    return "\n".join(parts).rstrip()


def _loads(raw: str) -> Any:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except ValueError:
        pass
    fixed = raw.rstrip().rstrip(",").rstrip()
    fixed = _TRAILING_COMMA.sub(r"\1", fixed)
    fixed = _BARE_KEY.sub(r'\1"\2":', fixed)
    return json.loads(fixed)  # a ValueError here means the line is not JSON


def parse_reply(text: str, *, first: int = 1) -> Parsed:
    """Splits a reply into what the person reads and the calls. Ids are `call_<n>` counting from `first`."""
    visible: list[str] = []
    calls: list[ToolCall] = []
    broken: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(PREFIX):
            visible.append(line)
            continue
        raw = stripped[len(PREFIX) :]
        shown = raw.strip()[:SHOWN_MAX]
        try:
            value = _loads(raw)
        except ValueError:
            broken.append(f"your OP line was not JSON: {shown}")
            continue
        name = value.get("tool") if isinstance(value, dict) else None
        args = value.get("args", {}) if isinstance(value, dict) else None
        if not isinstance(name, str) or not name.strip() or not isinstance(args, dict):
            broken.append(f'your OP line needs "tool" (a name) and "args" (an object): {shown}')
            continue
        calls.append(ToolCall(f"call_{first + len(calls)}", name.strip(), args))
    return Parsed("\n".join(visible).strip(), calls, broken)


def parse(text: str) -> tuple[str, list[ToolCall]]:
    """(visible text, tool calls). Use `parse_reply` to also get the notes for unreadable lines."""
    parsed = parse_reply(text)
    return parsed.visible, parsed.calls


def op_line(call: dict[str, Any]) -> str:
    """An OpenAI tool_call rendered back as the OP line the model would have written."""
    fn = call.get("function") or {}
    raw = fn.get("arguments") or "{}"
    try:
        args = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        args = {}
    body = {"tool": str(fn.get("name") or ""), "args": args if isinstance(args, dict) else {}}
    return PREFIX + " " + json.dumps(body, ensure_ascii=False, separators=(",", ":"))


def system_text(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
    """Every system message joined, then the tool instructions."""
    parts = [str(m.get("content") or "") for m in messages if m.get("role") == "system"]
    rendered = render_tools(tools)
    if rendered:
        parts.append(rendered)
    return "\n\n".join(p for p in parts if p.strip())


def transcript(
    messages: list[dict[str, Any]], *, notes: list[str] | None = None, include_system: bool = True
) -> str:
    """The OpenAI message list as one prompt: a stateless call sees the whole conversation.

    `notes` are tool-result lines with no call of their own (an OP line that could not be read); they
    follow the last message. `include_system=False` leaves the system messages to a separate channel.
    """
    names: dict[str, str] = {}
    parts: list[str] = []
    for m in messages:
        role = m.get("role")
        content = str(m.get("content") or "").strip()
        if role == "system":
            if include_system and content:
                parts.append(f"## System\n{content}")
        elif role == "user":
            parts.append(f"## Person\n{content}")
        elif role == "assistant":
            lines = [content] if content else []
            for call in m.get("tool_calls") or []:
                names[str(call.get("id") or "")] = str((call.get("function") or {}).get("name") or "")
                lines.append(op_line(call))
            parts.append("## Athena\n" + "\n".join(lines))
        elif role == "tool":
            call_id = str(m.get("tool_call_id") or "")
            label = names.get(call_id, "")
            parts.append(f"## Tool result ({label or call_id})\n{content}")
    for note in notes or []:
        parts.append(f"## Tool result (OP line)\n{note}")
    parts.append("## Athena\n(Write Athena's next message now: what the person reads, and any OP lines.)")
    return "\n\n".join(parts)
