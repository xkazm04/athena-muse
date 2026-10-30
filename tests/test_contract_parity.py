"""The Python and TypeScript contracts name the same routes, catalog, caps and enum values."""

from __future__ import annotations

import re
import typing
from pathlib import Path

from athena import contracts

TS = (Path(__file__).resolve().parents[1] / "apps/desktop/src/lib/contract.ts").read_text(encoding="utf-8")


def _ts_object(name: str) -> dict[str, str]:
    m = re.search(rf"export const {name}[^=]*=\s*\{{(.*?)\n\}}", TS, re.S)
    assert m, name
    return dict(re.findall(r"(\w+):\s*\"?([\w/{}-]+)\"?", m.group(1)))


def _ts_union(name: str) -> set[str]:
    m = re.search(rf"export type {name} =([^;]+);", TS)
    assert m, name
    return set(re.findall(r"\"(\w+)\"", m.group(1)))


def test_routes_match() -> None:
    assert _ts_object("ROUTES") == contracts.ROUTES


def test_catalog_matches() -> None:
    assert _ts_object("CATALOG") == dict(contracts.CATALOG)


def test_caps_match() -> None:
    drafts = ("FOLLOW_UPS_MAX", "REPAIRS_MAX", "SKETCH_NODES_MAX", "LABEL_MAX", "NEED_MAX", "DETAIL_MAX")
    drafts += ("ASK_TEXT_MAX", "SUGGESTIONS_MIN", "SUGGESTIONS_MAX")
    twins = ("TWINS_MAX", "SAMPLES_MAX", "BAR_MIN", "BAR_MAX", "BAR_DEFAULT", "RISKS_MAX")
    twins += ("POLL_SECONDS_DEFAULT", "DIAL_MIN", "DIAL_MAX")
    for cap in ("NAME_MAX", "BRIEF_MAX", "APPS_MAX", "SPACES_MAX", "HUE_MAX", "TEXT_MAX", *drafts, *twins):
        m = re.search(rf"export const {cap} = (\d+);", TS)
        assert m and int(m.group(1)) == getattr(contracts, cap), cap


def test_enums_match() -> None:
    names = ("ErrorWord", "EngineId", "KeySource", "MemoryKind", "Role", "ActionClass", "CardState")
    chores = ("SenseName", "FeaturedStatus", "BenchWord", "ChoreOrigin")
    drafts = (
        "DraftStep",
        "Slot",
        "SketchKind",
        "NodeOrigin",
        "SketchOpName",
        "Mark",
        "DraftVerdict",
        "StageView",
    )
    twins = ("Place", "ChannelKind", "Autonomy", "TwinState", "ChannelStatus", "ChannelHealth")
    twins += (
        "MissionState",
        "SendDecision",
        "WaitReason",
        "TwinMark",
        "ChoreKind",
        "DialSource",
        "TwinTurnSide",
    )
    twins += ("TwinMessageKind", "PieceOpName", "SetupPanel", "FactSuggest", "ConnectState")
    for name in (*names, "Verdict", "Surface", "ActionName", "AppEventType", *chores, *drafts, *twins):
        assert _ts_union(name) == set(typing.get_args(getattr(contracts, name))), name


def test_proof_op_matches() -> None:
    # ">=" is not a word, so _ts_union cannot read it; the operators are named here.
    assert set(typing.get_args(contracts.ProofOp)) == {">=", "<="}
    assert 'export type ProofOp = ">=" | "<=";' in TS


def test_list_envelopes_match() -> None:
    envelopes = (("SpaceList", "spaces"), ("TurnList", "turns"), ("CardList", "cards"))
    twins = (("ConnectionList", "connections"),)
    for name, key in (*envelopes, ("ChoreList", "chores"), ("ExpectedList", "expected"), *twins):
        assert list(getattr(contracts, name).__annotations__) == [key], name
        assert re.search(rf"export interface {name} \{{\s*{key}: \w+\[\];\s*\}}", TS), name


def _py_event_types(*classes: type) -> set[str]:
    return {typing.get_args(typing.get_type_hints(c)["type"])[0] for c in classes}


def _ts_event_types(name: str) -> set[str]:
    m = re.search(rf"export type {name} =(.*?);\n", TS, re.S)
    assert m, name
    return set(re.findall(r'type: "(\w+)"', m.group(1)))


