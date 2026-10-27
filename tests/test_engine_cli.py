"""The two CLI engines over a fake runner: no real CLI is ever spawned."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from athena.engine import EngineError, TextDelta, ToolCall, Usage
from athena.engine.claude_code import ClaudeCodeEngine
from athena.engine.cli import CliCall, CliResult
from athena.engine.muse_code import MuseCodeEngine

FIXTURES = Path(__file__).parent / "fixtures"
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Keep one fact.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }
]
MESSAGES: list[dict[str, Any]] = [
    {"role": "system", "content": "You are Athena."},
    {"role": "user", "content": "I like green tea"},
]


class Fake:
    """Replays recorded stdout lines and keeps what each call would have run (files read while live)."""

    def __init__(self, *outputs: list[str], stderr: str = "", code: int = 0) -> None:
        self.outputs = list(outputs)
        self.stderr = stderr
        self.code = code
        self.calls: list[CliCall] = []
        self.files: list[dict[str, str]] = []

    def __call__(self, call: CliCall) -> CliResult:
        self.calls.append(call)
        self.files.append({p.name: p.read_text(encoding="utf-8") for p in call.cwd.iterdir()})
        return CliResult(self.outputs.pop(0) if self.outputs else [], self.stderr, self.code)


def lines(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


def claude_text(text: str, cost: float | None = 0.001) -> list[str]:
    result: dict[str, Any] = {
        "type": "result",
        "is_error": False,
        "usage": {"input_tokens": 5, "output_tokens": 2},
    }
    if cost is not None:
        result["total_cost_usd"] = cost
    message = {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}
    return [json.dumps(message), json.dumps(result)]


def muse_text(text: str) -> list[str]:
    return [
        json.dumps({"payload_type": "run.output.delta", "payload": {"text": text}}),
        json.dumps(
            {"payload_type": "run.usage", "payload": {"models": [{"input_tokens": 9, "output_tokens": 1}]}}
        ),
        json.dumps({"payload_type": "run.terminal.completed", "payload": {}}),
    ]


# --- claude_code --------------------------------------------------------------------------------


def test_claude_reads_the_recorded_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    monkeypatch.setenv("META_API_KEY", "meta-secret")
    fake = Fake(lines("engine_claude_code.jsonl"))
    out = list(ClaudeCodeEngine("claude", model="sonnet", runner=fake).complete(MESSAGES, TOOLS))
    assert out == [
        TextDelta("Let me look, and keep that."),
        ToolCall("call_1", "recall", {"query": "tea"}),
        ToolCall("call_2", "remember", {"text": "Likes green tea"}),
        Usage(763, 132, 0.004328),
    ]
    call = fake.calls[0]
    assert call.argv[:6] == ["claude", "-p", "--output-format", "stream-json", "--verbose", "--model"]
    assert call.argv[call.argv.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in call.argv and "--no-session-persistence" in call.argv
    assert "ANTHROPIC_API_KEY" not in call.env and "META_API_KEY" not in call.env
    assert call.stdin is not None and "## Person\nI like green tea" in call.stdin
    assert "## System" not in call.stdin
    system = fake.files[0]["system.md"]
    assert system.startswith("You are Athena.") and "### remember" in system


def test_claude_ids_keep_counting_across_rounds() -> None:
    op = 'OP: {"tool":"remember","args":{"text":"a"}}'
    engine = ClaudeCodeEngine("claude", model="sonnet", runner=Fake(claude_text(op), claude_text(op)))
    first = [c for c in engine.complete(MESSAGES, TOOLS) if isinstance(c, ToolCall)]
    second = [c for c in engine.complete(MESSAGES, TOOLS) if isinstance(c, ToolCall)]
    assert [first[0].id, second[0].id] == ["call_1", "call_2"]


def test_claude_without_a_cost_reports_none() -> None:
    engine = ClaudeCodeEngine("claude", model="sonnet", runner=Fake(claude_text("hi", cost=None)))
    assert list(engine.complete(MESSAGES, []))[-1] == Usage(5, 2, None)
    assert engine.cost_estimated is True and engine.simulated is False and engine.id == "claude_code"


def test_claude_error_result_is_plain_words() -> None:
    bad = [json.dumps({"type": "result", "is_error": True, "result": "Model not found", "usage": {}})]
    with pytest.raises(EngineError, match="Claude Code answered with an error: Model not found"):
        list(ClaudeCodeEngine("claude", model="nope", runner=Fake(bad)).complete(MESSAGES, []))


def test_claude_with_no_result_line() -> None:
    with pytest.raises(EngineError, match="not signed in"):
        list(
            ClaudeCodeEngine("claude", model="s", runner=Fake([], stderr="Not logged in", code=1)).complete(
                [], []
            )
        )
    with pytest.raises(EngineError, match="exit 3"):
        list(ClaudeCodeEngine("claude", model="s", runner=Fake([], code=3)).complete([], []))


def test_a_reply_with_only_broken_lines_is_asked_again_once() -> None:
    broken = "Saving it.\nOP: {tool: remember, args: {text: tea}}"
    fixed = 'OP: {"tool":"remember","args":{"text":"tea"}}'
    fake = Fake(claude_text(broken, cost=0.001), claude_text(fixed, cost=0.002))
    out = list(ClaudeCodeEngine("claude", model="sonnet", runner=fake).complete(MESSAGES, TOOLS))
    assert out == [
        TextDelta("Saving it."),
        ToolCall("call_1", "remember", {"text": "tea"}),
        Usage(10, 4, 0.003),
    ]
    assert len(fake.calls) == 2
    second = fake.calls[1].stdin or ""
    assert "## Athena\nSaving it.\nOP: {tool: remember" in second
    assert "## Tool result (OP line)\nyour OP line was not JSON: {tool: remember" in second


def test_a_broken_line_beside_a_good_one_rides_into_the_next_call() -> None:
    reply = 'OP: {"tool":"remember","args":{"text":"a"}}\nOP: {nope'
    fake = Fake(claude_text(reply), claude_text("All set."))
    engine = ClaudeCodeEngine("claude", model="sonnet", runner=fake)
    calls = [c for c in engine.complete(MESSAGES, TOOLS) if isinstance(c, ToolCall)]
    assert len(calls) == 1 and len(fake.calls) == 1
    list(engine.complete(MESSAGES, TOOLS))
    assert "## Tool result (OP line)\nyour OP line was not JSON: {nope" in (fake.calls[1].stdin or "")


# --- muse_code ----------------------------------------------------------------------------------


def test_muse_reads_the_msp_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    monkeypatch.setenv("META_API_KEY", "meta-secret")
    fake = Fake(lines("engine_muse_code.jsonl"))
    engine = MuseCodeEngine("muse.cmd", model="muse-spark-1.3", runner=fake)
    out = list(engine.complete(MESSAGES, TOOLS))
    assert out == [
        TextDelta("I will keep that."),
        ToolCall("call_1", "remember", {"text": "Likes green tea"}),
        Usage(15222, 44, None),
    ]
    call = fake.calls[0]
    assert call.stdin is None
    assert call.argv[:3] == ["muse.cmd", "exec", "--json"]
    flags = " ".join(call.argv)
    assert "--contributor-mode off" in flags and "--preset empty" in flags and "--disable-shell" in flags
    assert "META_API_KEY" not in call.env and "ANTHROPIC_API_KEY" not in call.env
    prompt = fake.files[0]["prompt.md"]
    assert prompt.startswith("## System\nYou are Athena.") and "## Person\nI like green tea" in prompt
    assert call.argv[call.argv.index("--prompt-file") + 1] == str(call.cwd / "prompt.md")
    assert engine.cost_estimated is False and engine.id == "muse_code"


def test_muse_runs_in_a_fresh_directory_each_call() -> None:
    fake = Fake(muse_text("a"), muse_text("b"))
    engine = MuseCodeEngine("muse", model="m", runner=fake)
    list(engine.complete(MESSAGES, []))
    list(engine.complete(MESSAGES, []))
    assert fake.calls[0].cwd != fake.calls[1].cwd
    assert not fake.calls[0].cwd.exists()


def test_muse_not_signed_in() -> None:
    fake = Fake([], stderr="error: not logged in: run `muse login` first", code=1)
    with pytest.raises(EngineError) as e:
        list(MuseCodeEngine("muse", model="m", runner=fake).complete(MESSAGES, []))
    assert e.value.reason == "Muse Code is not signed in: run muse login"


def test_muse_failed_run_and_a_run_that_never_ended() -> None:
    failed = [json.dumps({"payload_type": "run.terminal.failed", "payload": {"reason": "model unavailable"}})]
    with pytest.raises(EngineError, match="Muse Code could not answer: model unavailable"):
        list(MuseCodeEngine("muse", model="m", runner=Fake(failed)).complete(MESSAGES, []))
    cut = muse_text("half")[:1]
    with pytest.raises(EngineError, match="without an answer"):
        list(MuseCodeEngine("muse", model="m", runner=Fake(cut, code=2)).complete(MESSAGES, []))


def test_probe_is_one_call_and_says_the_model() -> None:
    fake = Fake(muse_text("ok"))
    result = MuseCodeEngine("muse", model="muse-spark-1.3", runner=fake).probe()
    assert result["ok"] is True and result["model"] == "muse-spark-1.3" and len(fake.calls) == 1
    bad = MuseCodeEngine("muse", model="m", runner=Fake([], stderr="not logged in")).probe()
    assert bad == {"ok": False, "error": "Muse Code is not signed in: run muse login"}


def test_a_reply_after_tool_results_starts_on_its_own_paragraph() -> None:
    after = [*MESSAGES, {"role": "tool", "tool_call_id": "call_1", "content": "Kept."}]
    out = list(MuseCodeEngine("muse", model="m", runner=Fake(muse_text("Saved."))).complete(after, []))
    assert out[0] == TextDelta("\n\nSaved.")
