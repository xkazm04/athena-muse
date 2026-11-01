"""This PC's vitals, assembled for the daemon (ADR 0017, vitals).

:class:`VitalsService` puts the pieces together - the :class:`Probe` on the data directory's volume,
the :class:`Gate`, the :class:`Sampler` thread - and serves ``GET /vitals``. Given the peer host it
sets ``host.presence.own_vitals`` itself, publishes ``vitals.changed`` on the host bus, and starts
and stops the sampler with the host (``on_start`` / ``on_close``), so a test or a second Athena in
the same process never spawns ``nvidia-smi``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import BaseRoute, Route

from athena.vitals import VitalsView
from athena.vitals.gate import Gate
from athena.vitals.probe import Probe
from athena.vitals.sampler import Sampler

if TYPE_CHECKING:
    from athena.peer.listener import PeerHost

__all__ = ["VitalsService"]


class VitalsService:
    """The probe, the gate and the sampler of one daemon, and what it serves."""

    def __init__(self, *, data_dir: Path, host: PeerHost | None = None, probe: Probe | None = None) -> None:
        self.host = host
        self.probe = probe or Probe(data_dir)
        self.gate = Gate(publish=host.publish if host is not None else None)
        self.sampler = Sampler(self.probe, self.gate)
        if host is not None:
            host.presence.own_vitals = self.gate.vitals
            host.on_start.append(self.start)
            host.on_close.append(self.stop)

    def vitals(self) -> VitalsView:
        """The latest snapshot; a reading is taken now when the sampler has not taken one yet."""
        view = self.gate.vitals()
        if view is None:
            self.sampler.sample()
            view = self.gate.vitals()
        assert view is not None  # observe() has run: the gate has a reading
        return view

    def routes(self) -> list[BaseRoute]:
        """``GET /vitals`` -> ``{ok, vitals: VitalsView}``, this PC (loopback, behind the bearer)."""

        def get(request: Request) -> JSONResponse:
            return JSONResponse({"ok": True, "vitals": self.vitals()})

        return [Route("/vitals", get, methods=["GET"])]

    def start(self) -> None:
        self.sampler.start()

    def stop(self) -> None:
        self.sampler.stop()
