"""The ready-made chores a twin may run, as data: `presets/<id>.json` (ADR 0005's chores are data too).

Each file is `{order, id, tool, name, does, kind, suggest, later?}`. The catalogue grows with the
tools: a preset whose tool this app cannot reach, or whose account is not connected, is listed as
`coming` and cannot be picked. A resolved mission runs the picked outcome presets (`missions`).
"""

from __future__ import annotations

import json
import typing
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from athena.contracts import ChannelKind, ChoreKind, ChorePreset

PRESETS_DIR = Path(__file__).resolve().parent / "presets"
INBOX = "task-inbox"  # the preset that reads a Notion page for new missions (`twins.inbox`)
_KINDS = frozenset(typing.get_args(ChoreKind))
_TOOLS = frozenset(typing.get_args(ChannelKind))


@dataclass(frozen=True)
class Preset:
    id: str
    tool: str
    name: str
    does: str
    kind: ChoreKind
    suggest: bool
    later: bool


@cache
def presets() -> tuple[Preset, ...]:
    """Every preset, in its `order`. A file that does not fit is a bug in the app, so it raises."""
    found: list[tuple[int, Preset]] = []
    for path in sorted(PRESETS_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("id") != path.stem or raw.get("kind") not in _KINDS:
            raise ValueError(
                f"{path.name}: the id must be the file's name and the kind one of {sorted(_KINDS)}"
            )
        preset = Preset(
            id=raw["id"],
            tool=str(raw["tool"]),
            name=str(raw["name"]),
            does=str(raw["does"]),
            kind=raw["kind"],
            suggest=raw.get("suggest") is True,
            later=raw.get("later") is True,
        )
        found.append((int(raw["order"]), preset))
    return tuple(p for _, p in sorted(found, key=lambda x: x[0]))


def find(preset_id: str) -> Preset | None:
    return next((p for p in presets() if p.id == preset_id), None)


def reachable(preset: Preset, connected: set[str]) -> bool:
    """Whether the preset's tool is one this app reaches and its account is connected."""
    return preset.tool in _TOOLS and preset.tool in connected


def listed(picked: set[str], connected: set[str], inbox_page: str = "") -> list[ChorePreset]:
    out: list[ChorePreset] = []
    for p in presets():
        item: ChorePreset = {
            "id": p.id,
            "tool": p.tool,
            "name": p.name,
            "does": p.does,
            "kind": p.kind,
            "suggest": p.suggest,
            "picked": p.id in picked,
        }
        if p.later:
            item["later"] = True
        if not reachable(p, connected):
            item["coming"] = True
        if p.id == INBOX and inbox_page:
            item["page"] = inbox_page
        out.append(item)
    return out
