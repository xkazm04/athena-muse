"""The engine seam: Muse over its API, Muse Code or Claude Code on the plan, or a scripted stand-in."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from athena.contracts import EngineId, EngineOption, EngineSource, EngineStatus, Probe
from athena.keys import KeyStore

if TYPE_CHECKING:
    import httpx

    from athena.engine.cli import Runner

DEFAULT_MODEL = "muse-spark-1.3"
DEFAULT_BASE_URL = "https://api.meta.ai/v1"


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    #: What the call cost when the engine itself says so (a CLI that reports its bill); `None`
    #: leaves pricing to prices.py, or to nobody for an engine on the person's plan.
    cost_usd: float | None = None


@dataclass(frozen=True)
class McpAccess:
    """How an engine that calls tools itself reaches Athena's MCP server for one turn (ADR 0015)."""

    url: str
    token: str  # the turn's lease; never the daemon's token
    tools: list[str]


class EngineError(Exception):
    """A model call that failed. `reason` is plain words, safe to show."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class Engine(Protocol):
    id: EngineId
    model: str
    simulated: bool
    #: The ledger marks this engine's costs as estimates (list prices, or a CLI's own figure).
    cost_estimated: bool

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]: ...

    def probe(self) -> Probe: ...


ENGINES: tuple[EngineId, ...] = ("muse", "muse_code", "claude_code", "scripted")
PROGRAMS: dict[EngineId, str] = {"muse_code": "muse", "claude_code": "claude"}
NO_KEY = "There is no Meta key: add one in Settings or set META_API_KEY"
NOT_INSTALLED: dict[EngineId, str] = {
    "muse_code": "Muse Code is not installed: put `muse` on PATH, or set another ATHENA_ENGINE",
    "claude_code": "Claude Code is not installed: put `claude` on PATH, or set another ATHENA_ENGINE",
}
DEFAULT_MODELS: dict[EngineId, str] = {
    "muse": DEFAULT_MODEL,
    "muse_code": DEFAULT_MODEL,
    "claude_code": "sonnet",
    "scripted": "scripted",
}


def _known(raw: str) -> EngineId | None:
    raw = raw.strip().lower()
    for engine_id in ENGINES:
        if raw == engine_id:
            return engine_id
    return None


def decide(keys: KeyStore, stored: str = "") -> tuple[EngineId, EngineSource]:
    """The one place the engine is chosen, and who chose it (ADR 0006, ADR 0012 as amended).

    Settings is the place to change the engine: the stored choice wins whenever it can run (a key
    for `muse`, the program on PATH for a CLI). Else `ATHENA_ENGINE`, for the bench, the seams and
    a fresh data folder. Else the default: `muse` with a key, else the first installed CLI wrapper
    (Claude Code, then Muse Code), else `scripted`, labelled simulated."""
    chosen = _known(stored)
    if chosen is not None and runnable(chosen, keys):
        return chosen, "setting"
    raw = os.environ.get("ATHENA_ENGINE", "").strip()
    if raw:
        pinned = _known(raw)
        if pinned is None:
            raise EngineError("ATHENA_ENGINE must be one of muse, muse_code, claude_code or scripted")
        return pinned, "env"
    return fallback(keys), "default"


def runnable(engine_id: EngineId, keys: KeyStore) -> bool:
    """Whether an engine can run here, read without calling it: a key for Muse, a program on PATH
    for a CLI wrapper. Signed in or not is the probe's to say."""
    from athena.engine.cli import which

    if engine_id == "muse":
        return bool(keys.get())
    if engine_id in PROGRAMS:
        return which(PROGRAMS[engine_id]) is not None
    return True


def fallback(keys: KeyStore) -> EngineId:
    """The engine with nothing chosen: Muse with a key, else an installed CLI, else simulated."""
    for engine_id in ("muse", "claude_code", "muse_code"):
        if runnable(engine_id, keys):
            return engine_id
    return "scripted"


def choose(keys: KeyStore, stored: str = "") -> EngineId:
    """The engine `decide` picks. Every site that needs the engine (build, status, probe, run) asks
    here; the daemon passes the stored Settings choice, the CLIs pass none."""
    return decide(keys, stored)[0]


def options(keys: KeyStore) -> list[EngineOption]:
    """Every engine as Settings offers it, read without calling one: a key on file, a program on PATH.
    Whether the key works or the CLI is signed in is the probe's to say."""
    from athena.engine.cli import which

    found: list[EngineOption] = []
    for engine_id in ENGINES:
        if engine_id == "scripted":
            found.append({"id": engine_id, "readiness": "simulated"})
        elif engine_id == "muse":
            found.append(
                {"id": engine_id, "readiness": "ready"}
                if keys.get()
                else {"id": engine_id, "readiness": "no_key", "reason": NO_KEY}
            )
        elif which(PROGRAMS[engine_id]) is None:
            found.append({"id": engine_id, "readiness": "not_installed", "reason": NOT_INSTALLED[engine_id]})
        else:
            found.append({"id": engine_id, "readiness": "ready"})
    return found


def engine_model(engine_id: EngineId) -> str:
    """`ATHENA_MODEL` overrides any real engine; `META_MODEL` still works for `muse`. The scripted
    engine is always `scripted`: a label on a simulated row, never a model name."""
    if engine_id == "scripted":
        return "scripted"
    chosen = os.environ.get("ATHENA_MODEL", "").strip()
    if not chosen and engine_id == "muse":
        chosen = os.environ.get("META_MODEL", "").strip()
    return chosen or DEFAULT_MODELS[engine_id]


def model_name() -> str:
    """The Muse API engine's model (kept for callers that ask without an engine)."""
    return engine_model("muse")


def build_engine(
    keys: KeyStore,
    *,
    stored: str = "",
    transport: httpx.BaseTransport | None = None,
    runner: Runner | None = None,
) -> Engine:
    """Builds the chosen engine, or says in plain words what is missing. `stored` is the Settings
    choice (ADR 0012); `runner` replaces the CLI subprocess call (tests)."""
    from athena.engine.claude_code import ClaudeCodeEngine
    from athena.engine.cli import which
    from athena.engine.meta import MuseEngine
    from athena.engine.muse_code import MuseCodeEngine
    from athena.engine.scripted import ScriptedEngine

    engine_id = choose(keys, stored)
    if engine_id == "scripted":
        return ScriptedEngine()
    model = engine_model(engine_id)
    if engine_id in ("muse", "muse_code") and "contributor" in model.lower():
        raise EngineError("That model trains on your content, so Athena will not use it")
    if engine_id == "muse":
        key = keys.get()
        if key is None:
            raise EngineError(NO_KEY)
        base = os.environ.get("META_BASE_URL", "").strip() or DEFAULT_BASE_URL
        return MuseEngine(key, model=model, base_url=base, transport=transport)
    program = which(PROGRAMS[engine_id])
    if engine_id == "muse_code":
        if program is None:
            raise EngineError(NOT_INSTALLED["muse_code"])
        return MuseCodeEngine(program, model=model, runner=runner)
    if program is None:
        raise EngineError(NOT_INSTALLED["claude_code"])
    return ClaudeCodeEngine(program, model=model, runner=runner)


def status(keys: KeyStore, stored: str = "") -> EngineStatus:
    """The engine `choose` picks, as the windows show it. Raises EngineError on a bad ATHENA_ENGINE."""
    engine_id = choose(keys, stored)
    return {
        "engine": engine_id,
        "model": engine_model(engine_id),
        "key": keys.source(),
        "simulated": engine_id == "scripted",
    }
