"""The layout a project gets before Athena arranges it: deterministic per kind set, with stable ids, and
only kinds the project keeps. It passes the same validation door as a composed spec."""

from __future__ import annotations

from typing import Any

from athena.contracts import VOCAB, Binding, Block, RecordKind, ReportSpec

#: The funnel from an offer to a release, each stage a count over one kind.
_PIPELINE: tuple[tuple[str, RecordKind, dict[str, str | bool | None]], ...] = (
    ("Proposed", "agreement", {"state": "proposed"}),
    ("Agreed", "agreement", {"state": "agreed"}),
    ("Rendered", "render", {"state": "rendered"}),
    ("Released", "release", {}),
)

#: A kept kind no block below shows gets a count, so nothing a project keeps is invisible.
_COUNT_TITLES: dict[RecordKind, str] = {
    "creator": "Creators",
    "track": "Tracks",
    "thread": "Conversations",
    "agreement": "Agreements",
    "file": "Files",
    "render": "Renders",
    "release": "Releases",
    "stat": "Readings",
}


def default_spec(title: str, kinds: list[RecordKind]) -> ReportSpec:
    keep = set(kinds)
    blocks: list[Block] = []
    shown: set[RecordKind] = set()

    def add(block: Block, *used: RecordKind) -> None:
        blocks.append(block)
        shown.update(used)

    if "track" in keep:
        add(
            {
                "id": "d-queue",
                "kind": "queue",
                "title": "Tracks waiting for you",
                "span": 8,
                "binding": {"kind": "track", "filter": {"verdict": None}},
                "config": {},
            },
            "track",
        )
    if "creator" in keep:
        add(
            {
                "id": "d-creators",
                "kind": "stat",
                "title": "Creators followed",
                "span": 4,
                "binding": {"kind": "creator", "filter": {"followed": True}, "agg": "count"},
                "config": {},
            },
            "creator",
        )
    stages: list[dict[str, Any]] = []
    for label, kind, f in _PIPELINE:
        if kind in keep:
            binding: Binding = {"kind": kind, "agg": "count"}
            if f:
                binding["filter"] = dict(f)
            stages.append({"label": label, "binding": binding})
    if len(stages) >= 2:
        add(
            {
                "id": "d-pipeline",
                "kind": "pipeline",
                "title": "From offer to release",
                "span": 12,
                "config": {"stages": stages},
            },
            *(kind for _, kind, _ in _PIPELINE if kind in keep),
        )
    if "stat" in keep:
        add(
            {
                "id": "d-views",
                "kind": "trend",
                "title": "Views",
                "span": 6,
                "binding": {"kind": "stat", "filter": {"metric": "views"}, "agg": "series", "field": "value"},
                "config": {"unit": "views"},
            },
            "stat",
        )
    blocks.append(
        {"id": "d-cards", "kind": "cards", "title": "Waiting for your signature", "span": 6, "config": {}}
    )
    if "thread" in keep:
        add(
            {
                "id": "d-threads",
                "kind": "thread",
                "title": "Latest conversations",
                "span": 6,
                "binding": {"kind": "thread"},
                "config": {"limit": 5},
            },
            "thread",
        )
    if "track" in keep:
        add(
            {
                "id": "d-tracks",
                "kind": "list",
                "title": "Latest tracks",
                "span": 12,
                "binding": {"kind": "track"},
                "config": {"fields": ["title", "genre", "verdict"], "limit": 5},
            },
            "track",
        )
    for kind in _COUNT_TITLES:  # catalog order, so one kind set always gets one layout
        if kind in keep and kind not in shown:
            add(
                {
                    "id": f"d-{kind}",
                    "kind": "stat",
                    "title": _COUNT_TITLES[kind],
                    "span": 3,
                    "binding": {"kind": kind, "agg": "count"},
                    "config": {},
                },
                kind,
            )
    return {"v": 1, "vocab": VOCAB, "title": title, "blocks": blocks}
