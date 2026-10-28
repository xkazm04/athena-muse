"""Applying sketch ops. Places never move: an op adds, changes, removes or links, never reorders."""

from __future__ import annotations

import copy
import re
import typing
from typing import Any, cast

from athena.contracts import (
    DETAIL_MAX,
    LABEL_MAX,
    SKETCH_NODES_MAX,
    Sketch,
    SketchEdge,
    SketchKind,
    SketchNode,
    SketchOp,
    Slot,
)

KINDS: frozenset[str] = frozenset(typing.get_args(SketchKind))
SLOT_NAMES: frozenset[str] = frozenset(typing.get_args(Slot))
NODE_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")


class SketchError(ValueError):
    """An op that cannot apply (unknown id, duplicate id, dangling edge, a cap). Plain words."""


def empty() -> Sketch:
    return {"nodes": [], "edges": []}


def _label(raw: Any, field: str = "label") -> str:
    if not isinstance(raw, str):
        raise SketchError(f"the {field} must be text")
    text = " ".join(raw.split())
    if not 1 <= len(text) <= LABEL_MAX:
        raise SketchError(f"a {field} is 1 to {LABEL_MAX} characters; this one is {len(text)}")
    return text


def _detail(raw: Any) -> str:
    if not isinstance(raw, str):
        raise SketchError("the detail must be text")
    text = " ".join(raw.split())
    if len(text) > DETAIL_MAX:
        raise SketchError(f"a detail is at most {DETAIL_MAX} characters; this one is {len(text)}")
    return text


def _kind(raw: Any) -> SketchKind:
    if raw not in KINDS:
        raise SketchError(f"the kind must be one of {', '.join(sorted(KINDS))}")
    return cast("SketchKind", raw)


def _slot(raw: Any) -> Slot:
    if raw not in SLOT_NAMES:
        raise SketchError(f"the slot must be one of {', '.join(typing.get_args(Slot))}")
    return cast("Slot", raw)


def _index(sketch: Sketch, node_id: Any) -> int:
    for i, node in enumerate(sketch["nodes"]):
        if node["id"] == node_id:
            return i
    raise SketchError(f"there is no node {node_id!r} in the sketch")


def _edge(raw: Any) -> SketchEdge:
    if (
        not isinstance(raw, dict)
        or not isinstance(raw.get("from"), str)
        or not isinstance(raw.get("to"), str)
    ):
        raise SketchError("a link needs the ids of both ends")
    return {"from": raw["from"], "to": raw["to"]}


def _copy(e: SketchEdge) -> SketchEdge:
    return {"from": e["from"], "to": e["to"]}


def _add(sketch: Sketch, raw: dict[str, Any]) -> SketchOp:
    node_id = raw.get("id")
    if not isinstance(node_id, str) or not NODE_ID.fullmatch(node_id):
        raise SketchError("a new node needs an id of letters, digits, - or _ (at most 40)")
    if any(n["id"] == node_id for n in sketch["nodes"]):
        raise SketchError(f"there is already a node {node_id!r}")
    if len(sketch["nodes"]) >= SKETCH_NODES_MAX:
        raise SketchError(f"the sketch holds at most {SKETCH_NODES_MAX} nodes")
    node: SketchNode = {
        "id": node_id,
        "kind": _kind(raw.get("kind")),
        "slot": _slot(raw.get("slot")),
        "label": _label(raw.get("label")),
        "origin": "you" if raw.get("origin") == "you" else "athena",
        "confirmed": raw.get("confirmed") is True,
    }
    detail = _detail(raw["detail"]) if raw.get("detail") is not None else ""
    if detail:
        node["detail"] = detail
    sketch["nodes"].append(node)
    return {"op": "add", "node": copy.deepcopy(node)}


