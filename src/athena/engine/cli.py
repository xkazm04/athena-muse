"""What the two CLI engines share: one subprocess call per model call, behind a seam tests replace.

A CLI engine has no function-calling API, so tools travel as op lines (see oplines.py). A reply whose
OP lines could not all be read is handled in two ways: when it still made at least one call, the notes
ride along into the next call's prompt as tool results; when it made none (the turn would end with the
person told something was done that was not), the engine asks once more, at once, with the notes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from athena.contracts import EngineId, Probe
from athena.engine import EngineError, TextDelta, ToolCall, Usage
from athena.engine.oplines import parse_reply

CLI_TIMEOUT_S = 300.0
#: Keys a child process never inherits: each would move a run off the person's plan, and neither CLI
#: needs the other's.
STRIPPED_KEYS = ("ANTHROPIC_API_KEY", "META_API_KEY")


@dataclass(frozen=True)
class CliCall:
    argv: list[str]
    stdin: str | None
    env: dict[str, str]
    cwd: Path


@dataclass(frozen=True)
class CliResult:
    stdout: list[str]
    stderr: str
    code: int


Runner = Callable[[CliCall], CliResult]


def run_cli(call: CliCall) -> CliResult:
    """The real runner. Plain-words errors for a missing program and a run that never ends."""
    try:
        done = subprocess.run(
            call.argv,
            input=call.stdin,
            env=call.env,
            cwd=call.cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CLI_TIMEOUT_S,
            check=False,
        )
    except FileNotFoundError as e:
        raise EngineError(f"Could not start {Path(call.argv[0]).name}; is it installed?") from e
    except subprocess.TimeoutExpired as e:
        raise EngineError(f"The model took longer than {int(CLI_TIMEOUT_S)} seconds and was stopped") from e
    return CliResult(done.stdout.splitlines(), done.stderr or "", done.returncode)


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in STRIPPED_KEYS:
        env.pop(name, None)
    return env


def which(program: str) -> str | None:
    """The program's full path (on Windows this finds a `.cmd` shim too)."""
    return shutil.which(program)


@dataclass(frozen=True)
class Reply:
    text: str
    usage: Usage | None


class OpLineEngine:
    """The shared half of a CLI engine. A subclass says how to run one call and read its output."""

    id: EngineId
    model: str
    simulated = False
    cost_estimated: bool

    def __init__(self, program: str, *, model: str, runner: Runner | None = None) -> None:
        self.program = program
        self.model = model
        self._runner: Runner = runner or run_cli
        self._next_id = 1
        self._notes: list[str] = []

    def __repr__(self) -> str:
        return f"{type(self).__name__}(model={self.model!r})"

    # A subclass implements this: one stateless CLI call over the whole conversation.
    def _call(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], notes: list[str], workdir: Path
    ) -> Reply:
        raise NotImplementedError

    def _run(self, call: CliCall) -> CliResult:
        return self._runner(call)

    def _once(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], notes: list[str]) -> Reply:
        with tempfile.TemporaryDirectory(prefix="athena-engine-") as tmp:
            return self._call(messages, tools, notes, Path(tmp))

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        notes, self._notes = self._notes, []
        reply = self._once(messages, tools, notes)
        parsed = parse_reply(reply.text, first=self._next_id)
        usages = [reply.usage]
        visible, calls, broken = parsed.visible, list(parsed.calls), parsed.broken
        if broken and not calls:
            # Nothing would run and the turn would end; hand the notes back now, once.
            retry = [*messages, {"role": "assistant", "content": reply.text}]
            again = self._once(retry, tools, broken)
            usages.append(again.usage)
            second = parse_reply(again.text, first=self._next_id)
            calls = list(second.calls)
            visible = visible or second.visible
            broken = second.broken
        self._next_id += len(calls)
        self._notes = broken
        if visible:
            # A reply after tool results continues the same message the person reads: keep a break.
            follows = bool(messages) and messages[-1].get("role") == "tool"
            yield TextDelta("\n\n" + visible if follows else visible)
        yield from calls
        counted = [u for u in usages if u is not None]
        if counted:
            costs = [u.cost_usd for u in counted if u.cost_usd is not None]
            yield Usage(
                sum(u.input_tokens for u in counted),
                sum(u.output_tokens for u in counted),
                round(sum(costs), 8) if costs else None,
            )

    def probe(self) -> Probe:
        started = time.monotonic()
        try:
            self._once([{"role": "user", "content": "Reply with the single word: ok"}], [], [])
        except EngineError as e:
            return {"ok": False, "error": e.reason}
        return {"ok": True, "model": self.model, "latency_ms": int((time.monotonic() - started) * 1000)}
