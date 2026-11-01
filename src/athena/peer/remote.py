"""The remote composer: another device's message runs as a turn on this daemon (ADR 0017).

A paired PC or a phone granted ``chat`` sends a message; this daemon runs it as an ordinary turn
against the core space (``space_id`` ``""``), through the same ``run_turn`` the window's ``/run``
uses, and buffers the turn's events for the device that asked. There is no window to wake and
nothing to tee: the daemon is the one that runs turns here.

The life of one remote message, by ``request_id`` (a ``job_`` id: a job one device hands another):

1. **Filed.** ``POST /peer/message {text}`` (grant ``chat``, at most :data:`MAX_TEXT_CHARS`)
   builds the engine as ``/run`` does, takes the turn's slot at once (so the refusals a turn can
   make - no engine, a busy project - answer now, as 503 and 409), files a :class:`RemoteTurn`
   and hands the rest of the turn to a worker thread. A peer with :data:`MAX_WAITING_PER_PEER`
   turns still running gets 429 ``busy``.
2. **Buffered.** Each event of the turn is stored as the peer's JSON (:func:`shape`): the same
   ``kind`` vocabulary the phone page reads (``turn.started``, ``text.delta``, ``tool.result``,
   ``decision.requested``, ``turn.finished``, ``turn.error``). At most :data:`MAX_EVENTS` are kept;
   the rest are counted.
3. **Closed**, when the turn ends: a last ``remote.closed {reason, showing, total, footer}`` frame.
   A turn that filed a card ends too, with ``waiting`` true: the card lives in the gate and is
   answered through ``/peer/decisions`` (or by the person here), so no continuation is waited for.
   A turn nothing has touched for :data:`TURN_TTL_S` is forgotten.

The asking device reads ``GET /peer/turns/<request_id>?from=<n>`` (grant ``chat``, and only the
peer that sent the message; any other is a 403): every event from index ``n``, each with its SSE
``id:``, then ``remote.closed``. A stream that carried nothing for :data:`STREAM_QUIET_S` ends with
``retry`` (every response ends) and the reader comes back with ``from`` set to the count it has.

**Approvals.** The cards are the gate's. ``GET /peer/decisions`` lists those waiting (grant
``approve``); ``POST /peer/decisions/<id> {choice}`` answers one through ``gate.resolve``, exactly
what the loopback ``/decisions/<id>`` does, so an approved card's executor runs in the daemon.

**The asking side.** Loopback ``POST /devices/<peer_id>/message`` forwards to that peer with the
key this device holds for it, and ``GET /devices/<peer_id>/turns/<request_id>`` relays that peer's
stream to the window as it is written. The relay is the one outbound connection here that is not
:func:`~athena.peer.client.call` (a turn's stream must not be read whole); it keeps ``call``'s
discipline: a fixed timeout, ``Connection: close``, a bounded read, nothing logged, an exception
reduced to its type.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from functools import partial
from http.client import HTTPConnection, HTTPResponse
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import quote, urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import BaseRoute, Route

from athena.clock import mint
from athena.errors import ApiError
from athena.peer.client import CALL_TIMEOUT_S, MAX_ANSWER_BYTES, call
from athena.peer.events import RETRY_MS, event_frame
from athena.peer.listener import EventStream, PeerRequest, PeerRoute, peer_error, peer_of

if TYPE_CHECKING:
    from athena.app import Daemon
    from athena.contracts import Card, Verdict
    from athena.peer.listener import PeerHost, Reply
    from athena.peer.registry import PeerRow

__all__ = [
    "CLOSED_KIND",
    "MAX_TEXT_CHARS",
    "STREAM_QUIET_S",
    "TURN_TTL_S",
    "RemoteTurn",
    "RemoteTurns",
    "loopback_routes",
    "peer_routes",
    "resume_index",
    "shape",
]

#: How long a turn is kept after its last event. Also how long a closed one stays readable.
TURN_TTL_S = 600.0
#: The longest message a peer may send. A longer one is refused, never cut.
MAX_TEXT_CHARS = 8000
#: How many remote turns may be held at once; past it a new message is refused (429).
MAX_TURNS = 32
#: How many turns one peer may have running (not yet closed) at once; past it, 429 ``busy``.
MAX_WAITING_PER_PEER = 4
#: How many events one turn's buffer keeps. Past it the rest are counted, not kept.
MAX_EVENTS = 2000
#: A turn stream that carries nothing for this long ends, and its reader comes back with ``from``.
STREAM_QUIET_S = 15.0
#: The relay's socket patience: past the peer's quiet window, so only a dead peer trips it.
RELAY_TIMEOUT_S = STREAM_QUIET_S + 10.0
#: The last frame of a closed turn's stream.
CLOSED_KIND = "remote.closed"
#: The core space: a remote message is Athena's own conversation, not a project's.
CORE = ""

_REQUEST_ID = re.compile(r"^job_[0-9a-f]{12}$")
NO_KEY = "this computer holds no key for that device"


def is_request_id(value: str) -> bool:
    return bool(_REQUEST_ID.match(value))


def shape(event: Mapping[str, Any]) -> dict[str, Any] | None:
    """One event of the daemon's turn stream as the peer wire's JSON, or ``None`` to drop it."""
    kind = event.get("type")
    if kind == "start":
        return {
            "kind": "turn.started",
            "turn_id": event.get("turn_id"),
            "engine": event.get("engine"),
            "simulated": bool(event.get("simulated")),
        }
    if kind == "text":
        return {"kind": "text.delta", "text": str(event.get("delta", ""))}
    if kind == "tool":
        return {"kind": "tool.result", "name": event.get("name"), "label": event.get("label", ""), "ok": True}
    if kind == "card":
        card = cast("Mapping[str, Any]", event.get("card") or {})
        return {
            "kind": "decision.requested",
            "id": card.get("id"),
            "action": card.get("action"),
            "label": card.get("label", ""),
        }
    if kind == "done":
        return {
            "kind": "turn.finished",
            "turn_id": event.get("turn_id"),
            "waiting": bool(event.get("waiting")),
            "text": "",
        }
    if kind == "error":
        return {"kind": "turn.error", "reason": event.get("error"), "detail": event.get("reason", "")}
    return None


# --- the turns -----------------------------------------------------------------------------------


@dataclass
class RemoteTurn:
    """One message another device sent, and everything its turn has streamed so far."""

    request_id: str
    peer_id: str
    peer_name: str
    touched: float
    events: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    closed: dict[str, Any] | None = None


class TooMany(Exception):
    """:data:`MAX_TURNS` remote turns are already held."""


class PeerBusy(Exception):
    """The peer already has :data:`MAX_WAITING_PER_PEER` turns running."""


class RemoteTurns:
    """The remote turns this daemon holds, in memory: running, closed, expired."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        ttl_s: float = TURN_TTL_S,
        quiet_s: float = STREAM_QUIET_S,
    ) -> None:
        self._clock = clock
        self.ttl_s = ttl_s
        self.quiet_s = quiet_s
        self._cond = threading.Condition()
        self._turns: dict[str, RemoteTurn] = {}

    def file(self, peer: PeerRow) -> RemoteTurn:
        with self._cond:
            self._sweep()
            if len(self._turns) >= MAX_TURNS:
                raise TooMany
            running = sum(1 for t in self._turns.values() if t.peer_id == peer.peer_id and t.closed is None)
            if running >= MAX_WAITING_PER_PEER:
                raise PeerBusy
            turn = RemoteTurn(
                request_id=mint("job_"), peer_id=peer.peer_id, peer_name=peer.name, touched=self._clock()
            )
            self._turns[turn.request_id] = turn
            return turn

    def drop(self, turn: RemoteTurn) -> None:
        with self._cond:
            self._turns.pop(turn.request_id, None)

    def get(self, request_id: str) -> RemoteTurn | None:
        with self._cond:
            self._sweep()
            return self._turns.get(request_id)

    def append(self, turn: RemoteTurn, payload: dict[str, Any]) -> None:
        with self._cond:
            if turn.closed is not None:
                return
            turn.total += 1
            turn.touched = self._clock()
            if len(turn.events) < MAX_EVENTS:
                turn.events.append(payload)
            self._cond.notify_all()

    def close(self, turn: RemoteTurn, why: str) -> None:
        with self._cond:
            if turn.closed is not None:
                return
            shown, total = len(turn.events), turn.total
            turn.touched = self._clock()
            turn.closed = {
                "kind": CLOSED_KIND,
                "request_id": turn.request_id,
                "reason": why,
                "showing": shown,
                "total": total,
                "footer": "" if shown >= total else f"(showing {shown} of {total})",
            }
            self._cond.notify_all()

    def _sweep(self) -> None:
        """Forget every turn quiet for :attr:`ttl_s`. Called with the condition held."""
        now = self._clock()
        for request_id in [r for r, t in self._turns.items() if now - t.touched >= self.ttl_s]:
            turn = self._turns.pop(request_id)
            if turn.closed is None:
                self.close(turn, "expired")

    def frames(self, turn: RemoteTurn, start: int = 0) -> Iterator[str]:
        """The asker's stream: events from ``start``, then ``remote.closed``, or end on quiet."""
        yield f": athena turn\nretry: {RETRY_MS}\n\n"
        index = max(0, start)
        while True:
            with self._cond:
                self._cond.wait_for(partial(_moved, turn, index), timeout=self.quiet_s)
                batch = turn.events[index:]
                closed = turn.closed
            if not batch and closed is None:
                return
            for offset, payload in enumerate(batch):
                yield f"id: {index + offset}\n{event_frame(payload)}"
            index += len(batch)
            if closed is not None:
                yield event_frame(closed)
                return


