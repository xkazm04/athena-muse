"""Build a chore's senses into `sensed.json`, and prove them into `proofs.json`.

`build` runs every sense the media index names, each over the whole index and filtering to its own
items, then merges their tables: two senses writing one table, or a sensed table shadowing a world
table, is refused. Nothing in `sensed.json` reads the clock, so a fixture build is byte-identical
run to run. `prove` builds in memory and measures each sense against `senses/key.json`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from athena.contracts import ProofRow, SenseName
from athena.senses.backends import Fixtures, make_reader, make_segmenter, make_transcriber
from athena.senses.call import CallSense
from athena.senses.circle import CircleSense
from athena.senses.contract import ROLES, CallRow, Media, Sense, SenseContext, SenseOutput
from athena.senses.paper import PaperSense
from athena.senses.walk import WalkSense

PLAYBOOKS_ENV = "ATHENA_PLAYBOOKS"
ORDER: tuple[SenseName, ...] = ("paper", "call", "walk", "circle")
SENSES: dict[SenseName, Sense] = {
    "paper": PaperSense(),
    "call": CallSense(),
    "walk": WalkSense(),
    "circle": CircleSense(),
}


class SenseError(ValueError):
    """A chore whose senses cannot be built, in plain words."""


@dataclass(frozen=True)
class Built:
    ctx: SenseContext
    outputs: tuple[SenseOutput, ...]
    tables: dict[str, list[dict[str, Any]]]  # the sensed tables only
    asked: tuple[str, ...]


def library_dir() -> Path:
    env = os.environ.get(PLAYBOOKS_ENV, "").strip()
    return Path(env) if env else Path(__file__).resolve().parents[3] / "playbooks"


def chore_dir(chore: str) -> Path:
    """A chore id under the library, or a path to a chore folder."""
    as_path = Path(chore)
    root = as_path if (as_path / "senses").is_dir() else library_dir() / chore
    if not (root / "senses" / "media.json").is_file():
        raise SenseError(f"No chore with a media index at {chore!r}")
    return root


def _json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SenseError(f"{path.name} is not a JSON object")
    return data


def load_media(senses_dir: Path) -> tuple[tuple[Media, ...], dict[str, str]]:
    """The media index, and the backends it asks for by default."""
    data = _json(senses_dir / "media.json")
    items = []
    for raw in data.get("media") or []:
        if raw.get("sense") not in ORDER:
            raise SenseError(f"Media item {raw.get('id')!r} names no known sense")
        items.append(
            Media(
                id=str(raw["id"]),
                kind=str(raw["kind"]),
                sense=raw["sense"],
                path=str(raw.get("path") or ""),
                source=str(raw.get("source") or ""),
                params=dict(raw.get("params") or {}),
                personal=bool(raw.get("personal")),
            )
        )
    return tuple(items), {str(k): str(v) for k, v in (data.get("backends") or {}).items()}


def load_world(root: Path) -> dict[str, list[dict[str, Any]]]:
    path = root / "world.json"
    if not path.is_file():
        return {}
    return {str(k): list(v) for k, v in (_json(path).get("tables") or {}).items()}


def context(root: Path, chosen: dict[str, str | None] | None = None) -> SenseContext:
    senses_dir = root / "senses"
    media, defaults = load_media(senses_dir)
    want = {role: (chosen or {}).get(role) or defaults.get(role) or "fixture" for role in ROLES}
    fixtures = Fixtures(senses_dir / "fixtures")
    return SenseContext(
        playbook=root.name,
        senses_dir=senses_dir,
        media=media,
        tables=load_world(root),
        segmenter=make_segmenter(want["segmenter"], fixtures),
        transcriber=make_transcriber(want["transcriber"], fixtures),
        reader=make_reader(want["reader"], fixtures),
    )


def named_senses(media: tuple[Media, ...]) -> list[SenseName]:
    present = {m.sense for m in media}
    return [s for s in ORDER if s in present]


def build(ctx: SenseContext) -> Built:
    world = set(ctx.tables)
    outputs: list[SenseOutput] = []
    tables: dict[str, list[dict[str, Any]]] = {}
    owner: dict[str, str] = {}
    asked: list[str] = []
    for name in named_senses(ctx.media):
        out = SENSES[name].build(ctx)
        for table, rows in out.tables.items():
            if table in world:
                raise SenseError(f"The {name} sense would shadow the world table {table!r}")
            if table in owner:
                raise SenseError(f"The {owner[table]} and {name} senses both write the table {table!r}")
            owner[table] = name
            tables[table] = rows
        outputs.append(out)
        asked += out.asked
    return Built(ctx, tuple(outputs), tables, tuple(asked))


def backends(ctx: SenseContext) -> dict[str, str]:
    """The backend each role really ran on: a fallback shows, a mix is named as one."""
    chosen = {"segmenter": ctx.segmenter.name, "transcriber": ctx.transcriber.name, "reader": ctx.reader.name}
    out: dict[str, str] = {}
    for role in ROLES:
        used = sorted({c["backend"] for c in ctx.calls if c["role"] == role})
        out[role] = "+".join(used) if used else chosen[role]
    return out


def cost(calls: list[CallRow]) -> tuple[float, int]:
    priced = [c["cost_usd"] for c in calls if "cost_usd" in c]
    return round(sum(priced), 6), len(calls) - len(priced)


def sensed(b: Built) -> dict[str, Any]:
    total, unpriced = cost(b.ctx.calls)
    return {
        "playbook": b.ctx.playbook,
        "backends": backends(b.ctx),
        "cost_usd": total,
        "unpriced_calls": unpriced,
        "asked": list(b.asked),
        "calls": list(b.ctx.calls),
        "tables": b.tables,
    }


def prove(b: Built) -> dict[str, Any]:
    key_path = b.ctx.senses_dir / "key.json"
    key = _json(key_path) if key_path.is_file() else {}
    merged = SenseContext(
        playbook=b.ctx.playbook,
        senses_dir=b.ctx.senses_dir,
        media=b.ctx.media,
        tables={**b.ctx.tables, **b.tables},
        segmenter=b.ctx.segmenter,
        transcriber=b.ctx.transcriber,
        reader=b.ctx.reader,
        calls=b.ctx.calls,
    )
    rows: list[ProofRow] = []
    for out in b.outputs:
        rows += SENSES[out.sense].prove(merged, out, key)
    return {
        "playbook": b.ctx.playbook,
        "backends": backends(b.ctx),
        "passed": bool(rows) and all(r["passed"] for r in rows),
        "proofs": rows,
    }


def dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(data), encoding="utf-8", newline="\n")
