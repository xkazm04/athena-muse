"""The daemon's parts, built once and handed to the routes. Tests build one over ":memory:"."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from athena.busy import Busy
from athena.conversation import Conversation
from athena.drafts.store import Drafts
from athena.events import Events
from athena.gate import Gate
from athena.ledger import Ledger
from athena.memory import Memory
from athena.settings import Settings
from athena.spaces import Spaces
from athena.store import Store


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

    @classmethod
    def open(cls, data_dir: Path | None) -> Daemon:
        if data_dir is not None:
            data_dir.mkdir(parents=True, exist_ok=True)
        store = Store(data_dir / "athena.db" if data_dir is not None else ":memory:")
        busy = Busy()
        events = Events()
        return cls(
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
        )

    def active_space(self) -> str:
        """The active project, failing closed to core when its space is gone."""
        active = self.settings.active_space()
        return active if self.spaces.exists(active) else ""