def _change(sketch: Sketch, raw: dict[str, Any]) -> SketchOp:
    node = sketch["nodes"][_index(sketch, raw.get("id"))]
    reworded = any(k in raw for k in ("label", "kind", "slot"))
    if reworded and node["origin"] == "you":
        raise SketchError("that node is in the person's own words; ask them before changing it")
    if reworded:
        node["confirmed"] = False  # the person agreed to the old words, not to these
    changed = False
    if "label" in raw:
        node["label"] = _label(raw["label"])
        changed = True
    if "kind" in raw:
        node["kind"] = _kind(raw["kind"])
        changed = True
    if "slot" in raw:
        node["slot"] = _slot(raw["slot"])
        changed = True
    if "detail" in raw:
        detail = _detail(raw["detail"])
        if detail:
            node["detail"] = detail
        else:
            node.pop("detail", None)
        changed = True
    if not changed:
        raise SketchError("a change needs a new label, detail, kind or slot")
    return {"op": "change", "node": copy.deepcopy(node)}


def _remove(sketch: Sketch, op: SketchOp) -> list[SketchOp]:
    if "node" in op:
        i = _index(sketch, op["node"].get("id"))
        node = sketch["nodes"][i]
        if node["origin"] == "you":
            raise SketchError("that node is in the person's own words; ask them before removing it")
        out: list[SketchOp] = []
        kept: list[SketchEdge] = []
        for e in sketch["edges"]:
            if node["id"] in (e["from"], e["to"]):
                out.append({"op": "remove", "edge": _copy(e)})
            else:
                kept.append(e)
        sketch["edges"] = kept
        del sketch["nodes"][i]
        out.append({"op": "remove", "node": copy.deepcopy(node)})
        return out
    if "edge" in op:
        edge = _edge(op["edge"])
        if edge not in sketch["edges"]:
            raise SketchError(f"there is no link from {edge['from']!r} to {edge['to']!r}")
        sketch["edges"].remove(edge)
        return [{"op": "remove", "edge": _copy(edge)}]
    raise SketchError("a remove needs a node id, or both ends of a link")


def _link(sketch: Sketch, op: SketchOp) -> SketchOp:
    edge = _edge(op.get("edge"))
    _index(sketch, edge["from"])
    _index(sketch, edge["to"])
    if edge["from"] == edge["to"]:
        raise SketchError("a node cannot link to itself")
    if edge in sketch["edges"]:
        raise SketchError(f"there is already a link from {edge['from']!r} to {edge['to']!r}")
    sketch["edges"].append(edge)
    return {"op": "link", "edge": _copy(edge)}


def apply(sketch: Sketch, ops: list[SketchOp]) -> tuple[Sketch, list[SketchOp]]:
    """(the new sketch, the ops as applied). Raises SketchError and leaves `sketch` untouched.

    `add` takes the whole node (its `origin` and `confirmed` are the caller's to set: the shaping
    turn computes them, a model never claims them). `change` takes the node's id and only the fields
    that change (label, detail, kind, slot). `remove` takes a node (by id) or an edge; removing a node
    answers one `remove` per edge it took with it, then the node. `link` takes an edge.
    """
    out = copy.deepcopy(sketch)
    applied: list[SketchOp] = []
    for op in ops:
        name = op.get("op")
        raw_node = cast("dict[str, Any]", op.get("node") or {})
        if name == "add":
            applied.append(_add(out, raw_node))
        elif name == "change":
            applied.append(_change(out, raw_node))
        elif name == "remove":
            applied.extend(_remove(out, op))
        elif name == "link":
            applied.append(_link(out, op))
        else:
            raise SketchError("the op must be add, change, remove or link")
    return out, applied


def confirm(sketch: Sketch, node_ids: list[str]) -> tuple[Sketch, list[SketchOp]]:
    """Marks Athena's proposals as the person's; answers the `change` ops it made.

    A confirmed node keeps `origin: "athena"` (she wrote it) with `confirmed: true` (the person
    agreed). An unknown id raises SketchError; a node already confirmed makes no op.
    """
    out = copy.deepcopy(sketch)
    applied: list[SketchOp] = []
    for node_id in node_ids:
        node = out["nodes"][_index(out, node_id)]
        if not node["confirmed"]:
            node["confirmed"] = True
            applied.append({"op": "change", "node": copy.deepcopy(node)})
    return out, applied
