"""The role backends: recorded fixtures, and the stubs for Meta's segmenter and transcriber.

A fixture is `senses/fixtures/<media_id>.json`, every key optional: `segments`, `transcript`,
`reads`. A fixture call costs nothing and takes no time, so a fixture build is byte-identical run
to run; its row says `fixture` so no one mistakes it for a model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from athena.engine import EngineError
from athena.senses.contract import (
    READERS,
    SEGMENTERS,
    TRANSCRIBERS,
    Box,
    Media,
    Read,
    Reader,
    ReadField,
    Segment,
    Segmenter,
    SpokenTurn,
    Transcriber,
    Transcript,
    Usage,
)

FIXTURE = "fixture"


def _box(raw: Any) -> Box | None:
    if isinstance(raw, list | tuple) and len(raw) == 4:
        return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
    return None


class Fixtures:
    """The recorded answers of one chore, loaded once per media item."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self._cache: dict[str, dict[str, Any]] = {}

    def get(self, media_id: str) -> dict[str, Any]:
        if media_id not in self._cache:
            path = self.folder / f"{media_id}.json"
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            self._cache[media_id] = data if isinstance(data, dict) else {}
        return self._cache[media_id]


class FixtureSegmenter:
    name = FIXTURE

    def __init__(self, fixtures: Fixtures) -> None:
        self.fixtures = fixtures

    def segment(self, item: Media, prompt: str) -> tuple[list[Segment], Usage]:
        """Every recorded segment whose label contains the prompt (case-insensitive; empty = all)."""
        raw = self.fixtures.get(item.id).get("segments") or []
        want = prompt.strip().casefold()
        out: list[Segment] = []
        for s in raw:
            label = str(s.get("label") or "")
            box = _box(s.get("box"))
            if box is None or (want and want not in label.casefold()):
                continue
            out.append(
                Segment(
                    label,
                    float(s.get("score") or 0.0),
                    box,
                    int(s.get("frame") or 0),
                    str(s.get("track_id") or ""),
                )
            )
        frames = len({int(s.get("frame") or 0) for s in raw})
        return out, Usage(FIXTURE, FIXTURE, frames, "frame", cost_usd=0.0)


class FixtureTranscriber:
    name = FIXTURE

    def __init__(self, fixtures: Fixtures) -> None:
        self.fixtures = fixtures

    def transcribe(self, item: Media) -> tuple[Transcript, Usage]:
        raw = self.fixtures.get(item.id).get("transcript") or {}
        turns = tuple(
            SpokenTurn(str(t["speaker"]), float(t["start_s"]), float(t["end_s"]), str(t["text"]))
            for t in raw.get("turns") or []
        )
        seconds = max((t.end_s for t in turns), default=0.0)
        return Transcript(str(raw.get("language") or ""), turns), Usage(
            FIXTURE, FIXTURE, seconds, "second", cost_usd=0.0
        )


class FixtureReader:
    name = FIXTURE

    def __init__(self, fixtures: Fixtures) -> None:
        self.fixtures = fixtures

    def read(
        self, item: Media, fields: list[str], attempt: int, *, image: Path | None = None, hint: str = ""
    ) -> tuple[Read, Usage]:
        """`reads[attempt]` (else reads[0]) restricted to the fields asked; a field it lacks is unreadable."""
        reads = self.fixtures.get(item.id).get("reads") or []
        chosen: dict[str, Any] = next(
            (r for r in reads if r.get("attempt") == attempt), reads[0] if reads else {}
        )
        by_name = {str(f["name"]): f for f in chosen.get("fields") or []}
        marked = {str(n) for n in chosen.get("unreadable") or []}
        got: list[ReadField] = []
        unreadable: list[str] = []
        for name in fields:
            f = by_name.get(name)
            if f is None or name in marked or f.get("value") in (None, ""):
                unreadable.append(name)
                continue
            frame = f.get("frame")
            conf = f.get("confidence")
            got.append(
                ReadField(
                    name,
                    str(f["value"]),
                    float(conf) if conf is not None else None,
                    int(frame) if frame is not None else None,
                    _box(f.get("box")),
                )
            )
        return Read(attempt, tuple(got), tuple(unreadable)), Usage(FIXTURE, FIXTURE, 1, "read", cost_usd=0.0)


class MetaSegmenter:
    """SAM 3.1 over Meta's API. Not built: SAM is API-only and no key has been measured against it."""

    name = "meta"

    def segment(self, item: Media, prompt: str) -> tuple[list[Segment], Usage]:
        raise EngineError("not measured yet")


class MetaTranscriber:
    """Meta's voice transcription. Not built: it is not available on Windows today."""

    name = "meta"

    def transcribe(self, item: Media) -> tuple[Transcript, Usage]:
        raise EngineError("not measured yet")


def make_segmenter(name: str, fixtures: Fixtures) -> Segmenter:
    if name not in SEGMENTERS:
        raise ValueError(f"No segmenter called {name!r}; choose one of {', '.join(SEGMENTERS)}")
    return MetaSegmenter() if name == "meta" else FixtureSegmenter(fixtures)


def make_transcriber(name: str, fixtures: Fixtures) -> Transcriber:
    if name not in TRANSCRIBERS:
        raise ValueError(f"No transcriber called {name!r}; choose one of {', '.join(TRANSCRIBERS)}")
    return MetaTranscriber() if name == "meta" else FixtureTranscriber(fixtures)


def make_reader(name: str, fixtures: Fixtures) -> Reader:
    if name not in READERS:
        raise ValueError(f"No reader called {name!r}; choose one of {', '.join(READERS)}")
    fallback = FixtureReader(fixtures)
    if name == "muse_code":
        from athena.senses.readers import MuseCodeReader

        return MuseCodeReader(fallback)
    if name == "meta":
        from athena.senses.readers import MetaReader

        return MetaReader(fallback)
    return fallback
