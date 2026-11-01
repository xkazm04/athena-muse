"""The kind catalog: one entry per RecordKind. STUB (WP1.0) - WP1.1 fills it."""

from __future__ import annotations

from typing import Any, TypedDict

from athena.contracts import RecordKind

#: The kinds Athena may put on her own, as finds (the rest file a card).
FINDS: frozenset[RecordKind] = frozenset({"creator", "track"})


class KindSpec(TypedDict):
    kind: RecordKind
    description: str  # read by the report composer; generated docs come from here (one authority)
    fields: dict[str, str]  # field -> plain description, for the composer
    numeric: list[str]  # fields a block may sum, take last of or draw as a series


CATALOG: dict[RecordKind, KindSpec] = {}


def validate(kind: RecordKind, body: dict[str, Any]) -> dict[str, Any]:
    """The body, cleaned, or ApiError("bad_request", <plain reason>)."""
    raise NotImplementedError


def key_of(kind: RecordKind, body: dict[str, Any]) -> str:
    """The record's key under its kind's rule (track: url, stat: `<metric>@<measured_at>`, ...)."""
    raise NotImplementedError
