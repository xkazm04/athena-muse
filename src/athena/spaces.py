"""Projects (wire: spaces). Owned by WP1. Stub: final signatures."""

from __future__ import annotations

from typing import Any

from athena.busy import Busy
from athena.contracts import SpaceErased, SpaceSummary
from athena.store import Store


def normalise_origin(raw: str) -> str:
    """`scheme://host[:port]`, http(s) only, lower-cased, default port dropped; a path, query or user
    part is refused with ApiError("bad_request")."""
    raise NotImplementedError


class Spaces:
    def __init__(self, store: Store, busy: Busy) -> None:
        raise NotImplementedError

    def list(self) -> list[SpaceSummary]:
        """Ordered by `updated` desc."""
        raise NotImplementedError

    def get(self, space_id: str) -> SpaceSummary:
        """ApiError("unknown_ref") when absent."""
        raise NotImplementedError

    def exists(self, space_id: str) -> bool:
        """True for CORE and for any space on record."""
        raise NotImplementedError

    def create(self, body: dict[str, Any]) -> SpaceSummary:
        """`{name, brief?, apps?, hue?}`; caps refused, never cut; the 101st refused."""
        raise NotImplementedError

    def update(self, space_id: str, patch: dict[str, Any]) -> SpaceSummary:
        raise NotImplementedError

    def erase(self, space_id: str) -> SpaceErased:
        """Under `busy.closing`: deletes stamped memory, the conversation, cards, then the space."""
        raise NotImplementedError
