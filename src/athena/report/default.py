"""The layout a project gets before Athena arranges it. STUB (WP1.0) - WP1.2 fills it."""

from __future__ import annotations

from athena.contracts import RecordKind, ReportSpec


def default_spec(title: str, kinds: list[RecordKind]) -> ReportSpec:
    raise NotImplementedError
