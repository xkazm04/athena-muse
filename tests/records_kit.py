"""Shared bodies and set-up for the records tests (business Phase 1)."""

from __future__ import annotations

import typing
from pathlib import Path
from typing import Any

from athena.app import Daemon
from athena.contracts import RecordKind

ALL: list[RecordKind] = list(typing.get_args(RecordKind))
CREATOR = "https://youtube.example/@lumen"
TRACK = "https://youtube.example/watch?v=1"
WHEN = "2026-11-01T12:00:00Z"


def project(d: Daemon, kinds: list[RecordKind] | None = None) -> str:
    space: str = d.spaces.create({"name": "Music channel"})["id"]
    d.records.set_kinds(space, {"kinds": ALL if kinds is None else kinds})
    return space


def creator(name: str = "Lumen", url: str = CREATOR) -> dict[str, Any]:
    return {"name": name, "channel_url": url, "followed": True}


def track(url: str = TRACK, **extra: Any) -> dict[str, Any]:
    return {"url": url, "title": "Night Ferry", "creator_key": CREATOR, "found_at": WHEN, **extra}


def stat(value: float, at: str = WHEN, metric: str = "views") -> dict[str, Any]:
    return {"metric": metric, "value": value, "measured_at": at}


def file_row(d: Daemon, space: str, tmp: Path, data: bytes = b"RIFF tone") -> str:
    source = tmp / "tone.wav"
    source.write_bytes(data)
    file_id: str = d.files.ingest(space, source, "tone.wav", "https://youtube.example")["id"]
    return file_id


def renderable(d: Daemon, space: str, tmp: Path) -> str:
    """A track that may render: kept, agreed on the pro plan in a kept thread, with its file. Answers
    its key."""
    file_id = file_row(d, space, tmp)
    d.records.put(space, "creator", creator(), "athena")
    found = d.records.put(space, "track", track(file_id=file_id), "athena")
    d.records.verdict(found["id"], {"verdict": "keep"})
    d.records.put(
        space,
        "thread",
        {"key": "offer", "creator_key": CREATOR, "channel": "mail_web", "last_at": WHEN},
        "person",
    )
    d.records.put(
        space,
        "agreement",
        {"creator_key": CREATOR, "state": "agreed", "thread_key": "offer", "plan": "pro"},
        "person",
    )
    return found["key"]
