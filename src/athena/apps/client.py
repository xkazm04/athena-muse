"""The app transports (ADR 0025). STUB: the Director's signatures; WP2 fills them.

- mcp_http: Streamable HTTP on a loopback URL only, ported from athena-portable's
  ``connectors/mcp/client.py`` (initialize, notifications/initialized, tools/list with nextCursor,
  tools/call; no redirects; 1 MiB reply cap; :data:`~athena.contracts.APP_CALL_TIMEOUT_S`).
- mcp_stdio: a child process this module spawns from argv on first use, owns, and reaps: after
  :data:`~athena.contracts.APP_IDLE_S` unused and at :meth:`AppClients.shutdown` (process tree ended).
  Stdout is the protocol; stderr is drained and kept as the last lines for a reason.
- The class of a tool: readOnlyHint, or destructiveHint false and openWorldHint false -> auto; else gated.
"""

from __future__ import annotations

from dataclasses import dataclass

from athena.apps.store import AppRow
from athena.contracts import AppAnswer, AppStatus, AppTool


@dataclass(frozen=True)
class Probe:
    status: AppStatus
    tools: list[AppTool]
    reason: str | None  # plain words; None when ok


class AppClients:
    """One live connection (or child process) per app_id, opened on demand."""

    def probe(self, row: AppRow, token: str | None) -> Probe:
        """Connect and list tools. Never raises for an app that is down: answers `unreachable`."""
        raise NotImplementedError

    def call(self, row: AppRow, token: str | None, tool: str, arguments: dict[str, object]) -> AppAnswer:
        """One tools/call; a transport failure is `is_error` with the reason in `text`."""
        raise NotImplementedError

    def reap_idle(self) -> None:
        """Stops stdio children unused for APP_IDLE_S."""
        raise NotImplementedError

    def shutdown(self) -> None:
        """Stops every child (its process tree) and closes every session."""
        raise NotImplementedError
