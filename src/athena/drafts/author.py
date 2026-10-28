"""Authoring: the agreed sketch and the conversation become `playbook.json` and `world.json` under
`<data_dir>/drafts/<draft_id>/`, checked by `load_chore`, with up to REPAIRS_MAX silent repairs."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from athena.app import Daemon
from athena.engine import Engine


def write(daemon: Daemon, engine: Engine, draft_id: str) -> Iterator[dict[str, Any]]:
    """AuthorEvents: `writing`, `repair`*, then `written` or `author_failed`. Validates first."""
    raise NotImplementedError
