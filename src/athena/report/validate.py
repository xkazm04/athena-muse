"""The one validation door for a spec: the same door at dispatch (a composed answer, before it is stored)
and at render (a stored spec, before its values are computed). It keeps what survives and says, in plain
words, why each dropped block was dropped; nothing renders around it."""

from __future__ import annotations

import re
from typing import Any, NamedTuple

from athena.contracts import (
    BLOCKS_MAX,
    CALLOUT_MAX,
    REPORT_TITLE_MAX,
    VOCAB,
    Binding,
    Block,
    BlockKind,
    RecordKind,
    ReportSpec,
)
from athena.report import vocab
from athena.report.default import default_spec

_DIGIT = re.compile(r"\d")
_AGGS = frozenset(("count", "sum", "last", "series"))
NUMBER = "numbers on the report come from what the project keeps"


class Checked(NamedTuple):
    spec: ReportSpec  # what survives; the default spec when nothing does
    reasons: list[str]  # one per dropped block (or dropped callout), plain words
    default: bool  # True when nothing survived, or the answer was not a report at all
    rejected: str | None  # the whole answer was not a spec (envelope), plain words


class _Drop(Exception):
    """One block cannot be shown; the message is the reason, in plain words."""


def _cut(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _name(raw: dict[str, Any]) -> str:
    title, kind = raw.get("title"), raw.get("kind")
    if isinstance(title, str) and title.strip() and not _DIGIT.search(title):  # never echo her figure
        return f"“{_cut(title, 40)}”"
    return f"a {kind} part" if isinstance(kind, str) and kind in vocab.BLOCKS else "a part"


def _words(raw: Any, where: str, n: int) -> str:
    """A model-written string: words only, never a figure."""
    if not isinstance(raw, str):
        raise _Drop(f"its {where} is not words")
    if _DIGIT.search(raw):
        raise _Drop(f"its {where} has a number in it ({NUMBER})")
    return _cut(raw, n)


def _limit(config: dict[str, Any], out: dict[str, Any]) -> None:
    if "limit" in config:
        n = config["limit"]
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= vocab.ITEMS_MAX:
            raise _Drop(f"it asks to show {n!r} items; a part shows 1 to {vocab.ITEMS_MAX}")
        out["limit"] = n


def _only(config: dict[str, Any], kind: BlockKind, allowed: set[str]) -> None:
    extra = sorted(set(config) - allowed)
    if extra:
        raise _Drop(f"a {kind} part takes no {extra[0]}")


def _binding(raw: Any, kinds: list[RecordKind]) -> Binding:
    if not isinstance(raw, dict):
        raise _Drop("it is not tied to any entries")
    kind = raw.get("kind")
    if not isinstance(kind, str) or kind not in vocab.RECORD_KINDS:
        raise _Drop(f"it is tied to entries Athena does not keep ({kind!r})")
    if kind not in kinds:
        raise _Drop(f"this project keeps no {kind} entries")
    out: Binding = {"kind": kind}
    if "filter" in raw and raw["filter"] is not None:
        f = raw["filter"]
        ok = isinstance(f, dict) and all(
            isinstance(k, str) and (v is None or isinstance(v, str | bool)) for k, v in f.items()
        )
        if not ok:
            raise _Drop("its filter is not field = words, yes/no or absent")
        known = vocab.fields(kind)
        unknown = [k for k in f if known is not None and k not in known]
        if unknown:
            raise _Drop(f"{kind} entries have no {unknown[0]}")
        if f:
            out["filter"] = dict(f)
    if "agg" in raw and raw["agg"] is not None:
        if raw["agg"] not in _AGGS:
            raise _Drop(
                f"it asks for {raw['agg']!r}; a binding counts, sums, takes the last or draws a series"
            )
        out["agg"] = raw["agg"]
    if "field" in raw and raw["field"] is not None:
        if not isinstance(raw["field"], str):
            raise _Drop("its field is not a field name")
        out["field"] = raw["field"]
    return out


def _numeric(b: Binding) -> None:
    field = b.get("field")
    if field is None:
        raise _Drop(f"it does not say which field to {'sum' if b.get('agg') == 'sum' else 'read'}")
    if field not in vocab.numeric(b["kind"]):
        raise _Drop(f"{field} is not a figure {b['kind']} entries keep")
    if b["kind"] == "stat" and not isinstance(b.get("filter", {}).get("metric"), str):
        raise _Drop("it reads stats without naming one metric")


def _block(raw: dict[str, Any], kinds: list[RecordKind]) -> Block:
    kind = raw.get("kind")
    if not isinstance(kind, str) or kind not in vocab.BLOCKS:
        raise _Drop(f"{kind!r} is not a part the report can show")
    bk = kind
    span = raw.get("span")
    if isinstance(span, bool) or not isinstance(span, int) or not 1 <= span <= 12:
        raise _Drop(f"it is {span!r} columns wide; a part is 1 to 12")
    title = _words(raw.get("title", ""), "title", REPORT_TITLE_MAX)
    config = raw.get("config", {})
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise _Drop("its settings are not settings")
    block: Block = {"id": raw["id"], "kind": bk, "title": title, "span": span, "config": {}}
    spec = vocab.BLOCKS[bk]
    if spec["needs_binding"]:
        if raw.get("binding") is None:
            raise _Drop("it is not tied to any entries")
        block["binding"] = _binding(raw["binding"], kinds)
    # A block that takes no binding ignores a stray one: there is nothing to tie it to.
    out = block["config"]
    b = block.get("binding")
    if bk == "stat":
        _only(config, bk, {"unit"})
        assert b is not None
        agg = b.setdefault("agg", "count")
        if agg not in ("count", "sum", "last"):
            raise _Drop(f"a stat counts, sums or takes the last reading, not {agg!r}")
        if agg != "count":
            _numeric(b)
        if "unit" in config:
            out["unit"] = _words(config["unit"], "unit", vocab.UNIT_MAX)
    elif bk == "trend":
        _only(config, bk, {"unit"})
        assert b is not None
        if b.setdefault("agg", "series") != "series":
            raise _Drop("a trend draws a series")
        _numeric(b)
        if "unit" in config:
            out["unit"] = _words(config["unit"], "unit", vocab.UNIT_MAX)
    elif bk == "queue":
        _only(config, bk, {"limit"})
        assert b is not None
        if b["kind"] != "track":
            raise _Drop("a queue holds tracks")
        f = b.setdefault("filter", {"verdict": None})
        if f != {"verdict": None}:
            raise _Drop("a queue holds the tracks with no verdict yet")
        b.pop("agg", None)
        b.pop("field", None)
        _limit(config, out)
    elif bk == "thread":
        _only(config, bk, {"limit"})
        assert b is not None
        if b["kind"] != "thread":
            raise _Drop("a thread part holds conversations")
        _limit(config, out)
    elif bk == "list":
        _only(config, bk, {"fields", "limit"})
        assert b is not None
        names = config.get("fields")
        if (
            not isinstance(names, list)
            or not 1 <= len(names) <= vocab.LIST_FIELDS_MAX
            or not all(isinstance(n, str) for n in names)
        ):
            raise _Drop(f"a list names 1 to {vocab.LIST_FIELDS_MAX} fields to show")
        known = vocab.fields(b["kind"])
        missing = [n for n in names if known is not None and n not in known]
        if missing:
            raise _Drop(f"{b['kind']} entries have no {missing[0]}")
        out["fields"] = list(names)
        _limit(config, out)
    elif bk == "pipeline":
        _only(config, bk, {"stages"})
        stages = config.get("stages")
        if not isinstance(stages, list) or not 1 <= len(stages) <= vocab.STAGES_MAX:
            raise _Drop(f"a pipeline has 1 to {vocab.STAGES_MAX} stages")
        clean = []
        for stage in stages:
            if not isinstance(stage, dict):
                raise _Drop("one of its stages is not a stage")
            label = _words(stage.get("label"), "stage label", vocab.LABEL_MAX)
            sb = _binding(stage.get("binding"), kinds)
            if sb.setdefault("agg", "count") != "count":
                raise _Drop("each pipeline stage is a count")
            sb.pop("field", None)
            clean.append({"label": label, "binding": sb})
        out["stages"] = clean
    else:  # cards, callout
        _only(config, bk, set())
    return block


def check(raw: Any, kinds: list[RecordKind], name: str = "") -> Checked:
    """The door. `name` is the project's name: the report's title when the answer's title is missing or
    carries a figure (the person's words may hold digits; the model's may not)."""
    if not isinstance(raw, dict) or not isinstance(raw.get("blocks"), list):
        return Checked(default_spec(name, kinds), [], True, "the answer was not a report")
    if raw.get("v", 1) != 1:
        return Checked(default_spec(name, kinds), [], True, f"it is a report of version {raw.get('v')!r}")
    reasons: list[str] = []
    title_raw = raw.get("title")
    title = name
    if isinstance(title_raw, str) and title_raw.strip() and not _DIGIT.search(title_raw):
        title = _cut(title_raw, REPORT_TITLE_MAX)
    spec: ReportSpec = {"v": 1, "vocab": VOCAB, "title": _cut(title, REPORT_TITLE_MAX), "blocks": []}

    callout = raw.get("callout")
    if isinstance(callout, str) and callout.strip():
        if _DIGIT.search(callout):
            reasons.append(f"The callout had a number in it, so it is not shown ({NUMBER}).")
        else:
            spec["callout"] = _cut(callout, CALLOUT_MAX)

    blocks: list[Any] = raw["blocks"]
    # Caps first, so the door is never wedged by the document it judges.
    for extra in blocks[BLOCKS_MAX:]:
        who = _name(extra) if isinstance(extra, dict) else "a part"
        reasons.append(f"{who[0].upper()}{who[1:]}: a report holds at most {BLOCKS_MAX} parts.")
    seen: set[str] = set()
    for item in blocks[:BLOCKS_MAX]:
        if not isinstance(item, dict):
            reasons.append("A part was not a part.")
            continue
        who = _name(item)
        who = f"{who[0].upper()}{who[1:]}"
        block_id = item.get("id")
        if not isinstance(block_id, str) or not block_id.strip():
            reasons.append(f"{who}: it has no id.")
            continue
        if block_id in seen:
            reasons.append(f"{who}: another part already has the id “{block_id}”; the first was kept.")
            continue
        try:
            block = _block(item, kinds)
        except _Drop as e:
            reasons.append(f"{who}: {e}.")
            continue
        if block["kind"] == "callout" and "callout" not in spec:
            reasons.append(f"{who}: there is no callout to show.")
            continue
        seen.add(block_id)
        spec["blocks"].append(block)

    if not spec["blocks"]:
        return Checked(default_spec(name, kinds), reasons, True, None)
    return Checked(spec, reasons, False, None)


def validate(raw: Any, kinds: list[RecordKind]) -> tuple[ReportSpec, list[str]]:
    """(what survives, why each dropped block was dropped). Unknown kinds, unbound bindings, kinds the
    project does not keep, spans outside 1..12, more than BLOCKS_MAX, and any digit in a title or the
    callout are dropped; a spec with nothing left is the default spec."""
    checked = check(raw, kinds)
    return checked.spec, checked.reasons
