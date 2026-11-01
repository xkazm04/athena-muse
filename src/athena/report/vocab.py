"""The block registry: the one authority for what a report may hold. The validation door (`validate.py`)
enforces it and the composer's instructions are generated from it (`composer_docs`), so adding a block
kind is one entry here, never a hand-kept prompt beside it."""

from __future__ import annotations

import json
from typing import TypedDict, cast, get_args

from athena.contracts import BLOCKS_MAX, CALLOUT_MAX, REPORT_TITLE_MAX, VOCAB, BlockKind, RecordKind
from athena.records import kinds as record_kinds

#: Items a queue, list or thread block shows at most.
ITEMS_MAX = 10
#: Body fields a list block names at most.
LIST_FIELDS_MAX = 3
#: Stages a pipeline block holds at most.
STAGES_MAX = 6
#: Points a trend draws at most (the latest).
SERIES_MAX = 30
#: Characters in a stat's unit, and in a pipeline stage's label.
UNIT_MAX = 16
LABEL_MAX = 40

RECORD_KINDS: frozenset[str] = frozenset(get_args(RecordKind))


class BlockSpec(TypedDict):
    kind: BlockKind
    description: str  # when to choose it, for the composer
    needs_binding: bool
    config: dict[str, str]  # config key -> plain contract


BLOCKS: dict[BlockKind, BlockSpec] = {
    "stat": {
        "kind": "stat",
        "description": "One figure: how many records match, the sum of a numeric field, or its latest "
        "reading. Choose it for a headline the owner checks at a glance.",
        "needs_binding": True,
        "config": {
            "binding.agg": "`count` (the default), `sum` or `last`; `sum` and `last` name a numeric "
            "`field`, and over stat records the filter names one `metric`",
            "unit": f"optional; a word after the figure (`views`), at most {UNIT_MAX} characters, no digits",
        },
    },
    "trend": {
        "kind": "trend",
        "description": "A numeric field over time, oldest to newest, as a small line. Choose it for a "
        "reading taken again and again, such as a stat's `value` for one metric.",
        "needs_binding": True,
        "config": {
            "binding.agg": "`series`, with a numeric `field`; over stat records the filter names one "
            '`metric` (`{"metric": "views"}`)',
            "unit": f"optional; a word for the reading, at most {UNIT_MAX} characters, no digits",
        },
    },
    "queue": {
        "kind": "queue",
        "description": "Tracks waiting for the owner's verdict (keep, pass or later), newest first, each "
        "with a player. Choose it when tracks are found faster than they are judged.",
        "needs_binding": True,
        "config": {
            "binding": 'kind `track`, filter `{"verdict": null}` (tracks with no verdict yet)',
            "limit": f"optional; tracks shown, 1 to {ITEMS_MAX}",
        },
    },
    "pipeline": {
        "kind": "pipeline",
        "description": "Stages a piece of work passes through, each a count, as a funnel. Choose it to "
        "show where things stand between a first step and the last.",
        "needs_binding": False,
        "config": {
            "stages": f'1 to {STAGES_MAX} of `{{"label": <words, no digits>, "binding": <a count '
            "binding>}`, in order; the block itself has no binding",
        },
    },
    "list": {
        "kind": "list",
        "description": "The latest records of one kind, a few fields each. Choose it to show what was "
        "added lately.",
        "needs_binding": True,
        "config": {
            "fields": f"1 to {LIST_FIELDS_MAX} body fields of the bound kind to show per row",
            "limit": f"optional; rows shown, 1 to {ITEMS_MAX}",
        },
    },
    "thread": {
        "kind": "thread",
        "description": "The latest conversations with creators, most recent first. Choose it when the "
        "owner is waiting on replies.",
        "needs_binding": True,
        "config": {
            "binding": "kind `thread`",
            "limit": f"optional; conversations shown, 1 to {ITEMS_MAX}",
        },
    },
    "cards": {
        "kind": "cards",
        "description": "What waits for the owner's signature in this project. Choose it whenever "
        "something may need signing; it shows nothing when nothing waits.",
        "needs_binding": False,
        "config": {},
    },
    "callout": {
        "kind": "callout",
        "description": "The report's `callout` sentence, set apart. Choose it for one thing worth saying "
        "in words; it shows nothing without a callout.",
        "needs_binding": False,
        "config": {},
    },
}