def _moved(turn: RemoteTurn, index: int) -> bool:
    return index < len(turn.events) or turn.closed is not None


def resume_index(query: Mapping[str, str]) -> int:
    """``?from=<n>`` as the index a turn stream resumes at: ASCII digits, else ``0``."""
    start = query.get("from", "0")
    return int(start) if start.isascii() and start.isdigit() else 0


# --- running the turn ----------------------------------------------------------------------------


def _engine(daemon: Daemon) -> Any:
    from athena import engine as engine_mod
    from athena import routes_turn
    from athena.engine import EngineError
    from athena.keys import KeyStore

    try:
        return engine_mod.build_engine(
            KeyStore(daemon.data_dir), stored=daemon.settings.engine_choice(), transport=routes_turn.TRANSPORT
        )
    except EngineError as exc:
        raise ApiError("engine_unavailable", exc.reason) from exc


def _drain(
    turns: RemoteTurns, turn: RemoteTurn, first: dict[str, Any], rest: Iterator[dict[str, Any]]
) -> None:
    """Worker thread: copy the daemon's turn into the buffer, then close it."""
    why = "finished"
    reply: list[str] = []
    try:
        for event in _chain(first, rest):
            payload = shape(event)
            if payload is None:
                continue
            if payload["kind"] == "text.delta":
                reply.append(payload["text"])
            elif payload["kind"] == "turn.finished":
                payload["text"] = "".join(reply).strip()
            elif payload["kind"] == "turn.error":
                why = "error"
            turns.append(turn, payload)
    except Exception as exc:  # a turn's bug is a closed turn with its type, never a lost thread
        why = "error"
        turns.append(turn, {"kind": "turn.error", "reason": "unknown", "detail": type(exc).__name__})
    finally:
        close = getattr(rest, "close", None)
        if callable(close):
            with suppress(Exception):
                close()
        turns.close(turn, why)


