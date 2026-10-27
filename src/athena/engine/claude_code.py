"""Claude Code on the person's plan, as a development engine: `claude -p`, every built-in tool off.

Measured on Claude Code 2.1.311, 2026-10-27: `--tools ""` disables every built-in tool (the init line
lists `"tools": []`), `--strict-mcp-config` with no config loads no MCP server, `--setting-sources ""`
skips the user's hooks and settings while keeping the plan sign-in (`--bare` would drop it), and
`--system-prompt-file` replaces the default system prompt. Usage is read from the final `result` line,
which sums the whole call; cached input counts as input.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from athena.contracts import EngineId
from athena.engine import EngineError, Usage
from athena.engine.cli import CliCall, OpLineEngine, Reply, child_env
from athena.engine.oplines import system_text, transcript

DEFAULT_MODEL = "sonnet"
_INPUT_KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def argv(program: str, model: str, system_file: Path) -> list[str]:
    return [
        program,
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        model,
        "--system-prompt-file",
        str(system_file),
        "--tools",
        "",
        "--strict-mcp-config",
        "--setting-sources",
        "",
        "--no-session-persistence",
    ]


def read_stream(lines: list[str]) -> tuple[str, Usage | None, str | None]:
    """(reply text, usage, error words). Lines that are not JSON, or not ours, are skipped."""
    texts: list[str] = []
    usage: Usage | None = None
    error: str | None = None
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "assistant":
            content = (event.get("message") or {}).get("content") or []
            texts.extend(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        elif event.get("type") == "result":
            raw = event.get("usage") or {}
            cost = event.get("total_cost_usd")
            usage = Usage(
                sum(int(raw.get(k) or 0) for k in _INPUT_KEYS),
                int(raw.get("output_tokens") or 0),
                float(cost) if isinstance(cost, int | float) else None,
            )
            if event.get("is_error"):
                error = str(event.get("result") or event.get("subtype") or "an error")[:200]
    return "\n".join(t for t in texts if t), usage, error


class ClaudeCodeEngine(OpLineEngine):
    id: EngineId = "claude_code"
    #: The CLI's own `total_cost_usd`, at list prices: on a plan it is an estimate, not a bill.
    cost_estimated = True

    def _call(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], notes: list[str], workdir: Path
    ) -> Reply:
        system_file = workdir / "system.md"
        system_file.write_text(system_text(messages, tools) or "You are Athena.", encoding="utf-8")
        prompt = transcript(messages, notes=notes, include_system=False)
        result = self._run(CliCall(argv(self.program, self.model, system_file), prompt, child_env(), workdir))
        text, usage, error = read_stream(result.stdout)
        if error is not None:
            raise EngineError(f"Claude Code answered with an error: {error}")
        if usage is None:
            low = result.stderr.lower()
            if "login" in low or "not logged in" in low or "authenticat" in low:
                raise EngineError("Claude Code is not signed in: run claude and sign in")
            raise EngineError(f"Claude Code stopped without an answer (exit {result.code})")
        return Reply(text, usage)
