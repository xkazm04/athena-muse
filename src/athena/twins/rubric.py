"""The twin's rubric (ADR 0010): its places, what each requires, readiness, and its pieces on the wire.

A twin's parts are sketch nodes on the drafts machinery: a node's `slot` is the piece's place and its
`kind` says what the piece is, so the shaping rules (coverage from the sketch, ink proven by a quote,
one question at a time) are the chore's, unchanged. On the wire a node is a `Piece`: `slot` reads
`place`, the kind is not shown, and a piece learned from sent mail keeps `evidence` (the sample ids).
"""

from __future__ import annotations

import math
from typing import Any, cast

from athena.contracts import Piece, PlaceCoverage, Sketch, SketchNode
from athena.drafts.rubric import Rubric

PLACES = ("who", "channels", "voice", "knowledge", "chores", "never", "autonomy", "memory", "mission")

#: What a piece is. `name` and `purpose` say who it is; a channel piece is the account's kind; every
#: other piece is a `line`.
KINDS = ("line", "name", "purpose", "gmail", "notion")

TWIN_RUBRIC = Rubric(
    places=PLACES,
    # As the prototype's `places` (docs/concepts/twin-module/prototypes/shared/src/twin.src.mjs).
    required={
        "who": 1,
        "channels": 1,
        "voice": 1,
        "knowledge": 0.5,
        "chores": 0.5,
        "never": 1,
        "autonomy": 1,
        "memory": 0,
        "mission": 0,
    },
    meaning={
        "who": "who it speaks as: its name, what it is for and how it signs",
        "channels": "where it speaks: Gmail, Notion",
        "voice": "how it sounds, learned only from mail the person wrote",
        "knowledge": "what it knows: the Notion pages it may answer from",
        "chores": "what it does there: the ready-made chores it may run",
        "never": "what it must never do",
        "autonomy": "what it may send alone, per channel",
        "memory": "what it remembers about the person",
        "mission": "its first mission",
    },
    kinds=KINDS,
    allowed={
        "who": ("line", "name", "purpose"),
        "channels": ("gmail", "notion"),
        **{p: ("line",) for p in ("voice", "knowledge", "chores", "never", "autonomy", "memory", "mission")},
    },
)

#: The places readiness is the mean of: those setup requires.
CORE = tuple(p for p in PLACES if TWIN_RUBRIC.required[p] > 0)


def coverage(sketch: Sketch) -> PlaceCoverage:
    """Per place: 1 = a confirmed piece, 0.5 = only her proposals, 0 = empty. A twin skips nothing."""
    return cast("PlaceCoverage", TWIN_RUBRIC.coverage(sketch))


def ready(cov: PlaceCoverage) -> bool:
    """Every place at what it requires or above: the dress rehearsal may start."""
    return TWIN_RUBRIC.agreed(cov)


def readiness(cov: PlaceCoverage) -> int:
    """The mean coverage over the places setup requires, as a whole percent (half rounds up, as the
    prototype's `Math.round`)."""
    values = cast("dict[str, Any]", cov)
    total = sum(float(values[p]) for p in CORE)
    return math.floor(100 * total / len(CORE) + 0.5)


def evidence(node: SketchNode) -> list[str]:
    """The sample ids a piece was learned from; kept on its node beside the sketch's own fields."""
    return list(cast("dict[str, Any]", node).get("evidence", []))


def piece(node: SketchNode) -> Piece:
    """A node as the wire's `Piece`."""
    out: Piece = {
        "id": node["id"],
        "place": cast("Any", node["slot"]),
        "label": node["label"],
        "origin": node["origin"],
        "confirmed": node["confirmed"],
    }
    if "detail" in node:
        out["detail"] = node["detail"]
    if "quote" in node:
        out["quote"] = node["quote"]
    found = evidence(node)
    if found:
        out["evidence"] = found
    return out
