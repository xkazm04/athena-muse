"""Is each paired device there right now: ``presence`` and ``link`` on ``GET /devices`` (ADR 0017).

``last_seen`` says when a peer last called *this* device. It cannot say whether that device is on
now, which the Devices page needs: a lit node for a computer that answers, a dim one for a computer
that is on but has Athena closed, a broken link for one that is gone. So a background probe asks
every :data:`PRESENCE_EVERY_S` and keeps one verdict per paired PC:

``online``
    An authorized ``GET /peer/hello`` (the token the other PC minted for this one) answered ``200``
    within :data:`HELLO_TIMEOUT_S`.
``asleep``
    No answer, but the private overlay lists the address as online: the machine is up and Athena
    there is closed, or its listener is down because it has nothing to listen for.
``unreachable``
    Neither.
``None``
    A ``401`` (the other PC removed this one: neither sleep nor a broken network, so ``link`` says
    ``removed_there``); not probed yet; a phone (nothing to say hello to); or a PC this device
    holds no key for yet.

``presence_at`` is when the current verdict began. Every change publishes ``peer.changed`` with
the ``peer_id``. A pass with no paired PC dials nothing, so a device nobody paired with never
reaches out. The state of a link is decided in one place, :func:`athena.peer.link.derive`.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlsplit

from athena.peer.client import call
from athena.peer.identity import now_iso
from athena.peer.link import HelloSeen, derive, state_of
from athena.peer.overlay import read_status
from athena.vitals import VITALS_STALE_S, VitalsView
from athena.vitals.wire import clean_view

if TYPE_CHECKING:
    from athena.peer.listener import PeerHost

__all__ = ["HELLO_TIMEOUT_S", "PRESENCE_EVERY_S", "PresenceProbe", "authorized_hello", "overlay_online"]

PRESENCE_EVERY_S = 30.0
HELLO_TIMEOUT_S = 3.0
MAX_PARALLEL = 8

Presence = Literal["online", "asleep", "unreachable"]
HelloAnswer = tuple[int, Mapping[str, Any] | None]
Hello = Callable[[str, str], HelloAnswer]
OverlayOnline = Callable[[], frozenset[str] | None]


def authorized_hello(base_url: str, token: str) -> HelloAnswer:
    """``GET /peer/hello`` with this device's key for that peer: ``(status, body)``, the body only
    on ``200``. A ``401`` is kept apart from a timeout (status ``0``)."""
    answer = call(base_url, "GET", "/peer/hello", token=token, timeout=HELLO_TIMEOUT_S)
    return answer.status, (answer.body if answer.status == 200 else None)


def overlay_online() -> frozenset[str] | None:
    """The overlay addresses ``tailscale`` lists as online; ``None`` when there is nothing to ask."""
    status = read_status()
    if not status.installed:
        return None
    if not status.logged_in:
        return frozenset()
    return frozenset(peer.ip for peer in status.peers if peer.online and peer.ip)


class PresenceProbe:
    """One verdict per paired PC, refreshed every :attr:`every_s` while the host runs."""

    def __init__(
        self,
        host: PeerHost,
        *,
        hello: Hello = authorized_hello,
        overlay: OverlayOnline = overlay_online,
        every_s: float = PRESENCE_EVERY_S,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.host = host
        self.hello = hello
        self.overlay = overlay
        self.every_s = every_s
        self._now = now or host.now
        self._lock = threading.Lock()
        self._pass = threading.Lock()
        self._seen: dict[str, tuple[Presence, str]] = {}
        self._hellos: dict[str, HelloSeen] = {}
        self._unkeyed: set[str] = set()
        #: ``peer_id -> (its vitals off the last hello that answered, when that was)``.
        self._vitals: dict[str, tuple[VitalsView | None, datetime]] = {}
        #: This PC's own snapshot, for its hello and ``GET /devices`` (the vitals service sets it).
        self.own_vitals: Callable[[], VitalsView | None] = lambda: None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- what GET /devices shows ---------------------------------------------------------------

    def view(self, peer_id: str) -> dict[str, Any]:
        """``{presence, presence_at, link}`` for one peer; ``None`` before its first verdict."""
        with self._lock:
            seen = self._seen.get(peer_id)
        link = self.link(peer_id)
        vitals = self.vitals(peer_id)
        if seen is None:
            return {"presence": None, "presence_at": None, "vitals": vitals, "link": link}
        return {"presence": seen[0], "presence_at": seen[1], "vitals": vitals, "link": link}

    def own(self) -> VitalsView | None:
        """This PC's snapshot; a vitals service that raised says ``None``, never a 500."""
        try:
            return self.own_vitals()
        except Exception:
            return None

    def vitals(self, peer_id: str) -> VitalsView | None:
        """The peer's last vitals, or ``None``: never heard, or heard more than
        :data:`~athena.vitals.VITALS_STALE_S` ago. A phone says no hello, so it has none."""
        with self._lock:
            kept = self._vitals.get(peer_id)
        if kept is None or kept[0] is None:
            return None
        if (self._now() - kept[1]).total_seconds() > VITALS_STALE_S:
            return None
        return kept[0]

    def _keep_vitals(self, peer_id: str, vitals: VitalsView | None) -> bool:
        """Keep the vitals a hello carried; ``True`` when the peer's room or held reason moved
        (or it started or stopped sending any), which is what a ``peer.changed`` is worth."""
        with self._lock:
            before = self._vitals.get(peer_id)
            self._vitals[peer_id] = (vitals, self._now())
        old = before[0] if before is not None else None

        def said(view: VitalsView | None) -> tuple[Any, Any] | None:
            return None if view is None else (view["room"], view["held"])

        return said(old) != said(vitals)

    def link(self, peer_id: str) -> dict[str, Any] | None:
        """``{state, since, evidence}``, or ``None`` for a device with no row."""
        row = self.host.registry.get(peer_id)
        if row is None:
            return None
        with self._lock:
            hello = self._hellos.get(peer_id)
            unkeyed = peer_id in self._unkeyed
        keyed = row.kind == "pc" and not unkeyed and self.host.keys.url(peer_id) is not None
        from athena.peer.replicate import memory_view

        memory = memory_view(self.host, peer_id)
        return derive(row, keyed, hello, memory=memory, now=self._now(), every_s=self.every_s)

    # -- the loop ------------------------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="peer-presence", daemon=True)
        self._thread.start()

    def close(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def _run(self) -> None:
        from athena.peer.listener import log

        while not self._stop.is_set():
            try:
                self.probe_all()
            except Exception as exc:  # a pass's bug must not end the loop
                log(f"presence pass raised {type(exc).__name__}")
            if self._stop.wait(self.every_s):
                return

    # -- one pass ------------------------------------------------------------------------------

    def probe_all(self) -> list[str]:
        """Probe every probe-able peer once; publish and return the ids whose verdict changed."""
        with self._pass:
            rows = self.host.registry.rows()
            live = {row.peer_id for row in rows}
            with self._lock:  # a revoked or expired peer's verdict goes with its row
                self._seen = {k: v for k, v in self._seen.items() if k in live}
                self._hellos = {k: v for k, v in self._hellos.items() if k in live}
                self._vitals = {k: v for k, v in self._vitals.items() if k in live}
                self._unkeyed &= live
            targets: list[tuple[str, str, str]] = []
            for row in rows:
                if row.kind != "pc":
                    continue
                url = self.host.keys.url(row.peer_id)
                token = self.host.keys.token(row.peer_id) if url else None
                with self._lock:
                    if url and not token:
                        self._unkeyed.add(row.peer_id)
                    else:
                        self._unkeyed.discard(row.peer_id)
                if url and token:
                    targets.append((row.peer_id, url, token))
            if not targets:
                return []
            with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(targets))) as pool:
                answered = list(pool.map(lambda t: self._say_hello(t[1], t[2]), targets))
            online: frozenset[str] | None = None
            if any(status not in (200, 401) for status, _ in answered):
                online = self.overlay()
            changed: list[str] = []
            for (peer_id, url, _), (status, body) in zip(targets, answered, strict=True):
                verdict: Presence | None = "online"
                listed: bool | None = None
                if status == 401:
                    verdict = None  # it removed this device: not asleep, not unreachable
                elif status != 200:
                    address = urlsplit(url).hostname
                    if online is not None:
                        listed = address is not None and address in online
                    verdict = "asleep" if listed else "unreachable"
                moved = self._record(peer_id, verdict)
                moved = self._observe(peer_id, status, listed) or moved
                if body is not None:
                    moved = self._keep_vitals(peer_id, clean_view(body.get("vitals"))) or moved
                if moved:
                    changed.append(peer_id)
        for peer_id in changed:
            self.host.publish("peer.changed", peer_id=peer_id)
        return changed

    def _say_hello(self, url: str, token: str) -> HelloAnswer:
        try:
            return self.hello(url, token)
        except Exception:
            return 0, None

    def _observe(self, peer_id: str, status: int, listed: bool | None) -> bool:
        """Keep what the hello said; ``True`` when the link's state moved."""
        at = now_iso(self._now())
        with self._lock:
            before = self._hellos.get(peer_id)
            fresh = HelloSeen(status, at, at, listed)
            moved = before is None or state_of(before) != state_of(fresh)
            since = at if before is None or moved else before.since
            self._hellos[peer_id] = HelloSeen(status, since, at, listed)
        return moved

    def _record(self, peer_id: str, verdict: Presence | None) -> bool:
        with self._lock:
            before = self._seen.get(peer_id)
            if verdict is None:
                return self._seen.pop(peer_id, None) is not None
            if before is not None and before[0] == verdict:
                return False
            self._seen[peer_id] = (verdict, now_iso(self._now()))
            return True
