"""The apps of a project and of this device (ADR 0025, 0026). STUB: the Director's signatures; WP1 fills them.

Truth: website/local_page apps are the origins in ``spaces.apps`` (unchanged column, unchanged
consumers); their ``app_id`` is ``web_`` + the first 10 hex of sha1(origin). mcp_http/mcp_stdio apps,
device-level apps (space ``""``) and remote instances live in the ``apps`` and ``app_remotes`` tables,
erased with their space. A token is sealed with the connectors seal and never leaves this module
except through :meth:`Apps.token`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from athena.contracts import App, AppKind, AppNew, AppRemote, AppStatus, AppTool
from athena.store import Store


@dataclass(frozen=True)
class AppRow:
    """One app as the daemon uses it internally (the wire shape is :class:`~athena.contracts.App`)."""

    app_id: str
    space_id: str  # "" = device-level
    kind: AppKind
    label: str
    slug: str
    address: str  # origin | URL | argv joined by spaces
    status: AppStatus
    tools: list[AppTool] = field(default_factory=list)
    argv: list[str] | None = None
    offered: bool = False
    output_dir: str | None = None
    checked_at: str | None = None
    reason: str | None = None


class Apps:
    def __init__(self, store: Store, data_dir: object | None = None) -> None:
        self.store = store
        self.data_dir = data_dir

    def views(self, space_id: str) -> list[App]:
        """Every app of the space, the derived web ones first, in the order they were added."""
        raise NotImplementedError

    def rows(self, space_id: str) -> list[AppRow]:
        """The process kinds only (mcp_http, mcp_stdio): what tools are offered from."""
        raise NotImplementedError

    def get(self, space_id: str, app_id: str) -> AppRow:
        """ApiError not_found when the space has no such app."""
        raise NotImplementedError

    def add(self, space_id: str, body: AppNew) -> App:
        """Validates by kind (400 bad_request in plain words), seals the token, writes, publishes `app`."""
        raise NotImplementedError

    def remove(self, space_id: str, app_id: str) -> None:
        raise NotImplementedError

    def token(self, space_id: str, app_id: str) -> str | None:
        """The unsealed token for a call, or None."""
        raise NotImplementedError

    def set_probe(
        self, space_id: str, app_id: str, status: AppStatus, tools: list[AppTool], reason: str | None
    ) -> App:
        """Records a probe's finding (checked_at = now) and publishes `app`."""
        raise NotImplementedError

    def remotes(self, space_id: str, app_id: str) -> list[AppRemote]:
        raise NotImplementedError

    def put_remote(self, space_id: str, app_id: str, remote: AppRemote) -> App:
        """Attach or refresh a paired device's instance of this app; publishes `app`."""
        raise NotImplementedError

    def drop_remote(self, space_id: str, app_id: str, peer_id: str) -> None:
        raise NotImplementedError

    def offered(self) -> list[AppRow]:
        """Device-level apps marked offered (space "")."""
        raise NotImplementedError
