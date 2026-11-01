"""Write-once memory replication between paired PCs (ADR 0017, "Memory replication").

Every device is a full Athena with its own memory, and what one of them remembers the others come
to remember. Only what cannot go stale travels: an **episode** or a **fact** is written once (no
rewrite path exists for either), so a copy is either here byte for byte or not here yet. And only
the **core** space travels, because a project's space id is minted per device: the same id on two
machines names two different projects.

**Serving** (grant ``memory``, :func:`peer_routes`):

``GET /peer/brain/manifest?since=<iso>&after=<id>``
    ``{items: [{id, kind, created, sha256}], next, next_after, truncated}``, oldest first, at most
    :data:`MANIFEST_PAGE` items, ordered by ``(created, id)``. ``next`` (with ``next_after``, the
    last id) is where the next page starts, or ``null`` at the end. ``since`` is inclusive and
    ``after`` breaks a tie on one stamp, so a page that is all one instant still moves on.
``GET /peer/brain/file?id=<id>``
    ``{id, kind, created, text}`` or ``404 not_found`` - for anything that is not a core episode or
    fact, a project's memory included.

**Pulling** (:class:`Puller`). A peer is pulled when *this* device granted it ``memory`` and holds a
sealed key for it. A ``403`` from the peer is recorded as ``not_shared``, a ``401`` (it no longer
knows this device's token) as ``removed_there``, silence as ``unreachable``. A pass reads the
manifest from the cursor and files each new row through :meth:`athena.memory.Memory.receive`:

- same id, same sha256 of the text: skipped;
- same id, different sha: the local row stays and the remote copy is kept at
  ``<data>/peer/conflicts/<id>.<peer_id>.json`` for a person, counted, and logged by id only;
- new: filed under the sender's id and stamp, through the store's own insert (FTS stays honest).

**The cursor** (``<data>/peer/cursors.json``, ``{peer_id: iso}``) is the newest ``created`` a pass
saw, held back to the oldest item it could not finish, minus :data:`SKEW` (ten minutes, two PCs'
clocks disagree). Re-reading that margin costs nothing: an id already here is skipped.

**When.** A thread subscribed to the host's bus pulls at start, on every ``peer.changed``, and every
:data:`PULL_EVERY_S`; it is started by ``host.on_start`` and stopped by ``host.on_close``. Passes
never overlap and read at most :data:`MAX_PAGES` pages of :data:`MANIFEST_PAGE` per peer.
:func:`memory_view` is the status ``GET /devices`` shows under ``memory``.

Nothing here logs a token, a body, a URL or a memory's text.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from athena.memory import REPLICATED_KINDS, Memory, memory_sha
from athena.peer.client import CALL_TIMEOUT_S, call
from athena.peer.identity import now_iso, write_whole
from athena.peer.listener import PeerRequest, PeerRoute, log, peer_error

if TYPE_CHECKING:
    from pathlib import Path

    from athena.peer.listener import PeerHost, Reply

__all__ = [
    "CONFLICTS_DIRNAME",
    "CURSORS_FILENAME",
    "MANIFEST_PAGE",
    "MAX_PAGES",
    "PULL_EVERY_S",
    "SKEW",
    "PassResult",
    "Puller",
    "manifest",
    "memory_view",
    "peer_routes",
]

CURSORS_FILENAME = "cursors.json"
CONFLICTS_DIRNAME = "conflicts"
MANIFEST_PAGE = 500
MAX_PAGES = 40
PULL_EVERY_S = 60.0
#: How far behind the newest stamp seen the cursor is kept (clock skew between devices).
SKEW = timedelta(minutes=10)
_PEER_ID_CHARS = frozenset("0123456789abcdef")


def _instant(stamp: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _stamp(instant: datetime) -> str:
    """The shape this daemon stamps memories in (``clock.now_iso``), so stamps compare as text."""
    return instant.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_mem_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 16
        and value.startswith("mem_")
        and all(c in _PEER_ID_CHARS for c in value[4:])
    )


# --- serving -------------------------------------------------------------------------------------


def manifest(
    memory: Memory, since: str | None, after: str | None = None, *, limit: int | None = None
) -> dict[str, Any]:
    """One page of this device's core episodes and facts from ``since`` (inclusive), oldest first."""
    limit = limit or MANIFEST_PAGE
    rows = memory.replicable_page(since, after, limit + 1)
    truncated = len(rows) > limit
    page = rows[:limit]
    last = page[-1] if truncated and page else None
    return {
        "ok": True,
        "items": [
            {"id": r["id"], "kind": r["kind"], "created": r["created"], "sha256": memory_sha(r["text"])}
            for r in page
        ],
        "next": last["created"] if last is not None else None,
        "next_after": last["id"] if last is not None else None,
        "truncated": truncated,
    }


