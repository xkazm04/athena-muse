"""The senses' contract: three roles, their backends, and the shapes a sense build passes around.

A sense turns recorded media into tables whose every row cites its media item (ADR 0005). It does
so through three roles, each a Protocol with backends chosen per role:

- Segmenter (`fixture` | `meta`): finds the objects a prompt names in a video or photo.
- Transcriber (`fixture` | `meta`): turns a recording into speaker turns.
- Reader (`fixture` | `muse_code` | `meta`): reads named fields off one image.

Wire conventions: a box is `[x0, y0, x1, y1]` normalised 0..1 from the top-left; a frame is
0-based; a second is a float; an absent value is the key omitted (never 0). Every role call is one
`CallRow` in `sensed.json`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, NotRequired, Protocol, TypedDict

from athena.contracts import ProofRow, SenseName

Role = Literal["segmenter", "transcriber", "reader"]
ROLES: tuple[Role, ...] = ("segmenter", "transcriber", "reader")
SEGMENTERS = ("fixture", "meta")
TRANSCRIBERS = ("fixture", "meta")
READERS = ("fixture", "muse_code", "meta")
#: The backends that run on one of Meta's models (a proof on them can make a chore `proven`).
META_BACKENDS = ("meta", "muse_code")

Box = tuple[float, float, float, float]


class CallRow(TypedDict):
    """One role call, as `sensed.json` lists it."""

    sense: SenseName
    role: Role
    backend: str
    model: str
    mode: Literal["standard"]
    media_id: str
    units: float
    unit: str  # frame | second | read | token
    cost_estimated: bool
    latency_ms: int
    cost_usd: NotRequired[float]  # omitted = unpriced


@dataclass(frozen=True)
class Media:
    """One item of `senses/media.json`."""

    id: str
    kind: str  # paper | video | audio | photo
    sense: SenseName
    path: str = ""
    source: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    personal: bool = False


@dataclass(frozen=True)
class Usage:
    """What one role call cost: the backend that really answered it (a fallback says so)."""

    backend: str
    model: str
    units: float
    unit: str
    latency_ms: int = 0
    cost_usd: float | None = None  # None = unpriced
    cost_estimated: bool = False


@dataclass(frozen=True)
class Segment:
    label: str
    score: float
    box: Box
    frame: int
    track_id: str = ""


@dataclass(frozen=True)
class SpokenTurn:
    speaker: str  # the diarised label (A, B...), not yet a role
    start_s: float
    end_s: float
    text: str


@dataclass(frozen=True)
class Transcript:
    language: str
    turns: tuple[SpokenTurn, ...]


@dataclass(frozen=True)
class ReadField:
    name: str
    value: str
    confidence: float | None = None
    frame: int | None = None
    box: Box | None = None


@dataclass(frozen=True)
class Read:
    """One attempt at reading named fields off one image."""

    attempt: int
    fields: tuple[ReadField, ...]
    unreadable: tuple[str, ...] = ()


class Segmenter(Protocol):
    name: str

    def segment(self, item: Media, prompt: str) -> tuple[list[Segment], Usage]: ...


class Transcriber(Protocol):
    name: str

    def transcribe(self, item: Media) -> tuple[Transcript, Usage]: ...


class Reader(Protocol):
    name: str

    def read(
        self, item: Media, fields: list[str], attempt: int, *, image: Path | None = None, hint: str = ""
    ) -> tuple[Read, Usage]: ...


@dataclass
class SenseContext:
    """Everything a sense build sees: the chore's media, its world, and the chosen backends.

    `tables` is the world's tables while building; for `prove` it is the world's tables merged with
    every sensed table, so a proof can follow a cite across senses.
    """

    playbook: str
    senses_dir: Path
    media: tuple[Media, ...]
    tables: dict[str, list[dict[str, Any]]]
    segmenter: Segmenter
    transcriber: Transcriber
    reader: Reader
    calls: list[CallRow] = field(default_factory=list)

    def items(self, sense: SenseName, kind: str | None = None) -> list[Media]:
        return [m for m in self.media if m.sense == sense and (kind is None or m.kind == kind)]

    def record(self, sense: SenseName, role: Role, media_id: str, usage: Usage) -> None:
        row: CallRow = {
            "sense": sense,
            "role": role,
            "backend": usage.backend,
            "model": usage.model,
            "mode": "standard",
            "media_id": media_id,
            "units": usage.units,
            "unit": usage.unit,
            "cost_estimated": usage.cost_estimated,
            "latency_ms": usage.latency_ms,
        }
        if usage.cost_usd is not None:
            row["cost_usd"] = usage.cost_usd
        self.calls.append(row)

    def render_png(self, item: Media) -> Path | None:
        """The rendered PNG of a paper sheet, or a photo's own image, when it exists on disk."""
        if item.kind == "paper":
            png = self.senses_dir / "render" / f"{item.id}.png"
            return png if png.is_file() else None
        if item.kind == "photo" and item.path:
            photo = self.senses_dir / item.path
            return photo if photo.is_file() else None
        return None


@dataclass(frozen=True)
class SenseOutput:
    """What one sense built: its tables, the values it would not guess, and its calls."""

    sense: SenseName
    tables: dict[str, list[dict[str, Any]]]
    asked: tuple[str, ...] = ()


class Sense(Protocol):
    name: SenseName

    def build(self, ctx: SenseContext) -> SenseOutput: ...

    def prove(self, ctx: SenseContext, out: SenseOutput, key: dict[str, Any]) -> list[ProofRow]: ...


def proof(
    sense: SenseName,
    pid: str,
    question: str,
    bar: float,
    op: Literal[">=", "<="],
    n: int,
    measured: float | None,
    note: str,
) -> ProofRow:
    """One proof row. No measurement (n == 0) fails: a proof with nothing counted proves nothing."""
    value = round(measured, 4) if measured is not None else None
    passed = value is not None and n > 0 and (value >= bar if op == ">=" else value <= bar)
    row: ProofRow = {
        "sense": sense,
        "id": pid,
        "question": question,
        "bar": bar,
        "op": op,
        "passed": passed,
        "n": n,
    }
    if value is not None:
        row["measured"] = value
    if note:
        row["note"] = note
    return row
