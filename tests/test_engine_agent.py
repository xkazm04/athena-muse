"""Claude Code with tools on (ADR 0015): one run against Athena's MCP server under the turn's lease.
The fake streamer plays Claude Code: it reads the MCP config it was handed, calls the server the way
the CLI would (in process, with the lease as bearer), then prints recorded stream-json lines."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from athena import mcp
from athena.app import Daemon
from athena.engine import EngineError, McpAccess, TextDelta, Usage
from athena.engine.claude_code import AGENT_TURNS_MAX, ClaudeCodeEngine
from athena.engine.cli import CliCall
from athena.turn import run_turn


def _assistant(text: str) -> str:
    return json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})


RESULT = json.dumps(
    {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "total_cost_usd": 0.012,
        "usage": {"input_tokens": 900, "cache_read_input_tokens": 100, "output_tokens": 40},
    }
)


class Agent:
    """Calls `tools` through the server, then answers `lines`."""

    def __init__(self, daemon: Daemon, tools: list[tuple[str, dict[str, Any]]], lines: list[str]) -> None:
        self.daemon = daemon
        self.tools = tools
        self.lines = lines
        self.calls: list[CliCall] = []
        self.answers: list[dict[str, Any]] = []

    def __call__(self, call: CliCall) -> Iterator[str]:
        self.calls.append(call)
        config = json.loads(Path(call.argv[call.argv.index("--mcp-config") + 1]).read_text(encoding="utf-8"))
        server = config["mcpServers"]["athena"]
        token = server["headers"]["Authorization"].removeprefix("Bearer ")
        lease = self.daemon.mcp.get(token)
        assert lease is not None
        for i, (name, args) in enumerate(self.tools, 1):
            msg = {
                "jsonrpc": "2.0",
                "id": i,
                "method": "tools/call",
                "params": {"name": name, "arguments": args},
            }
            answer = mcp.handle(self.daemon, lease, msg)
            assert answer is not None
            self.answers.append(answer["result"])
        yield from self.lines


def test_the_argv_turns_builtins_off_and_names_only_athenas_server(tmp_path: Path) -> None:
    seen: list[CliCall] = []

    def stream(call: CliCall) -> Iterator[str]:
        seen.append(call)
        cfg = json.loads(Path(call.argv[call.argv.index("--mcp-config") + 1]).read_text(encoding="utf-8"))
        assert cfg == {
            "mcpServers": {
                "athena": {
                    "type": "http",
                    "url": "http://127.0.0.1:9/mcp",
                    "headers": {"Authorization": "Bearer lease-x"},
                }
            }
        }
        yield _assistant("Hello.")
        yield RESULT

    engine = ClaudeCodeEngine("claude", model="sonnet", streamer=stream)
    out = list(
        engine.agent(
            [{"role": "user", "content": "hi"}],
            McpAccess("http://127.0.0.1:9/mcp", "lease-x", ["recall", "page_read"]),
        )
    )
    argv = seen[0].argv
    assert argv[argv.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in argv and argv[argv.index("--setting-sources") + 1] == ""
    assert argv[argv.index("--allowedTools") + 1] == "mcp__athena__recall,mcp__athena__page_read"
    assert argv[argv.index("--max-turns") + 1] == str(AGENT_TURNS_MAX)
    assert "ANTHROPIC_API_KEY" not in seen[0].env
    assert out == [TextDelta("Hello."), Usage(1000, 40, 0.012)]
    assert not Path(argv[argv.index("--mcp-config") + 1]).exists()  # the lease's file is gone with the run


def test_an_error_result_or_no_result_is_an_engine_error() -> None:
    bad = json.dumps({"type": "result", "is_error": True, "result": "Not logged in", "usage": {}})
    engine = ClaudeCodeEngine("claude", model="sonnet", streamer=lambda _: iter([bad]))
    with pytest.raises(EngineError, match="Not logged in"):
        list(engine.agent([], McpAccess("u", "t", [])))
    engine = ClaudeCodeEngine("claude", model="sonnet", streamer=lambda _: iter([]))
    with pytest.raises(EngineError, match="without an answer"):
        list(engine.agent([], McpAccess("u", "t", [])))


def test_a_turn_with_tools_on_streams_the_servers_lines_and_cards_in_order(daemon: Daemon) -> None:
    daemon.mcp_url = "http://127.0.0.1:9/mcp"
    space = daemon.spaces.create({"name": "Channel"})["id"]
    agent = Agent(
        daemon,
        [
            ("remember", {"text": "The channel posts on Fridays"}),
            ("propose_brief", {"brief": "An AI-music channel."}),
        ],
        [_assistant("I kept that, and the new brief waits for your signature."), RESULT],
    )
    engine = ClaudeCodeEngine("claude", model="sonnet", streamer=agent)
    assert engine.tools_on
    events = list(run_turn(daemon, engine, "Remember we post on Fridays and set the brief", space))
    kinds = [e["type"] for e in events]
    assert kinds == ["start", "tool", "tool", "card", "text", "done"]
    assert events[1]["name"] == "remember" and events[2]["name"] == "propose_brief"
    card = events[3]["card"]
    assert agent.answers[1]["structuredContent"] == {"pending": {"card_id": card["id"]}}
    assert daemon.spaces.get(space)["brief"] == ""  # nothing changes until the person signs
    assert events[-1]["waiting"] is True and events[-1]["cost_usd"] == pytest.approx(0.012)
    [row] = daemon.ledger.page(5)["rows"]  # one row for the whole run
    assert row["engine"] == "claude_code" and row["ok"] and row["input_tokens"] == 1000
    turns = daemon.conversation.list(space, 5)
    assert turns[-1]["text"].startswith("I kept that") and turns[-1].get("card_id") == card["id"]


def test_the_lease_ends_with_the_turn(daemon: Daemon) -> None:
    daemon.mcp_url = "http://127.0.0.1:9/mcp"
    tokens: list[str] = []

    def stream(call: CliCall) -> Iterator[str]:
        cfg = json.loads(Path(call.argv[call.argv.index("--mcp-config") + 1]).read_text(encoding="utf-8"))
        tokens.append(cfg["mcpServers"]["athena"]["headers"]["Authorization"].removeprefix("Bearer "))
        yield _assistant("Hi.")
        yield RESULT

    list(run_turn(daemon, ClaudeCodeEngine("claude", model="sonnet", streamer=stream), "hello", ""))
    assert tokens and daemon.mcp.get(tokens[0]) is None


def test_tools_off_keeps_op_lines(daemon: Daemon, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATHENA_CLAUDE_TOOLS", "0")
    daemon.mcp_url = "http://127.0.0.1:9/mcp"

    def stream(_: CliCall) -> Iterator[str]:
        raise AssertionError("tools off never streams")

    engine = ClaudeCodeEngine("claude", model="sonnet", streamer=stream, runner=lambda c: _batch())
    assert not engine.tools_on
    events = list(run_turn(daemon, engine, "hello", ""))
    assert events[-1]["type"] == "done"


def _batch() -> Any:
    from athena.engine.cli import CliResult

    return CliResult([_assistant("Hello there."), RESULT], "", 0)