def test_stream_event_types_match() -> None:
    c = contracts
    turn = (c.StartEvent, c.TextEvent, c.ToolEvent, c.CardEvent, c.DoneEvent, c.ErrorEvent)
    stage = (c.SketchEvent, c.AskEvent, c.CoverageEvent)
    assert _ts_event_types("TurnEvent") == _py_event_types(*turn, *stage)
    author = (c.AuthorWriting, c.AuthorRepair, c.AuthorWritten, c.AuthorFailed, c.ErrorEvent)
    assert _ts_event_types("AuthorEvent") == _py_event_types(*author)
    rehearsal = (c.RehearsalPhase, c.RehearsalCard, c.RehearsalScored, c.ErrorEvent)
    assert _ts_event_types("RehearsalEvent") == _py_event_types(*rehearsal)
    setup = (c.TwinSketchEvent, c.TwinAskEvent, c.TwinCoverageEvent)
    assert _ts_event_types("TwinSetupEvent") == _py_event_types(*turn, *setup)
    twin_rehearsal = (c.TwinTurnEvent, c.TwinOutcomeEvent, c.ErrorEvent)
    assert _ts_event_types("TwinRehearsalEvent") == _py_event_types(*twin_rehearsal)


def test_draft_shapes_match() -> None:
    # Every key of every draft shape is on both sides; TS optional keys end in "?".
    shapes = ("SketchNode", "Sketch", "SketchOp", "Ask", "ExpectedCard", "KeyMark", "MissingCard")
    shapes += ("NeverLine", "PracticeApp")
    bodies = ("SayBody", "ConfirmBody", "DropBody", "KeyBody", "VerdictBody", "DraftAbandoned")
    for name in (*shapes, "DraftKey", "Draft", *bodies):
        m = re.search(rf"export interface {name} \{{(.*?)\n\}}", TS, re.S)
        assert m, name
        ts_keys = set(re.findall(r"^\s+(\w+)\??:", m.group(1), re.M))
        assert ts_keys == set(getattr(contracts, name).__annotations__), name


def _ts_interface_keys(name: str) -> dict[str, bool]:
    """An interface's keys, its parent's included, each mapped to whether it is optional."""
    m = re.search(rf"export interface {name}(?: extends (\w+))? \{{(.*?)\n\}}", TS, re.S)
    assert m, name
    keys = _ts_interface_keys(m.group(1)) if m.group(1) else {}
    keys.update({k: bool(q) for k, q in re.findall(r"^\s+(\w+)(\??):", m.group(2), re.M)})
    return keys


def _py_keys(name: str) -> dict[str, bool]:
    hints = typing.get_type_hints(getattr(contracts, name), include_extras=True)
    return {k: typing.get_origin(v) is typing.NotRequired for k, v in hints.items()}


def test_twin_shapes_match() -> None:
    # Every key of every twin shape is on both sides, and optional on one side exactly when it is on
    # the other: an absent value is an omitted key (never null) on both.
    shapes = ("Piece", "StyleDial", "Sample", "NotionPage", "ChorePreset", "MemoryFact", "AutonomySplit")
    shapes += ("TwinChannel", "MissionBeat", "MissionTurn", "TwinFiled", "Mission", "TwinDraft", "TwinWeek")
    shapes += ("TwinSummary", "TwinAsk", "TwinDetail", "TwinStats", "PieceOp", "Connection")
    shapes += ("ConnectFlow", "TwinPreview")
    bodies = (
        "NewTwinBody",
        "TwinSayBody",
        "PiecesBody",
        "SamplesBody",
        "DialsBody",
        "PagesBody",
        "ChoresBody",
    )
    bodies += ("AutonomyBody", "MemoryBody", "RehearseBody", "MarkBody", "NewMissionBody", "ConnectBody")
    bodies += ("DecisionEdit", "DecisionBody")
    for name in (*shapes, "TwinPage", "ConnectionList", *bodies):
        assert _ts_interface_keys(name) == _py_keys(name), name


def test_twin_page_envelope_matches() -> None:
    assert list(contracts.TwinPage.__annotations__) == ["twins", "stats"]
    assert re.search(r"export interface TwinPage \{\s*twins: TwinSummary\[\];\s*stats: TwinStats;\s*\}", TS)


def test_place_coverage_has_one_key_per_place() -> None:
    places = list(typing.get_args(contracts.Place))
    assert list(contracts.PlaceCoverage.__annotations__) == places
    assert "export type PlaceCoverage = Record<Place, CoverageValue>;" in TS


def test_twin_actions_are_gated() -> None:
    assert contracts.CATALOG["twin_send"] == contracts.CATALOG["twin_note"] == "gated"
