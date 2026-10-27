"""The engine seam: Muse over its API, Muse Code or Claude Code on the plan, or a scripted stand-in."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from athena.contracts import EngineId, EngineStatus, Probe
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
DEFAULT_MODELS: dict[EngineId, str] = {
    "muse": DEFAULT_MODEL,
    "muse_code": DEFAULT_MODEL,
    "claude_code": "sonnet",
    "scripted": "scripted",
}


def choose(keys: KeyStore) -> EngineId:
    """The one place the engine is chosen. `ATHENA_ENGINE` wins; unset, `muse` with a key, else
    `scripted`. Every site that needs the engine (build, status, probe, run) asks here."""
    raw = os.environ.get("ATHENA_ENGINE", "").strip().lower()
    if not raw:
        return "muse" if keys.get() else "scripted"
    for engine_id in ENGINES:
        if raw == engine_id:
            return engine_id
    raise EngineError("ATHENA_ENGINE must be one of muse, muse_code, claude_code or scripted")


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
    keys: KeyStore, *, transport: httpx.BaseTransport | None = None, runner: Runner | None = None
) -> Engine:
    """Builds the chosen engine, or says in plain words what is missing. `runner` replaces the CLI
    subprocess call (tests)."""
    from athena.engine.claude_code import ClaudeCodeEngine
    from athena.engine.cli import which
    from athena.engine.meta import MuseEngine
    from athena.engine.muse_code import MuseCodeEngine
    from athena.engine.scripted import ScriptedEngine

    engine_id = choose(keys)
    if engine_id == "scripted":
        return ScriptedEngine()
    model = engine_model(engine_id)
    if engine_id in ("muse", "muse_code") and "contributor" in model.lower():
        raise EngineError("That model trains on your content, so Athena will not use it")
    if engine_id == "muse":
        key = keys.get()
        if key is None:
            raise EngineError("There is no Meta key: add one in Settings or set META_API_KEY")
        base = os.environ.get("META_BASE_URL", "").strip() or DEFAULT_BASE_URL
        return MuseEngine(key, model=model, base_url=base, transport=transport)
    program = which(PROGRAMS[engine_id])
    if engine_id == "muse_code":
        if program is None:
            raise EngineError("Muse Code is not installed: put `muse` on PATH, or set another ATHENA_ENGINE")
        return MuseCodeEngine(program, model=model, runner=runner)
    if program is None:
        raise EngineError("Claude Code is not installed: put `claude` on PATH, or set another ATHENA_ENGINE")
    return ClaudeCodeEngine(program, model=model, runner=runner)


def status(keys: KeyStore) -> EngineStatus:
    """The engine `choose` picks, as the windows show it. Raises EngineError on a bad ATHENA_ENGINE."""
    engine_id = choose(keys)
    return {
        "engine": engine_id,
        "model": engine_model(engine_id),
        "key": keys.source(),
        "simulated": engine_id == "scripted",
    }
