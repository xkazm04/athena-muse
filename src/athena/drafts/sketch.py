"""Applying sketch ops. Places never move: an op adds, changes, removes or links, never reorders."""

from __future__ import annotations

from athena.contracts import Sketch, SketchOp


class SketchError(ValueError):
    """An op that cannot apply (unknown id, duplicate id, dangling edge, a cap). Plain words."""


def empty() -> Sketch:
    return {"nodes": [], "edges": []}


def apply(sketch: Sketch, ops: list[SketchOp]) -> tuple[Sketch, list[SketchOp]]:
    """(the new sketch, the ops as applied). Raises SketchError and leaves `sketch` untouched."""
    raise NotImplementedError


def confirm(sketch: Sketch, node_ids: list[str]) -> tuple[Sketch, list[SketchOp]]:
    """Marks Athena's proposals as the person's; answers the `change` ops it made."""
    raise NotImplementedError
