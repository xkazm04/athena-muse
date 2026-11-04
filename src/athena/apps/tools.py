"""The tools she is offered for a project's apps, and their dispatch (ADR 0025, 0026). STUB; WP2 fills it.

Names: ``<slug>__<tool>`` for this device's instance, ``<slug>_on_<device_slug>__<tool>`` for a paired
device's (WP3's remote call through :mod:`athena.peer.apps`), and ``app_fetch`` for pulling a file
from an app's output folder into the project's files. A name over APP_TOOL_NAME_MAX is not offered.
A call runs under ``app_read`` (the tool's access is auto) or files an ``app_act`` card (gated); the
signed card runs the call once. Offered only inside a project, from the last probe's tool list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from athena.app import Daemon


def offered(daemon: Daemon, space_id: str) -> list[dict[str, Any]]:
    """Function-tool definitions (the shape `turn.TOOLS` uses) for the space's apps; [] in core."""
    raise NotImplementedError


def owns(daemon: Daemon, space_id: str, name: str) -> bool:
    raise NotImplementedError
