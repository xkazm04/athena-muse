"""Every number on the report, computed from records. The model's spec only says what to count; a block's
value is read here from the latest revisions, so a figure always traces to a records query.

A count of nothing is a real `count: 0`; a sum or a last reading over no records is absent (the key is
omitted), never 0."""

from __future__ import annotations

from typing import Any

from athena.contracts import Binding, Block, BlockValue, Card, RecordItem, SeriesPoint, StageCount
from athena.records.store import Records
from athena.report import vocab


def _matches(item: RecordItem, filt: dict[str, Any]) -> bool:
    body = item["body"]
    for field, want in filt.items():
        if want is None:
            if field in body:
                return False
        elif field not in body or body[field] != want:
            return False
    return True


def matching(records: Records, space_id: str, binding: Binding) -> list[RecordItem]:
    """The latest revision of every key of the bound kind that passes the filter, newest first."""
    items = records.latest(space_id, binding["kind"])
    filt = binding.get("filter") or {}
    return [i for i in items if _matches(i, filt)]


def _when(item: RecordItem) -> str:
    """When a reading was taken: a stat's `measured_at`, else when the revision was written."""
    measured = item["body"].get("measured_at")
    return measured if isinstance(measured, str) and measured else item["created"]


def _number(raw: Any) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        return None
    return float(raw)


def _count(records: Records, space_id: str, binding: Binding) -> int:
    if not binding.get("filter"):
        return records.count(space_id, binding["kind"])  # every key, past the page cap
    return len(matching(records, space_id, binding))


def _numbers(records: Records, space_id: str, binding: Binding) -> list[tuple[str, float]]:
    """(when, figure) of each matching record whose field holds a figure, oldest first."""
    field = binding.get("field", "")
    out = []
    for item in matching(records, space_id, binding):
        v = _number(item["body"].get(field))
        if v is not None:
            out.append((_when(item), v))
    out.sort(key=lambda p: p[0])
    return out


def _items(records: Records, space_id: str, block: Block) -> list[RecordItem]:
    binding = block.get("binding")
    if binding is None:
        return []
    items = matching(records, space_id, binding)
    if block["kind"] == "thread":
        items.sort(key=lambda i: str(i["body"].get("last_at") or i["created"]), reverse=True)
    else:
        items.sort(key=lambda i: i["created"], reverse=True)
    return items[: int(block["config"].get("limit", vocab.ITEMS_MAX))]


def value(records: Records, space_id: str, block: Block, cards: list[Card]) -> BlockValue:
    kind = block["kind"]
    binding = block.get("binding")
    out: BlockValue = {}
    if kind == "cards":
        out["cards"] = [c for c in cards if c["space_id"] == space_id and c["state"] == "waiting"]
    elif kind == "pipeline":
        stages: list[StageCount] = []
        for stage in block["config"].get("stages", []):
            stages.append({"label": stage["label"], "count": _count(records, space_id, stage["binding"])})
        out["stages"] = stages
    elif kind in ("queue", "list", "thread"):
        out["items"] = _items(records, space_id, block)
    elif binding is not None and kind in ("stat", "trend"):
        agg = binding.get("agg", "series" if kind == "trend" else "count")
        if agg == "count":
            out["count"] = _count(records, space_id, binding)
        elif agg == "series":
            points: list[SeriesPoint] = [{"t": t, "v": v} for t, v in _numbers(records, space_id, binding)]
            out["series"] = points[-vocab.SERIES_MAX :]
        else:
            figures = _numbers(records, space_id, binding)
            if figures:  # no records: the value is absent, never 0
                out["value"] = figures[-1][1] if agg == "last" else sum(v for _, v in figures)
    return out
