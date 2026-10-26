"""A conversation per space. Owned by WP1. Stub: final signatures."""

from __future__ import annotations

from athena.contracts import Role, Turn
from athena.store import Store


class Conversation:
    def __init__(self, store: Store) -> None:
        raise NotImplementedError

    def append(
        self,
        space_id: str,
        role: Role,
        text: str,
        *,
        cost_usd: float | None = None,
        card_id: str | None = None,
    ) -> Turn:
        raise NotImplementedError

    def list(self, space_id: str, limit: int = 200) -> list[Turn]:
        """Oldest first, the last `limit` turns."""
        raise NotImplementedError

    def erase_space(self, space_id: str) -> int:
        raise NotImplementedError
