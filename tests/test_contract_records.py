"""Business Phase 1: the records and report shapes are the same on both sides of the wire."""

from __future__ import annotations

import typing

from athena import contracts
from test_contract_parity import TS, _py_keys, _ts_interface_keys, _ts_union

ENUMS = (
    "RecordKind",
    "RecordBy",
    "TrackVerdict",
    "AgreementState",
    "SunoPlan",
    "ThreadChannel",
    "RenderState",
    "BlockKind",
    "BindingAgg",
)
SHAPES = (
    "CreatorBody",
    "TrackBody",
    "ThreadBody",
    "AgreementBody",
    "FileRecordBody",
    "RenderBody",
    "ReleaseBody",
    "StatBody",
    "RecordItem",
    "RecordList",
    "RecordPutBody",
    "TrackVerdictBody",
    "KindsBody",
    "MayRender",
    "Binding",
    "Block",
    "ReportSpec",
    "SeriesPoint",
    "StageCount",
    "BlockValue",
    "ReportView",
    "PinsBody",
    "SpaceSummary",
)
CAPS = ("RECORDS_PAGE_MAX", "BLOCKS_MAX", "REPORT_TITLE_MAX", "CALLOUT_MAX", "RECOMPOSE_MIN_S", "VOCAB")


def test_record_enums_match() -> None:
    for name in ENUMS:
        assert _ts_union(name) == set(typing.get_args(getattr(contracts, name))), name


def test_record_shapes_match() -> None:
    # Every key on both sides, optional on one side exactly when on the other.
    for name in SHAPES:
        assert _ts_interface_keys(name) == _py_keys(name), name


def test_record_caps_match() -> None:
    import re

    for cap in CAPS:
        m = re.search(rf"export const {cap} = (\d+);", TS)
        assert m and int(m.group(1)) == getattr(contracts, cap), cap


def test_record_list_envelope() -> None:
    assert list(contracts.RecordList.__annotations__) == ["records"]


def test_record_actions() -> None:
    # The class is the floor: record_put of a non-find kind files a card (athena.records).
    assert contracts.CATALOG["record_list"] == contracts.CATALOG["record_put"] == "auto"
