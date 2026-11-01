"""Several devices, one Athena: identity, pairing, and the overlay-only peer listener (ADR 0017).

Ported from portable (its ADR 0140, pairing and the Devices page; memory replication, the remote
composer, the phone page and the setup conversation are not part of this port). Each device is a
full Athena. This package is how two of them come to trust each other, built to the
device-pairing standard: a human approval in the granting device's own window is the only thing
that mints a token; tokens are born scoped (``chat``, ``approve``, ``memory``) and optionally
expiring, are claimed exactly once, and are kept only as fingerprints; admission is decided by
address class before any auth; and the listener is off until trust exists.

The modules, in the order a request meets them:

- :mod:`~athena.peer.classify` - ``loopback`` / ``overlay`` / ``refused`` for a remote address;
- :mod:`~athena.peer.overlay` - is Tailscale here, logged in, and what is this device's address;
- :mod:`~athena.peer.listener` - the peer socket, its handler, its lifecycle, and the
  :class:`~athena.peer.listener.PeerHost` that holds everything below;
- :mod:`~athena.peer.identity` - ``<data>/peer/device.json``;
- :mod:`~athena.peer.registry` - ``<data>/peer/peers.json``, who may call in;
- :mod:`~athena.peer.pairing` - the ceremony's windows, requests and single claims, in memory;
- :mod:`~athena.peer.client` - the outbound call and the sealed keys this device calls out with;
- :mod:`~athena.peer.presence` and :mod:`~athena.peer.link` - is each paired PC there right now;
- :mod:`~athena.peer.audit` - the append-only trail of who was let in or kept out;
- :mod:`~athena.peer.events` - the bus behind loopback ``GET /devices/events``;
- :mod:`~athena.peer.routes` - the peer routes (``/peer/hello``, ``/peer/pair/*``);
- :mod:`~athena.peer.devices` - the loopback routes (``/devices*``).
"""

from athena.peer.listener import DEFAULT_PEER_PORT, PeerHost, PeerRequest, PeerRoute

__all__ = ["DEFAULT_PEER_PORT", "PeerHost", "PeerRequest", "PeerRoute"]
