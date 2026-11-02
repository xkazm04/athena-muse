"""What the two CLI engines share: one subprocess call per model call, behind a seam tests replace.

A CLI engine has no function-calling API, so tools travel as op lines (see oplines.py). A reply whose
OP lines could not all be read is handled in two ways: when it still made at least one call, the notes
ride along into the next call's prompt as tool results; when it made none (the turn would end with the
person told something was done that was not), the engine asks once more, at once, with the notes.
"""

from __future__ import annotations

import contextvars
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from athena.contracts import EngineId, Probe
from athena.engine import EngineError, TextDelta, ToolCall, Usage
from athena.engine.oplines import parse_reply

CLI_TIMEOUT_S = 300.0
#: The words a model call ends with when the person pressed Stop (a draft's job maps them to `stopped`).
STOPPED = "You stopped her."
#: How often a running call looks at its limit and its Stop.
WATCH_S = 0.1
#: Keys a child process never inherits: each would move a run off the person's plan, and neither CLI
#: needs the other's.
STRIPPED_KEYS = ("ANTHROPIC_API_KEY", "META_API_KEY")


@dataclass(frozen=True)
class CallLimits:
    """What ends a model call early: a wall clock (None: none at all, a draft's writing) and a Stop."""

    timeout_s: float | None = CLI_TIMEOUT_S
    cancel: threading.Event | None = None


#: The limits of the calls made on this thread; unset means the default (CLI_TIMEOUT_S, no Stop), read
#: when the call starts, so every caller that never sets them (chat, twins, the bench) is unchanged.
_LIMITS: contextvars.ContextVar[CallLimits | None] = contextvars.ContextVar(
    "athena_call_limits", default=None
)


def current_limits() -> CallLimits:
    set_ = _LIMITS.get()
    return set_ if set_ is not None else CallLimits(CLI_TIMEOUT_S, None)


@contextmanager
def call_limits(limits: CallLimits) -> Iterator[None]:
    """Every model call made inside runs under `limits` (a draft's job sets them on its thread)."""
    token = _LIMITS.set(limits)
    try:
        yield
    finally:
        _LIMITS.reset(token)


def stopped() -> bool:
    """Whether the person pressed Stop on the work running on this thread."""
    cancel = current_limits().cancel
    return cancel is not None and cancel.is_set()


def check_stopped() -> None:
    """Raises EngineError(STOPPED) once the person pressed Stop: a call not yet started never starts."""
    if stopped():
        raise EngineError(STOPPED)


def kill_tree(proc: subprocess.Popen[str]) -> None:
    """Ends the process and everything it started (a CLI wrapper runs the model in a child)."""
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    if proc.poll() is None:
        proc.kill()


class _Watch:
    """Watches one running process against its limits; kills its tree at the wall clock or on Stop."""

    def __init__(self, proc: subprocess.Popen[str], limits: CallLimits) -> None:
        self._proc = proc
        self._limits = limits
        self._done = threading.Event()
        self.why: str | None = None
        self._thread = threading.Thread(target=self._watch, name="cli-watch", daemon=True)

    def __enter__(self) -> _Watch:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._done.set()
        self._thread.join()

    def _watch(self) -> None:
        timeout, cancel = self._limits.timeout_s, self._limits.cancel
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self._done.wait(WATCH_S):
            if cancel is not None and cancel.is_set():
                self.why = STOPPED
            elif deadline is not None and time.monotonic() >= deadline:
                self.why = f"The model took longer than {timeout or 0:g} seconds and was stopped"
            else:
                continue
            kill_tree(self._proc)
            return

    def raise_if_stopped(self) -> None:
        if self.why is not None:
            raise EngineError(self.why)


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
    """The real runner. Plain-words errors for a missing program, a run past its limit and a Stop."""
    limits = current_limits()
    check_stopped()
    try:
        proc = subprocess.Popen(
            call.argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=call.env,
            cwd=call.cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as e:
        raise EngineError(f"Could not start {Path(call.argv[0]).name}; is it installed?") from e
    with _Watch(proc, limits) as watch:
        stdout, stderr = proc.communicate(call.stdin)
    watch.raise_if_stopped()
    return CliResult(stdout.splitlines(), stderr or "", proc.returncode)


#: Runs one CLI call and hands back its stdout line by line as it comes (an engine with tools on).
Streamer = Callable[[CliCall], Iterator[str]]


def stream_cli(call: CliCall) -> Iterator[str]:
    """The real streamer: stdout lines as they arrive; the run is stopped at its limit (CLI_TIMEOUT_S
    unless a job set another) or on Stop, and says so. Its stderr is not kept: the final line says how
    it ended."""
    limits = current_limits()
    check_stopped()
    try:
        proc = subprocess.Popen(
            call.argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=call.env,
            cwd=call.cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as e:
        raise EngineError(f"Could not start {Path(call.argv[0]).name}; is it installed?") from e
    with _Watch(proc, limits) as watch:
        try:
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(call.stdin or "")
            proc.stdin.close()
            yield from (line.rstrip("\n") for line in proc.stdout)
            proc.wait()
        finally:
            if proc.poll() is None:
                kill_tree(proc)
                proc.wait()
    watch.raise_if_stopped()


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
