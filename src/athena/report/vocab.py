"""The block registry. STUB (WP1.0) - WP1.2 fills it."""

from __future__ import annotations

from typing import TypedDict

from athena.contracts import BlockKind


class BlockSpec(TypedDict):
    kind: BlockKind
    description: str  # when to choose it, for the composer
    needs_binding: bool
    config: dict[str, str]  # config key -> plain contract


BLOCKS: dict[BlockKind, BlockSpec] = {}


def composer_docs(kinds: list[str]) -> str:
    """The composer's vocabulary, generated from BLOCKS and the record kind catalog, stamped VOCAB."""
    raise NotImplementedError
