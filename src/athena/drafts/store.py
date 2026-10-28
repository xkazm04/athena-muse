"""The drafts table: one row per draft, its JSON columns stored as text, erased with its space."""

from __future__ import annotations

from athena.contracts import Draft
from athena.store import Store


class Drafts:
    def __init__(self, store: Store) -> None:
        self._store = store

    def create(self, space_id: str, need: str) -> Draft:
        """A new draft at step `describe` with an empty sketch, in an existing space."""
        raise NotImplementedError

    def get(self, draft_id: str) -> Draft:
        """The draft, or ApiError("unknown_ref")."""
        raise NotImplementedError

    def put(self, draft: Draft) -> Draft:
        """Writes the whole draft back, stamping `updated`; answers it as stored."""
        raise NotImplementedError

    def delete(self, draft_id: str) -> None:
        """Abandons the draft. Its Project stays."""
        raise NotImplementedError
