"""A chore's invented portals as turn tools (stub: WP2 fills the bodies, keeping every signature).

The turn offers `tools()` beside its own; a call whose name `owns()` is a portal call. A READ tool
runs at once (`read`, action `portal_read`); any other kind files a card (`check`, action
`portal_act`, args `{app, tool, params}`) that `execute` answers with the tool's `says` once signed.
Portal cards do not end the turn's tool loop: one reply may file a whole pile.
"""

from __future__ import annotations

from typing import Any

from athena.chores.spec import Chore

#: Model-facing tool names are `<app_id>__<tool>`: function names allow no dots.
SEPARATOR = "__"


class Portal:
    def __init__(self, chore: Chore, app_id: str) -> None:
        self.chore = chore
        self.app_id = app_id

    def tools(self) -> list[dict[str, Any]]:
        """The current app's tools as OpenAI function definitions."""
        raise NotImplementedError

    def owns(self, name: str) -> bool:
        raise NotImplementedError

    def read(self, name: str, args: dict[str, Any]) -> tuple[str, str]:
        """(tool result for the model, on-screen label) for a READ tool."""
        raise NotImplementedError

    def check(self, name: str, args: dict[str, Any]) -> tuple[str, dict[str, Any]] | str:
        """For a gated tool: (card label, card args `{app, tool, params}`) or a plain refusal."""
        raise NotImplementedError

    def execute(self, args: dict[str, Any]) -> str:
        """A signed `portal_act` card: the tool's `says`, its slots filled from the params."""
        raise NotImplementedError
