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
    for cap in ("NAME_MAX", "BRIEF_MAX", "APPS_MAX", "SPACES_MAX", "HUE_MAX", "TEXT_MAX"):
        m = re.search(rf"export const {cap} = (\d+);", TS)
        assert m and int(m.group(1)) == getattr(contracts, cap), cap


def test_enums_match() -> None:
    names = ("ErrorWord", "EngineId", "KeySource", "MemoryKind", "Role", "ActionClass", "CardState")
    chores = ("SenseName", "FeaturedStatus", "BenchWord")
    for name in (*names, "Verdict", "Surface", "ActionName", "AppEventType", *chores):
        assert _ts_union(name) == set(typing.get_args(getattr(contracts, name))), name


def test_proof_op_matches() -> None:
    # ">=" is not a word, so _ts_union cannot read it; the operators are named here.
    assert set(typing.get_args(contracts.ProofOp)) == {">=", "<="}
    assert 'export type ProofOp = ">=" | "<=";' in TS


def test_list_envelopes_match() -> None:
    envelopes = (("SpaceList", "spaces"), ("TurnList", "turns"), ("CardList", "cards"))
    for name, key in (*envelopes, ("ChoreList", "chores")):
        assert list(getattr(contracts, name).__annotations__) == [key], name
        assert re.search(rf"export interface {name} \{{\s*{key}: \w+\[\];\s*\}}", TS), name
