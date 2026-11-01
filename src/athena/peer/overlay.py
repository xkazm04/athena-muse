"""Is there a private overlay on this machine, and what is this device's address on it (ADR 0017).

The peer listener binds the overlay interface's own address and nothing else, so before it binds it
asks the overlay client. Three answers, the ``overlay.state`` of ``GET /devices``:

``absent``
    No ``tailscale`` binary, or it would not run: nothing is installed, and the listener stays down.
``logged_out``
    The client is installed but its backend is not ``Running`` (``NeedsLogin``, ``Stopped``, ...).
``up``
    Running, with an IPv4 overlay address from ``tailscale ip -4``.

Both commands are fixed argv lists - no shell, no string from anywhere else - with a short timeout
and no window on Windows. :class:`TailscaleProbe` is the default; a test hands the host any
callable returning an :class:`Overlay` instead, which is how the suite runs with no overlay at all.
"""

from __future__ import annotations

import ipaddress
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from athena.peer.classify import peer_class

__all__ = [
    "NO_WINDOW",
    "PEER_LIMIT",
    "PROBE_TIMEOUT_S",
    "Overlay",
    "OverlayPeer",
    "OverlayProbe",
    "OverlayState",
    "Status",
    "TailscaleProbe",
    "overlay_peers",
    "parse_status",
    "read_status",
]

OverlayState = Literal["absent", "logged_out", "up"]
PROBE_TIMEOUT_S = 3.0
#: ``CREATE_NO_WINDOW`` on Windows, nothing elsewhere: the daemon is a windowless sidecar.
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
#: The most devices the join form's pick list shows.
PEER_LIMIT = 30


@dataclass(frozen=True)
class Overlay:
    state: OverlayState
    #: This device's overlay IPv4 address when ``up``; ``None`` otherwise.
    address: str | None = None


OverlayProbe = Callable[[], Overlay]


class TailscaleProbe:
    """``tailscale status --json`` for the state, then ``tailscale ip -4`` for the address."""

    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable

    def __call__(self) -> Overlay:
        binary = self.executable or _find_tailscale()
        if binary is None:
            return Overlay("absent")
        status = _run([binary, "status", "--json"])
        if status is None:
            return Overlay("absent")
        try:
            backend = json.loads(status).get("BackendState")
        except (json.JSONDecodeError, AttributeError):
            backend = None
        if backend != "Running":
            return Overlay("logged_out")
        address = _first_v4(_run([binary, "ip", "-4"]) or "")
        return Overlay("up", address) if address else Overlay("logged_out")


def _find_tailscale() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        candidate = Path(program_files) / "Tailscale" / "tailscale.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def _run(argv: list[str]) -> str | None:
    try:
        done = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_S,
            check=False,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # ``status --json`` exits non-zero when logged out but still prints the JSON.
    return done.stdout or None


def _first_v4(text: str) -> str | None:
    for line in text.split():
        try:
            ip = ipaddress.ip_address(line.strip())
        except ValueError:
            continue
        if isinstance(ip, ipaddress.IPv4Address):
            return str(ip)
    return None


# --- the status document -----------------------------------------------------------------------


@dataclass(frozen=True)
class OverlayPeer:
    name: str
    ip: str | None
    os: str
    online: bool


@dataclass(frozen=True)
class Status:
    """What ``tailscale status --json`` said, or that there was nothing to ask."""

    installed: bool
    logged_in: bool = False
    ip: str | None = None
    peers: tuple[OverlayPeer, ...] = ()


def _v4(addresses: object) -> str | None:
    if not isinstance(addresses, list):
        return None
    for item in addresses:
        if isinstance(item, str) and "." in item and peer_class(item) == "overlay":
            return item
    return None


def parse_status(text: str) -> Status:
    """A ``tailscale status --json`` document, read defensively: anything odd is "not there"."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return Status(installed=True)
    if not isinstance(data, dict):
        return Status(installed=True)
    me = data.get("Self") if isinstance(data.get("Self"), dict) else {}
    peers: list[OverlayPeer] = []
    raw_peers = data.get("Peer")
    if isinstance(raw_peers, dict):
        for row in raw_peers.values():
            if not isinstance(row, dict):
                continue
            peers.append(
                OverlayPeer(
                    name=str(row.get("HostName") or row.get("DNSName") or "a device")[:64],
                    ip=_v4(row.get("TailscaleIPs")),
                    os=str(row.get("OS") or "")[:24],
                    online=row.get("Online") is True,
                )
            )
    peers.sort(key=lambda p: (not p.online, p.name.lower()))
    return Status(
        installed=True,
        logged_in=data.get("BackendState") == "Running",
        ip=_v4(me.get("TailscaleIPs")) if isinstance(me, dict) else None,
        peers=tuple(peers),
    )


def read_status() -> Status:
    """Ask ``tailscale`` now; ``installed=False`` when there is no client to ask."""
    binary = _find_tailscale()
    if binary is None:
        return Status(installed=False)
    text = _run([binary, "status", "--json"])
    return Status(installed=False) if text is None else parse_status(text)


def overlay_peers(status: Status | None = None) -> dict[str, object]:
    """The other devices on the private network, for the join form (``GET /devices/overlay``)."""
    status = status or read_status()
    state = "no_overlay" if not status.installed else "up" if status.logged_in else "logged_out"
    rows = [
        {"name": p.name, "ip": p.ip, "os": p.os, "online": p.online}
        for p in status.peers
        if p.ip and status.logged_in
    ]
    shown = rows[:PEER_LIMIT]
    return {
        "ok": True,
        "state": state,
        "self_ip": status.ip,
        "peers": shown,
        "showing": len(shown),
        "total": len(rows),
        "footer": "" if len(shown) >= len(rows) else f"(showing {len(shown)} of {len(rows)})",
    }
