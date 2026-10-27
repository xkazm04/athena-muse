from __future__ import annotations

from typing import Any

from athena.engine import ToolCall
from athena.engine.oplines import parse, parse_reply, render_tools, system_text, transcript


def tool(name: str, **props: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"The {name} tool.",
            "parameters": {
                "type": "object",
                "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
                "required": list(props),
            },
        },
    }


def test_render_names_each_tool_its_params_and_the_rule() -> None:
    out = render_tools([tool("recall", query="What to look for"), tool("remember", text="The fact")])
    assert "### recall" in out and "### remember" in out
    assert "`query` (string, required): What to look for" in out
    assert 'OP: {"tool": "<name>", "args": {...}}' in out
    assert "one line per call" in out and "as many OP lines" in out
    assert 'Call: OP: {"tool":"recall","args":{"query":"..."}}' in out
    assert render_tools([]) == ""


def test_two_op_lines_in_one_reply() -> None:
    text = (
        "Let me look.\n"
        'OP: {"tool":"recall","args":{"query":"tea"}}\n'
        'OP: {"tool":"remember","args":{"text":"Likes tea"}}\n'
        "Done."
    )
    visible, calls = parse(text)
    assert visible == "Let me look.\nDone."
    assert calls == [
        ToolCall("call_1", "recall", {"query": "tea"}),
        ToolCall("call_2", "remember", {"text": "Likes tea"}),
    ]


def test_trailing_comma_and_bare_keys_are_tolerated() -> None:
    parsed = parse_reply(
        'OP: {tool: "recall", args: {query: "tea",},},\n  OP: {"tool":"forget","args":{"id":"m1"}},', first=7
    )
    assert parsed.broken == []
    assert parsed.calls == [
        ToolCall("call_7", "recall", {"query": "tea"}),
        ToolCall("call_8", "forget", {"id": "m1"}),
    ]


def test_a_broken_line_is_dropped_and_reported() -> None:
    parsed = parse_reply('Sure.\nOP: {"tool": "recall", "args": {"query": tea}\nOP: ["recall"]')
    assert parsed.visible == "Sure."
    assert parsed.calls == []
    assert parsed.broken[0].startswith('your OP line was not JSON: {"tool": "recall"')
    assert '"tool"' in parsed.broken[1] and "args" in parsed.broken[1]


def test_broken_note_quotes_at_most_80_chars() -> None:
    parsed = parse_reply("OP: {" + "x" * 200)
    assert len(parsed.broken[0]) == len("your OP line was not JSON: ") + 80


def test_missing_args_means_empty_args() -> None:
    assert parse('OP: {"tool":"recall"}')[1] == [ToolCall("call_1", "recall", {})]


def test_round_trip_render_then_parse() -> None:
    """A call the model writes in the rendered form parses back to the tool and args it named."""
    rendered = render_tools([tool("add_app", origin="An origin")])
    example = next(line for line in rendered.splitlines() if line.startswith("Call: "))[len("Call: ") :]
    visible, calls = parse("Adding it.\n" + example.replace("...", "https://example.com"))
    assert visible == "Adding it."
    assert calls == [ToolCall("call_1", "add_app", {"origin": "https://example.com"})]


def test_transcript_renders_every_role_and_calls_as_op_lines() -> None:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "You are Athena."},
        {"role": "user", "content": "What do I drink?"},
        {
            "role": "assistant",
            "content": "Let me look.",
            "tool_calls": [
                {
                    "id": "c9",
                    "type": "function",
                    "function": {"name": "recall", "arguments": '{"query":"drink"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c9", "content": "- Likes green tea"},
    ]
    out = transcript(messages, notes=["your OP line was not JSON: {oops"])
    order = ["## System", "## Person", "## Athena\nLet me look.", "## Tool result (recall)", "(OP line)"]
    assert [out.index(s) for s in order] == sorted(out.index(s) for s in order)
    assert 'OP: {"tool":"recall","args":{"query":"drink"}}' in out
    assert out.rstrip().endswith("and any OP lines.)")
    assert "## System" not in transcript(messages, include_system=False)


def test_system_text_appends_the_tools() -> None:
    out = system_text([{"role": "system", "content": "Law."}], [tool("recall", query="q")])
    assert out.startswith("Law.\n\n## Tools")
