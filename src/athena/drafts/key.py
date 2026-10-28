"""The answer key: the person's marks, never Athena's. yes -> eligible, no -> trap, never -> forbidden."""

from __future__ import annotations

from typing import Any

from athena.app import Daemon
from athena.contracts import Draft, KeyBody
from athena.engine import Engine


def put_key(daemon: Daemon, engine: Engine, draft_id: str, body: KeyBody) -> Draft:
    """Stores the key on the draft and writes the chore's `truth.json` from it. A missing line is
    placed on a practice-app tool and key when Athena can; otherwise it is kept unscored."""
    raise NotImplementedError


def truth(key: dict[str, Any]) -> dict[str, Any]:
    """`truth.json` for a stored DraftKey, exactly from the marks."""
    raise NotImplementedError
