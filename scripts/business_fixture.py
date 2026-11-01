"""Seed a simulated music channel project through the daemon's own code (business Phase 1).

Opens a daemon on a data folder (no HTTP) and keeps, through `Records`: every record kind; 4
creators; 9 tracks (3 not judged yet, the queue; 3 kept, 2 passed, 1 later); 3 threads; 3 agreements
(one agreed on the pro plan with a thread, one proposed, one declined); one file record for an
agreed, kept track, pointing at a real files row (a short generated tone, kept with `Files.ingest`);
and 14 days of `views` and `subscribers` stats. Every name is invented and labelled simulated.

The project is found again by its name, and a put of an unchanged body appends nothing, so running
it again on the same folder (on the same day) changes nothing.

    uv run python scripts/business_fixture.py <data_dir>                  # prints {"space_id": ...}
    uv run python scripts/business_fixture.py <data_dir> --view out.json  # and the report's view
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import typing
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from athena.app import Daemon
from athena.contracts import RecordKind

NAME = "Music channel (simulated)"
BRIEF = (
    "Simulated: a music channel that finds songs by small creators, asks for a licence, and makes "
    "videos of the ones it keeps. Every creator, song and number here is invented."
)
SITE = "https://youtube.example"  # a made-up address: nothing here is a real channel
GENRES = ("lo-fi", "synthwave", "ambient", "chillhop")
#: Business addresses the simulated mailbox (athena.browser.fixture) sends from.
EMAILS = {"lumen-tide-sim": "lumen.tide@creators.example", "paper-orbit-sim": "paper.orbit@creators.example"}

CREATORS = (
    ("Lumen Tide (simulated)", "lumen-tide-sim"),
    ("Paper Orbit (simulated)", "paper-orbit-sim"),
    ("Velvet Static (simulated)", "velvet-static-sim"),
    ("Moss Arcade (simulated)", "moss-arcade-sim"),
)
#: (title, creator index, verdict or None, genre or None)
TRACKS = (
    ("Night Ferry (simulated)", 0, "keep", "lo-fi"),
    ("Glass Harbour (simulated)", 0, "keep", "ambient"),
    ("Neon Pantry (simulated)", 1, "keep", "synthwave"),
    ("Slow Comet (simulated)", 1, "pass", "chillhop"),
    ("Tin Lanterns (simulated)", 2, "pass", "synthwave"),
    ("Rain Index (simulated)", 2, "later", "ambient"),
    ("Low Tide Radio (simulated)", 3, None, None),
    ("Paper Moons (simulated)", 3, None, None),
    ("Quiet Arcade (simulated)", 1, None, None),
)


def channel_url(handle: str) -> str:
    return f"{SITE}/@{handle}"


def track_url(n: int) -> str:
    return f"{SITE}/watch?v=sim{n:04d}"


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds").replace("+00:00", "Z")


def _tone(path: Path) -> None:
    """Half a second of a quiet 440 Hz tone: the same bytes every run, so it is kept once."""
    rate = 8000
    frames = b"".join(
        struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(rate // 2)
    )
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


def _project(daemon: Daemon) -> str:
    for space in daemon.spaces.list():
        if space["name"] == NAME:
            return space["id"]
    return daemon.spaces.create({"name": NAME, "brief": BRIEF, "apps": [SITE]})["id"]


def seed(daemon: Daemon, today: datetime | None = None) -> str:
    """Seeds the project through Records and Files; answers its space id."""
    day = (today or datetime.now(UTC)).replace(hour=12, minute=0, second=0, microsecond=0)
    space = _project(daemon)
    records = daemon.records
    records.set_kinds(space, {"kinds": list(typing.get_args(RecordKind))})

    for name, handle in CREATORS:
        creator: dict[str, Any] = {"name": name, "channel_url": channel_url(handle), "followed": True}
        if handle in EMAILS:  # the simulated mailbox's senders (browser.fixture), for the inbox routine
            creator["emails"] = [EMAILS[handle]]
        records.put(space, "creator", creator, "athena")

    tracks: dict[int, dict[str, Any]] = {}
    for n, (title, who, verdict, genre) in enumerate(TRACKS):
        again = records.latest(space, "track", track_url(n))
        if again:  # found before: finding it again changes nothing
            tracks[n] = again[0]
            continue
        found = records.put(
            space,
            "track",
            {
                "url": track_url(n),
                "title": title,
                "creator_key": channel_url(CREATORS[who][1]),
                "found_at": _iso(day - timedelta(days=9 - n)),
            },
            "athena",
        )
        tracks[n] = found
        if verdict is not None:
            body: dict[str, Any] = {"verdict": verdict}
            if genre is not None:
                body["genre"] = genre
            records.verdict(found["id"], body)  # type: ignore[arg-type]

    threads = (
        ("lumen-offer", 0, "mail_web", "Licence for Night Ferry (simulated)"),
        ("paper-bio", 1, "bio", "Asked about Neon Pantry (simulated)"),
        ("velvet-comment", 2, "comment", "Comment under Tin Lanterns (simulated)"),
    )
    for n, (key, who, channel, subject) in enumerate(threads):
        records.put(
            space,
            "thread",
            {
                "key": key,
                "creator_key": channel_url(CREATORS[who][1]),
                "channel": channel,
                "last_at": _iso(day - timedelta(days=3 - n)),
                "subject": subject,
                "snippet": "Simulated message: happy to talk about a licence.",
            },
            "person",
        )

    agreements = (
        (0, "agreed", "lumen-offer", "pro", "Simulated terms: credit in every video, revenue split 50/50."),
        (1, "proposed", "paper-bio", None, None),
        (2, "declined", "velvet-comment", "free", None),
    )
    for who, state, thread_key, plan, terms in agreements:
        body = {"creator_key": channel_url(CREATORS[who][1]), "state": state, "thread_key": thread_key}
        if plan is not None:
            body["plan"] = plan
        if terms is not None:
            body["terms"] = terms
        records.put(space, "agreement", body, "person")

    # The agreed creator's first kept track gets its audio: a real files row, then a file record.
    tone = daemon.files.incoming(space) / "night-ferry-simulated.wav"
    _tone(tone)
    item = daemon.files.ingest(space, tone, "night-ferry-simulated.wav", SITE)
    kept = tracks[0]
    records.put(space, "file", {"file_id": item["id"], "track_key": kept["key"]}, "person")
    latest = records.latest(space, "track", kept["key"])[0]
    records.put(space, "track", {**latest["body"], "file_id": item["id"]}, "person")

    for d in range(14):
        when = _iso(day - timedelta(days=13 - d))
        records.put(
            space,
            "stat",
            {"metric": "views", "value": 120 + 37 * d + (d % 3) * 11, "measured_at": when},
            "routine",
        )
        records.put(
            space, "stat", {"metric": "subscribers", "value": 40 + 2 * d, "measured_at": when}, "routine"
        )
    return space


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("--view", type=Path, help="after seeding, write the report's view (WP1.2) here")
    args = parser.parse_args(argv)
    daemon = Daemon.open(args.data_dir)
    try:
        space = seed(daemon)
        if args.view is not None:
            from athena.report.compose import view

            args.view.write_text(
                json.dumps(view(daemon, space), indent=2, ensure_ascii=False), encoding="utf-8"
            )
    finally:
        daemon.store.close()
    print(json.dumps({"space_id": space}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