def manifest_route(memory: Memory, request: PeerRequest) -> Reply:
    since = request.query.get("since")
    after = request.query.get("after")
    if since is not None:
        instant = _instant(since)
        if instant is None:
            return peer_error(400, "bad_request", "since must be an ISO 8601 stamp")
        since = _stamp(instant)
    if after is not None and (since is None or not _is_mem_id(after)):
        return peer_error(400, "bad_request", "after is a memory id, and needs since")
    return 200, manifest(memory, since, after)


def file_route(memory: Memory, request: PeerRequest) -> Reply:
    row = memory.replicable(request.query.get("id") or "")
    if row is None:
        return peer_error(404, "not_found", "no such memory here")
    return 200, {"ok": True, **row}


def peer_routes(host: PeerHost, memory: Memory) -> list[PeerRoute]:
    """The two serving routes (grant ``memory``); this host's :class:`Puller` starts and stops with it."""
    puller = Puller(host, memory)
    host.on_start.append(puller.start)
    host.on_close.append(puller.close)
    return [
        PeerRoute("GET", "/peer/brain/manifest", lambda r: manifest_route(memory, r), grant="memory"),
        PeerRoute("GET", "/peer/brain/file", lambda r: file_route(memory, r), grant="memory"),
    ]


# --- pulling -------------------------------------------------------------------------------------


@dataclass
class PassResult:
    """What one pass against one peer did."""

    state: str
    pulled: int = 0
    skipped: int = 0
    conflicts: int = 0
    deferred: int = 0
    refused: int = 0
    failed: int = 0


@dataclass
class _Status:
    last_pull_at: str
    state: str
    pulled: int = 0
    deferred: int = 0

    def view(self, conflicts: int) -> dict[str, Any]:
        return {
            "last_pull_at": self.last_pull_at,
            "pulled": self.pulled,
            "conflicts": conflicts,
            "deferred": self.deferred,
            "state": self.state,
        }


@dataclass(frozen=True)
class _Item:
    id: str
    kind: str
    created: str
    sha256: str

    @staticmethod
    def parse(data: Any) -> _Item | None:
        """A manifest item from a peer, or ``None``: every field checked."""
        if not isinstance(data, dict):
            return None
        node_id, kind, created, digest = (data.get(k) for k in ("id", "kind", "created", "sha256"))
        if not (isinstance(kind, str) and isinstance(created, str) and isinstance(digest, str)):
            return None
        if not _is_mem_id(node_id) or kind not in REPLICATED_KINDS or _instant(created) is None:
            return None
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            return None
        return _Item(str(node_id), kind, created, digest)


@dataclass
class _Pass:
    result: PassResult
    newest: datetime | None = None
    #: The oldest item this pass could not finish: the cursor may not move past it.
    held: datetime | None = None
    items: dict[str, _Item] = field(default_factory=dict)

    def saw(self, item: _Item) -> None:
        instant = _instant(item.created)
        if instant is not None and (self.newest is None or instant > self.newest):
            self.newest = instant

    def hold(self, item: _Item) -> None:
        instant = _instant(item.created)
        if instant is not None and (self.held is None or instant < self.held):
            self.held = instant


_PULLERS: weakref.WeakKeyDictionary[PeerHost, Puller] = weakref.WeakKeyDictionary()


def memory_view(host: PeerHost, peer_id: str) -> dict[str, Any] | None:
    """The replication status ``GET /devices`` shows for one peer, ``None`` if never pulled."""
    puller = _PULLERS.get(host)
    return None if puller is None else puller.view(peer_id)