def _chain(first: dict[str, Any], rest: Iterator[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    yield first
    yield from rest


def _refused(exc: ApiError) -> Reply:
    word = {"space_busy": "busy", "engine_unavailable": "engine_unavailable"}.get(exc.error, exc.error)
    return peer_error(exc.status, word, exc.reason)


# --- the peer routes -----------------------------------------------------------------------------


def peer_message(host: PeerHost, daemon: Daemon, turns: RemoteTurns, request: PeerRequest) -> Reply:
    from athena.turn import run_turn

    row = peer_of(request)
    text = request.body.get("text")
    if not isinstance(text, str) or not text.strip():
        return peer_error(400, "bad_request", "text is required")
    if len(text) > MAX_TEXT_CHARS:
        return peer_error(400, "bad_request", f"text is longer than {MAX_TEXT_CHARS} characters")
    try:
        turn = turns.file(row)
    except TooMany:
        return peer_error(429, "busy", f"{MAX_TURNS} messages are already held here")
    except PeerBusy:
        return peer_error(429, "busy", "Athena is still answering your earlier messages")
    try:
        events = run_turn(daemon, _engine(daemon), text, CORE)
        first = next(events)  # takes the turn's slot now, so a refusal answers now
    except ApiError as exc:
        turns.drop(turn)
        return _refused(exc)
    except StopIteration:
        turns.drop(turn)
        return peer_error(502, "unknown", "the turn produced nothing")
    threading.Thread(
        target=_drain, args=(turns, turn, first, events), name="peer-remote", daemon=True
    ).start()
    return 200, {"ok": True, "request_id": turn.request_id, "name": host.identity.identity.name}


def peer_turn(turns: RemoteTurns, request: PeerRequest) -> Reply | EventStream:
    row = peer_of(request)
    request_id = request.path[len("/peer/turns/") :]
    turn = turns.get(request_id) if is_request_id(request_id) else None
    if turn is None:
        return peer_error(404, "not_found", "no such message, or it expired")
    if turn.peer_id != row.peer_id:
        # A turn's stream is the asker's alone; another paired device learns nothing of it.
        return peer_error(403, "not_sender", "only the device that sent this message reads it")
    return EventStream(turns.frames(turn, resume_index(request.query)))


def card_view(card: Card) -> dict[str, Any]:
    """A waiting card as the phone draws it: what, why (the gate's label), and the details."""
    return {
        "id": card["id"],
        "action": card["action"],
        "rationale": card["label"],
        "params": card["args"],
        "created": card["created"],
    }


def peer_decisions(daemon: Daemon) -> Reply:
    return 200, {"ok": True, "pending": [card_view(c) for c in daemon.gate.list("waiting")]}


def peer_decide(daemon: Daemon, request: PeerRequest) -> Reply:
    from athena.twins import missions

    approval_id = request.path[len("/peer/decisions/") :]
    choice = request.body.get("choice")
    if choice not in ("approve", "decline"):
        return peer_error(400, "bad_request", "choice must be approve or decline")
    try:
        card = daemon.gate.resolve(approval_id, cast("Verdict", choice))
        if card["state"] == "declined" and card["action"] in missions.TWIN_ACTIONS:
            missions.declined(daemon, card)
    except ApiError as exc:
        if exc.error == "bad_request" and "already" in exc.reason:
            return peer_error(409, "already_decided", exc.reason)
        return peer_error(exc.status, exc.error, exc.reason)
    return 200, {"ok": True, "id": card["id"], "state": card["state"], "outcome": card.get("outcome", "")}


def peer_routes(host: PeerHost, daemon: Daemon, turns: RemoteTurns) -> list[PeerRoute]:
    return [
        PeerRoute("POST", "/peer/message", lambda r: peer_message(host, daemon, turns, r), grant="chat"),
        PeerRoute("GET", "/peer/turns/", lambda r: peer_turn(turns, r), grant="chat", prefix=True),
        PeerRoute("GET", "/peer/decisions", lambda r: peer_decisions(daemon), grant="approve"),
        PeerRoute("POST", "/peer/decisions/", lambda r: peer_decide(daemon, r), grant="approve", prefix=True),
    ]


# --- the loopback routes: the asking side --------------------------------------------------------


def _reply(answer: Reply) -> Response:
    return JSONResponse(answer[1], status_code=answer[0])


def _keyed(host: PeerHost, peer_id: str) -> tuple[str, str] | None:
    """Where ``peer_id`` listens and the token this device calls it with, or ``None``."""
    url, token = host.keys.url(peer_id), host.keys.token(peer_id)
    return None if url is None or token is None else (url, token)


def send_message(host: PeerHost, body: dict[str, Any] | None, peer_id: str) -> Reply:
    text = (body or {}).get("text")
    if not isinstance(text, str) or not text.strip():
        return peer_error(400, "bad_request", "text is required")
    if len(text) > MAX_TEXT_CHARS:
        return peer_error(400, "bad_request", f"text is longer than {MAX_TEXT_CHARS} characters")
    keyed = _keyed(host, peer_id)
    if keyed is None:
        return peer_error(404, "unknown_ref", NO_KEY)
    url, token = keyed
    answer = call(url, "POST", "/peer/message", {"text": text}, token=token, timeout=2 * CALL_TIMEOUT_S)
    if not answer.reached:
        return peer_error(502, "peer_unreachable", "that device did not answer")
    if answer.status != 200:
        word = str(answer.body.get("error") or "unknown")
        return peer_error(answer.status, word, str(answer.body.get("detail") or ""))
    request_id = answer.body.get("request_id")
    if not isinstance(request_id, str) or not is_request_id(request_id):
        return peer_error(502, "peer_unreachable", "that device answered without a request id")
    return 200, {"ok": True, "request_id": request_id, "peer_id": peer_id}


def relay_turn(
    host: PeerHost, query: Mapping[str, str], peer_id: str, request_id: str
) -> Reply | Iterator[str]:
    keyed = _keyed(host, peer_id)
    if keyed is None:
        return peer_error(404, "unknown_ref", NO_KEY)
    if not is_request_id(request_id):
        return peer_error(400, "bad_request", "not a message id")
    url, token = keyed
    path = f"/peer/turns/{quote(request_id)}?from={resume_index(query)}"
    parts = urlsplit(url)
    connection = HTTPConnection(parts.hostname or "", parts.port or 80, timeout=RELAY_TIMEOUT_S)
    try:
        connection.request("GET", path, headers={"Authorization": f"Bearer {token}", "Connection": "close"})
        reply = connection.getresponse()
    except (OSError, ValueError):
        connection.close()
        return peer_error(502, "peer_unreachable", "that device did not answer")
    if reply.status != 200:
        try:
            decoded = json.loads(reply.read(MAX_ANSWER_BYTES) or b"{}")
        except (OSError, ValueError):
            decoded = {}
        finally:
            connection.close()
        body = decoded if isinstance(decoded, dict) else {}
        return peer_error(reply.status, str(body.get("error") or "unknown"), str(body.get("detail") or ""))
    return _relayed(connection, reply)


def _relayed(connection: HTTPConnection, reply: HTTPResponse) -> Iterator[str]:
    """The peer's frames as they arrive, a frame at a time, until it ends or goes quiet."""
    frame: list[str] = []
    read = 0
    try:
        while True:
            try:
                line = reply.readline(MAX_ANSWER_BYTES)
            except (OSError, ValueError):
                return
            if not line:
                return
            read += len(line)
            if read > 64 * MAX_ANSWER_BYTES:
                return
            text = line.decode("utf-8", errors="replace")
            frame.append(text)
            if text in ("\n", "\r\n"):
                yield "".join(frame)
                frame = []
    finally:
        with suppress(Exception):
            connection.close()


def loopback_routes(host: PeerHost) -> list[BaseRoute]:
    async def post_message(request: Request) -> Response:
        try:
            body = await request.json()
        except ValueError:
            body = None
        sent = await asyncio.to_thread(
            send_message, host, body if isinstance(body, dict) else None, request.path_params["peer_id"]
        )
        return _reply(sent)

    async def get_turn(request: Request) -> Response:
        answer = await asyncio.to_thread(
            relay_turn,
            host,
            dict(request.query_params),
            request.path_params["peer_id"],
            request.path_params["request_id"],
        )
        if isinstance(answer, tuple):
            return _reply(answer)
        return StreamingResponse(
            answer,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return [
        Route("/devices/{peer_id}/message", post_message, methods=["POST"]),
        Route("/devices/{peer_id}/turns/{request_id}", get_turn, methods=["GET"]),
    ]
