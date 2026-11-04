"""Apps offered across paired devices (ADR 0026). STUB: the Director's signatures; WP3 fills them.

The offering side (B) serves, on the overlay listener, with the ``apps`` grant:
``GET /peer/apps`` -> OfferedList; ``POST /peer/apps/{app_id}/call`` (PeerAppCall) -> AppAnswer,
re-deriving each tool's class from B's own listing and answering 403 ``approval_missing`` for a
gated tool without ``approval_id``; ``GET /peer/apps/{app_id}/file?path=`` -> the bytes of a file
under the app's ``output_dir`` only (``outside_output`` 403 otherwise; cap APP_FILE_MAX_BYTES).

The calling side (A) uses the three functions below; every failure is an AppAnswer / ApiError in
plain words, never a traceback.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from athena.contracts import AppAnswer, OfferedApp

if TYPE_CHECKING:
    from athena.app import Daemon


def offers(daemon: Daemon, peer_id: str) -> list[OfferedApp]:
    """What a paired device offers this one (live call to its /peer/apps)."""
    raise NotImplementedError


def call_remote(
    daemon: Daemon,
    peer_id: str,
    remote_app_id: str,
    tool: str,
    arguments: dict[str, Any],
    approval_id: str | None,
) -> AppAnswer:
    raise NotImplementedError


def fetch_remote(daemon: Daemon, peer_id: str, remote_app_id: str, path: str, dest: Path) -> int:
    """Streams one file from the peer's app output folder into `dest`; returns its size in bytes."""
    raise NotImplementedError