class Puller:
    """Pulls every peer this device shares memory with, into one memory, one pass at a time."""

    def __init__(
        self,
        host: PeerHost,
        memory: Memory,
        *,
        every_s: float = PULL_EVERY_S,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.host = host
        self.memory = memory
        self.every_s = every_s
        self._now = now or host.now
        self.cursors_path: Path = host.root / CURSORS_FILENAME
        self.conflicts_dir: Path = host.root / CONFLICTS_DIRNAME
        self._lock = threading.Lock()
        self._pass = threading.Lock()
        self._status: dict[str, _Status] = {}
        self._cursors = self._load_cursors()
        self._thread: threading.Thread | None = None
        self._inbox: queue.Queue[dict[str, Any]] | None = None
        self._again = False
        self._closed = threading.Event()
        _PULLERS[host] = self

    # -- the loop ------------------------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        inbox = self._inbox = self.host.bus.subscribe()
        self._thread = threading.Thread(target=self._run, args=(inbox,), name="peer-replicate", daemon=True)
        self._thread.start()

    def close(self, timeout: float = 10.0) -> None:
        """Stop after the item in hand, and wait for it."""
        self._closed.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def _run(self, inbox: queue.Queue[dict[str, Any]]) -> None:
        due = 0.0
        try:
            while not self._closed.is_set():
                try:
                    wait = max(0.0, min(due - time.monotonic(), 1.0))
                    payload: dict[str, Any] | None = inbox.get(timeout=wait)
                except queue.Empty:
                    payload = None
                kind = None if payload is None else payload.get("kind")
                if kind == "__closed__":
                    return
                if payload is None and time.monotonic() < due:
                    continue  # woke to look at the stop flag, not because a pass is due
                if payload is not None and kind != "peer.changed":
                    continue
                self._again = False
                try:
                    self.pull_all()
                except Exception as exc:  # a pass's bug must not end the loop
                    log(f"replication pass raised {type(exc).__name__}")
                # A ``peer.changed`` heard during the pass is a reason to go again now.
                due = 0.0 if self._again else time.monotonic() + self.every_s
        finally:
            self._closed.set()
            self.host.bus.unsubscribe(inbox)

    def _stopping(self) -> bool:
        """Has the host closed? Read off the inbox between items, without waiting."""
        inbox = self._inbox
        while inbox is not None and not self._closed.is_set():
            try:
                payload = inbox.get_nowait()
            except queue.Empty:
                break
            if payload.get("kind") == "__closed__":
                self._closed.set()
            elif payload.get("kind") == "peer.changed":
                self._again = True
        return self._closed.is_set()

    # -- passes --------------------------------------------------------------------------------

    def candidates(self) -> list[tuple[str, str, str]]:
        """``(peer_id, url, token)`` for every PC this device granted ``memory`` and can call."""
        out: list[tuple[str, str, str]] = []
        for row in self.host.registry.rows():
            if row.kind != "pc" or "memory" not in row.grants:
                continue
            url = self.host.keys.url(row.peer_id)
            token = self.host.keys.token(row.peer_id) if url else None
            if url and token:
                out.append((row.peer_id, url, token))
        return out

    def pull_all(self) -> dict[str, PassResult]:
        done: dict[str, PassResult] = {}
        for peer_id, url, token in self.candidates():
            if self._stopping():
                break
            done[peer_id] = self.pull(peer_id, url, token)
        return done

    def pull(self, peer_id: str, url: str, token: str) -> PassResult:
        """One pass against one peer: manifest from the cursor, then each new row."""
        with self._pass:
            work = _Pass(PassResult("ok"))
            state = self._read_manifest(work, url, token, self.cursor(peer_id))
            if state != "ok":
                return self._finish(peer_id, work, state)
            for item in sorted(work.items.values(), key=lambda i: (i.created, i.id)):
                if self._stopping():
                    work.hold(item)
                    continue
                self._apply(peer_id, url, token, item, work)
            return self._finish(peer_id, work, "ok")

    def _read_manifest(self, work: _Pass, url: str, token: str, since: str | None) -> str:
        after: str | None = None
        for _ in range(MAX_PAGES):
            query = "" if since is None else f"?since={quote(since)}"
            if after is not None:
                query += f"&after={quote(after)}"
            answer = call(url, "GET", f"/peer/brain/manifest{query}", token=token, timeout=CALL_TIMEOUT_S)
            if answer.status == 401:
                return "removed_there"
            if answer.status == 403:
                return "not_shared"
            if answer.status != 200:
                return "unreachable"
            raw = answer.body.get("items")
            for entry in raw if isinstance(raw, list) else []:
                item = _Item.parse(entry)
                if item is None:
                    work.result.refused += 1
                    continue
                work.items.setdefault(item.id, item)
                work.saw(item)
            nxt, nxt_after = answer.body.get("next"), answer.body.get("next_after")
            if not isinstance(nxt, str) or not isinstance(nxt_after, str):
                return "ok"
            since, after = nxt, nxt_after
        # More pages than one pass reads: the cursor stops at the last stamp seen; the next pass
        # carries on from there.
        return "ok"

    def _fetch(self, url: str, token: str, item: _Item) -> dict[str, Any] | None:
        """The row a peer serves for ``item``, if it is the row the manifest described."""
        answer = call(url, "GET", f"/peer/brain/file?id={quote(item.id)}", token=token)
        body = answer.body
        text = body.get("text")
        if answer.status != 200 or not isinstance(text, str) or memory_sha(text) != item.sha256:
            return None
        if body.get("id") != item.id or body.get("kind") != item.kind or body.get("created") != item.created:
            return None
        return {"id": item.id, "kind": item.kind, "text": text, "created": item.created}

    def _apply(self, peer_id: str, url: str, token: str, item: _Item, work: _Pass) -> None:
        result = work.result
        local = self.memory.replicable(item.id)
        if local is not None and memory_sha(local["text"]) == item.sha256:
            result.skipped += 1
            return
        row = self._fetch(url, token, item)
        if row is None:
            # Unreached, gone since the manifest, or not what it described: try again later.
            result.failed += 1
            work.hold(item)
            return
        try:
            filed = self.memory.receive(row)
        except ValueError:
            result.refused += 1
            log(f"replication refused {item.id} from {peer_id}")
            return
        if filed == "added":
            result.pulled += 1
        elif filed == "same":
            result.skipped += 1
        else:
            self._conflict(peer_id, row, work)

    def _conflict(self, peer_id: str, row: dict[str, Any], work: _Pass) -> None:
        """Keep the local row; keep the remote copy beside the store for a person."""
        target = self.conflicts_dir / f"{row['id']}.{peer_id}.json"
        if target.exists():
            return  # already filed, already counted
        write_whole(target, row)
        work.result.conflicts += 1
        log(f"replication conflict on {row['id']} from {peer_id}: kept the local copy")

    def _finish(self, peer_id: str, work: _Pass, state: str) -> PassResult:
        result = work.result
        result.state = state
        if state == "ok":
            moved = work.newest
            if work.held is not None and (moved is None or work.held < moved):
                moved = work.held
            if moved is not None:
                self._set_cursor(peer_id, _stamp(moved - SKEW))
        with self._lock:
            status = self._status.get(peer_id)
            if status is None:
                status = self._status[peer_id] = _Status(now_iso(self._now()), state)
            status.last_pull_at = now_iso(self._now())
            status.state = state
            status.pulled += result.pulled
            if state == "ok":
                status.deferred = result.deferred
        if state == "removed_there":
            self.host.publish("peer.changed", peer_id=peer_id)
        return result

    # -- status --------------------------------------------------------------------------------

    def view(self, peer_id: str) -> dict[str, Any] | None:
        with self._lock:
            status = self._status.get(peer_id)
        return None if status is None else status.view(self.conflict_count(peer_id))

    def conflict_count(self, peer_id: str) -> int:
        """Conflicts filed from ``peer_id``, counted on disk: the files are the record."""
        if not self.conflicts_dir.is_dir():
            return 0
        return sum(1 for _ in self.conflicts_dir.glob(f"*.{peer_id}.json"))

    # -- the cursor file -----------------------------------------------------------------------

    def cursor(self, peer_id: str) -> str | None:
        with self._lock:
            return self._cursors.get(peer_id)

    def _set_cursor(self, peer_id: str, stamp: str) -> None:
        with self._lock:
            if self._cursors.get(peer_id) == stamp:
                return
            self._cursors[peer_id] = stamp
            write_whole(self.cursors_path, self._cursors)

    def _load_cursors(self) -> dict[str, str]:
        try:
            data = json.loads(self.cursors_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        # An unreadable stamp is dropped: that peer is read from the start again, which dedupe by
        # id makes harmless.
        return {str(k): str(v) for k, v in data.items() if isinstance(v, str) and _instant(v) is not None}
