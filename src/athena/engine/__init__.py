"""The engine seam: Muse over an OpenAI-compatible API, or a deterministic scripted stand-in."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from athena.contracts import EngineId, EngineStatus, Probe
from athena.keys import KeyStore

if TYPE_CHECKING:
    import httpx

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


class EngineError(Exception):
    """A model call that failed. `reason` is plain words, safe to show."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class Engine(Protocol):
    id: EngineId
    model: str
    simulated: bool

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]: ...

    def probe(self) -> Probe: ...


def model_name() -> str:
    return os.environ.get("META_MODEL", "").strip() or DEFAULT_MODEL


def build_engine(keys: KeyStore, *, transport: httpx.BaseTransport | None = None) -> Engine:
    from athena.engine.meta import MuseEngine
    from athena.engine.scripted import ScriptedEngine

    key = keys.get()
    if key is None:
        return ScriptedEngine()
    model = model_name()
    if "contributor" in model.lower():
        raise EngineError("That model trains on your content, so Athena will not use it")
    base = os.environ.get("META_BASE_URL", "").strip() or DEFAULT_BASE_URL
    return MuseEngine(key, model=model, base_url=base, transport=transport)


def status(keys: KeyStore) -> EngineStatus:
    source = keys.source()
    if source == "absent":
        return {"engine": "scripted", "model": "scripted", "key": source, "simulated": True}
    return {"engine": "muse", "model": model_name(), "key": source, "simulated": False}
