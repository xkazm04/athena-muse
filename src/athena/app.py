"""The daemon's parts, built once and handed to the routes. Tests build one over ":memory:"."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from athena.apps.client import AppClients
from athena.apps.store import Apps
from athena.browser.files import Files
from athena.browser.relay import Relay
from athena.browser.sites import Sites
from athena.busy import Busy
from athena.connectors.part import Connectors
from athena.conversation import Conversation
from athena.drafts.jobs import Jobs, recover
from athena.drafts.store import Drafts
from athena.events import Events
from athena.gate import Gate
from athena.ledger import Ledger
from athena.mcp import Leases
from athena.memory import Memory
from athena.peer.listener import PeerHost
from athena.records.store import Records
from athena.routines.store import Routines
from athena.settings import Settings
from athena.spaces import Spaces
from athena.store import Store
from athena.twins.store import Twins


@dataclass
class Daemon:
    data_dir: Path | None  # None = nothing on disk (tests); the key file then lives nowhere
    store: Store
    busy: Busy
    events: Events
    spaces: Spaces
    memory: Memory
    ledger: Ledger
    conversation: Conversation
    settings: Settings
    gate: Gate
    drafts: Drafts
    connectors: Connectors  # connected accounts (ADR 0008); nothing on disk or on the wire without a data dir
    twins: Twins  # the twins' tables (ADR 0008-0010)
    relay: Relay  # her browser in the desktop shell (ADR 0013)
    files: Files  # a project's files (ADR 0013)
    sites: Sites  # a project's sites: the browser's trust list, set up by onboarding (ADR 0014)
    records: Records  # a project's records, append-only revisions (business Phase 1)
    routines: Routines  # a project's routines and their runs; the host's claims (business Phase 2)
    apps: Apps  # a project's apps by kind, and this device's offered apps (ADR 0025, 0026)
    mcp: Leases  # who may call the MCP server, and for which project (ADR 0015)
    peers: PeerHost | None = None  # other devices (ADR 0017); None = off (tests, --no-peer, no data dir)
    mcp_url: str | None = None  # set once the server knows its port; None = no MCP (tests, unless set)
    app_clients: AppClients = field(default_factory=AppClients)  # live app connections (ADR 0025)
    jobs: Jobs = field(default_factory=Jobs)  # each draft's last background job (ADR 0020)

    @classmethod
    def open(cls, data_dir: Path | None, *, peers: bool = False, peer_port: int | None = None) -> Daemon:
        if data_dir is not None:
            data_dir.mkdir(parents=True, exist_ok=True)
        store = Store(data_dir / "athena.db" if data_dir is not None else ":memory:")
        busy = Busy()
        events = Events()
        daemon = cls(
            data_dir=data_dir,
            store=store,
            busy=busy,
            events=events,
            spaces=Spaces(store, busy, data_dir),
            memory=Memory(store),
            ledger=Ledger(store),
            conversation=Conversation(store),
            settings=Settings(store),
            gate=Gate(store, events),
            drafts=Drafts(store, data_dir),
            connectors=Connectors.open(data_dir),
            twins=Twins(store),
            relay=Relay(),
            files=Files(store, data_dir),
            sites=Sites(store),
            records=Records(store, events),
            routines=Routines(store, events),
            apps=Apps(store, data_dir),
            mcp=Leases(),
            peers=_peer_host(data_dir, peer_port) if peers and data_dir is not None else None,
        )
        recover(daemon)  # a job still `running` on disk was cut off by the app closing
        return daemon

    def active_space(self) -> str:
        """The active project, failing closed to core when its space is gone."""
        active = self.settings.active_space()
        return active if self.spaces.exists(active) else ""


def _peer_host(data_dir: Path, port: int | None) -> PeerHost:
    """The peer surface (ADR 0017). Nothing is written, and nothing listens, until a device pairs."""
    return PeerHost(data_dir / "peer") if port is None else PeerHost(data_dir / "peer", port=port)
