"""Where the peer surface meets the rest of the daemon (ADR 0017).

:func:`install` is called once by ``create_app``. It registers each feature's routes on the peer
listener (``host.add_routes(<module>.peer_routes(host, daemon))``) and returns the loopback routes
to mount on the app. A feature adds one line here and touches no other shared file.
"""

from __future__ import annotations

from starlette.routing import BaseRoute

from athena.app import Daemon
from athena.peer import apps as peer_apps
from athena.peer import devices as peer_devices
from athena.peer import phone as peer_phone
from athena.peer import remote as peer_remote
from athena.peer import replicate as peer_replicate
from athena.peer import setup as peer_setup
from athena.vitals.service import VitalsService


def install(daemon: Daemon) -> list[BaseRoute]:
    host = daemon.peers
    if host is None:
        return []
    host.add_routes(peer_replicate.peer_routes(host, daemon.memory))
    remote_turns = peer_remote.RemoteTurns()
    host.add_routes(peer_remote.peer_routes(host, daemon, remote_turns))
    host.add_routes(peer_phone.peer_routes(host))
    host.add_routes(peer_apps.peer_routes(host, daemon))
    loopback: list[BaseRoute] = []
    loopback.extend(peer_remote.loopback_routes(host))
    loopback.extend(peer_apps.loopback_routes(daemon))
    peer_setup.of(daemon)  # the hello's setup_phase and the listener's setup hold
    loopback.extend(peer_setup.routes(daemon))
    if daemon.data_dir is not None:
        loopback.extend(VitalsService(data_dir=daemon.data_dir, host=host).routes())
    # Specific loopback routes (/devices/<peer>/message ...) go BEFORE the catch-all DELETE
    # /devices/{peer_id} in devices.routes, so extend `loopback` first and append devices last.
    loopback.extend(peer_devices.routes(host))
    return loopback