#: Numeric fields per kind, read only while the kind catalog has no entry for a kind (WP1.1 fills the
#: catalog); the catalog's own `numeric` list wins whenever it has the kind.
_NUMERIC_UNTIL_CATALOGUED: dict[str, list[str]] = {"stat": ["value"]}


def _catalog() -> dict[str, record_kinds.KindSpec]:
    """The kind catalog, read at call time (it is WP1.1's), keyed by plain strings."""
    return cast("dict[str, record_kinds.KindSpec]", record_kinds.CATALOG)


def numeric(kind: str) -> list[str]:
    """The fields of `kind` a block may sum, take the last of or draw as a series."""
    spec = _catalog().get(kind)
    return list(spec["numeric"]) if spec else list(_NUMERIC_UNTIL_CATALOGUED.get(kind, []))


def fields(kind: str) -> list[str] | None:
    """The body fields the catalog names for `kind`; None when it has no entry (any field passes)."""
    spec = _catalog().get(kind)
    return list(spec["fields"]) if spec else None


def _kind_line(kind: str) -> str:
    spec = _catalog().get(kind)
    if spec is None:
        return f"- `{kind}`"
    lines = [f"- `{kind}`: {spec['description']}"]
    if spec["fields"]:
        lines.append("  Fields: " + "; ".join(f"`{f}` {d}" for f, d in spec["fields"].items()) + ".")
    if spec["numeric"]:
        lines.append("  Numeric: " + ", ".join(f"`{f}`" for f in spec["numeric"]) + ".")
    return "\n".join(lines)


def _block_line(spec: BlockSpec) -> str:
    lines = [f"- `{spec['kind']}`: {spec['description']}"]
    lines.append("  Binding: required." if spec["needs_binding"] else "  Binding: none.")
    lines.extend(f"  `{key}`: {contract}." for key, contract in spec["config"].items())
    return "\n".join(lines)


_EXAMPLE = {
    "v": 1,
    "vocab": VOCAB,
    "title": "<the report's title>",
    "callout": "<optional, one sentence>",
    "blocks": [
        {
            "id": "<kept from the current report, or new>",
            "kind": "queue",
            "title": "Tracks waiting for you",
            "span": 8,
            "binding": {"kind": "track", "filter": {"verdict": None}},
            "config": {"limit": ITEMS_MAX},
        }
    ],
}


def composer_docs(kinds: list[str]) -> str:
    """The composer's vocabulary, generated from BLOCKS and the record kind catalog, stamped VOCAB."""
    return "\n".join(
        [
            "You arrange one project's report: its front page, built from a closed kit of blocks. You "
            "choose blocks, tie each to the project's records, size them on a twelve-column grid and "
            "write their titles and at most one callout sentence.",
            "",
            "Never write a number. Every count, sum and reading on the report is computed from the "
            "records after you answer. A title, label, unit or callout with a digit in it is thrown away.",
            "",
            f"Block vocabulary version {VOCAB}. Stamp it as `vocab` on your answer.",
            "",
            "Answer with one JSON object and nothing else, shaped like this:",
            json.dumps(_EXAMPLE, indent=2),
            "",
            "A binding is "
            '`{"kind": <record kind>, "filter": {<body field>: <value>}, "agg": <agg>, "field": <field>}`. '
            "The filter matches a body field exactly; `null` means the field is absent. `agg` is one of "
            "`count`, `sum`, `last`, `series`; `field` is a numeric field of the kind.",
            "",
            "Ids: keep the id of every block you carry over from the current report, even when you move, "
            "resize or retitle it. Give a new block a new short id (lowercase letters and dashes). A block "
            "marked `pinned` was pinned by the owner: keep it, with its id, kind, binding and config.",
            "",
            f"Limits: at most {BLOCKS_MAX} blocks; `span` is 1 to 12 columns, and the spans of a row add "
            f"up to twelve; the title at most {REPORT_TITLE_MAX} characters; the callout at most "
            f"{CALLOUT_MAX}. A block the kit cannot show is dropped, and the owner is told why.",
            "",
            "Blocks:",
            *(_block_line(spec) for spec in BLOCKS.values()),
            "",
            "Record kinds this project keeps (bind only to these):",
            *(_kind_line(k) for k in kinds if k in RECORD_KINDS),
        ]
    )
