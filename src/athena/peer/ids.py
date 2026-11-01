"""Ids the peer package mints: ``dev_`` for a device, ``pair_`` for one pairing window (ADR 0017)."""

from __future__ import annotations

import re

from athena.clock import mint as _mint

__all__ = ["is_id", "mint"]

PREFIXES: dict[str, str] = {"device": "dev_", "pairing": "pair_"}
_SHAPE = {kind: re.compile(rf"^{re.escape(prefix)}[0-9a-f]{{12}}$") for kind, prefix in PREFIXES.items()}


def mint(kind: str) -> str:
    return _mint(PREFIXES[kind])


def is_id(kind: str, value: str) -> bool:
    shape = _SHAPE.get(kind)
    return bool(shape and isinstance(value, str) and shape.match(value))
