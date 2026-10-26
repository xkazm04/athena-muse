"""The memory wall. Owned by WP1. Stub: final signatures.

Every memory is stamped with the space it was written in (CORE = ""). A view sees
`visible_spaces(active)`: core sees ("",), a project sees ("", project).
"""

from __future__ import annotations

from athena.contracts import MemoryKind, MemoryPage, MemoryRow, SpaceCounts
from athena.store import Store


def visible_spaces(active: str) -> tuple[str, ...]:
    return ("",) if active == "" else ("", active)


class Memory:
    def __init__(self, store: Store) -> None:
        raise NotImplementedError

    def append_episode(self, space_id: str, text: str) -> MemoryRow:
        raise NotImplementedError

    def write_fact(self, space_id: str, text: str) -> MemoryRow:
        raise NotImplementedError

    def recall(self, space_id: str, query: str, limit: int = 8) -> list[MemoryRow]:
        """Full-text over episodes and facts inside `visible_spaces(space_id)`."""
        raise NotImplementedError

    def kept(self, space_id: str, limit: int = 12) -> list[MemoryRow]:
        """Exactly this space's facts (core's when ""), newest first: the frame's kept lines."""
        raise NotImplementedError

    def page(self, space_id: str, kind: MemoryKind | None, limit: int) -> MemoryPage:
        """Exactly this space's memory (core's when ""), newest first."""
        raise NotImplementedError

    def get(self, mem_id: str) -> MemoryRow:
        """ApiError("unknown_ref") when absent."""
        raise NotImplementedError

    def make_core(self, space_id: str, mem_id: str) -> MemoryRow:
        """Facts only: ApiError("bad_request") for an episode, ("unknown_ref") when not in that space."""
        raise NotImplementedError

    def forget(self, mem_id: str) -> None:
        raise NotImplementedError

    def counts(self, space_id: str) -> SpaceCounts:
        raise NotImplementedError

    def erase_space(self, space_id: str) -> SpaceCounts:
        """Deletes every memory stamped with the space; answers what went."""
        raise NotImplementedError
