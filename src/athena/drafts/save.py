"""The verdict: `keep` copies the chore into the person's library and sets the Project's brief and
apps; `revise` returns the draft to `shape` with the person's note."""

from __future__ import annotations

from athena.app import Daemon
from athena.contracts import Draft, DraftVerdict


def verdict(daemon: Daemon, draft_id: str, word: DraftVerdict, note: str | None) -> Draft:
    raise NotImplementedError
