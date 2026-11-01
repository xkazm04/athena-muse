"""Business Phase 2: the routines and web-channel shapes are the same on both sides of the wire."""

from __future__ import annotations

import re
import typing

from athena import contracts
from test_contract_parity import TS, _py_keys, _ts_interface_keys, _ts_union

ENUMS = (
    "RoutineKind",
    "RoutineState",
    "RunOutcome",
    "SkipReason",
    "ConnectorKind",
    "ChannelKind",
    "WaitReason",
)
SHAPES = (
    "RoutineRun",
    "Routine",
    "RoutineList",
    "RunList",
    "RoutineBody",
    "PasteBody",
    "CreatorBody",
    "AppEvent",
)
CAPS = ("CADENCE_MIN_S", "ROUTINE_CEILING_CENTS", "RUNS_KEPT", "PASTE_MAX")


def test_routine_enums_match() -> None:
    for name in ENUMS:
        assert _ts_union(name) == set(typing.get_args(getattr(contracts, name))), name


def test_routine_shapes_match() -> None:
    for name in SHAPES:
        assert _ts_interface_keys(name) == _py_keys(name), name


def test_routine_caps_match() -> None:
    for cap in CAPS:
        m = re.search(rf"export const {cap} = (\d+);", TS)
        assert m and int(m.group(1)) == getattr(contracts, cap), cap


def test_routine_envelopes() -> None:
    assert list(contracts.RoutineList.__annotations__) == ["routines"]
    assert list(contracts.RunList.__annotations__) == ["runs"]


def test_web_send_is_always_a_card() -> None:
    assert contracts.CATALOG["twin_send_web"] == "gated"


def test_connectors_are_a_subset_of_channels() -> None:
    connectors = set(typing.get_args(contracts.ConnectorKind))
    assert connectors < set(typing.get_args(contracts.ChannelKind))


def test_a_round_runs_only_what_it_was_offered() -> None:
    import inspect

    from athena import turn

    src = inspect.getsource(turn._rounds)
    assert "if name not in offered" in src and turn.NOT_OFFERED == "That action is not offered here."
