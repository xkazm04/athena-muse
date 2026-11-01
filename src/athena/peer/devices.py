"""The loopback ``/devices`` routes: the window's view of pairing and its one mint door (ADR 0017).

These are routes on the loopback daemon, behind its bearer token like every other route there. The
person in this device's own window is the only one who reaches them, which is what makes
``POST /devices/pending/<pairing_id>`` the one door a peer token is minted through.

Every refusal is ``{ok: false, error, reason, detail}``: ``error`` is the word a program acts on,
``reason`` (and ``detail``) the plain sentence a person is shown.

``GET /devices``
    ``{self: {device_id, name, vitals}, peers: [row without its fingerprint, plus ``memory``
    (``{last_pull_at, pulled, conflicts, deferred, state}``, ``null`` until the first pull),
    ``presence`` (``online`` / ``asleep`` / ``unreachable``) with
    ``presence_at``, ``vitals`` (the peer's room off its last hello, ``null`` when stale) and
    ``link`` ``{state, since, evidence}``],
    pending: [{pairing_id, name, kind, requested_grants, expires_at, pair_back, address,
    replaces}], beacon: {on, url}, overlay: {state}, listener: {up, address, port, error},
    joining: [{join_id, address, name, state, expires_at}]}``. Absent values are ``null``.
``PUT /devices/self`` ``{name}``
    Rename this device.
``POST /devices/pairing`` ``{kind}``
    Open a window: ``{pairing_id, code, url, expires_at}``. ``url`` is
    ``http://<overlay-ip>:<peer-port>/m/#claim=<pairing_id>.<nonce>`` for a phone's QR, or
    ``null`` while the listener cannot bind (no overlay).
``POST /devices/pending/<pairing_id>`` ``{choice, grants, expires_days}``
    ``approve`` (grants may only narrow what was asked; absent means as asked) or ``decline``.
``DELETE /devices/<peer_id>``
    Revoke, at once, with no confirmation: the next request with that peer's token is a 401.
``PUT /devices/beacon`` ``{on}``
    Keep the listener up for a phone page; ``url`` is ``http://<overlay-ip>:<peer-port>/m/``.
``POST /devices/join`` ``{address, port, code, requested_grants}``
    This PC asks the PC at ``address`` (an overlay address) to let it in, with the code that PC's
    person read out; the tick then polls the claim and files the pair-back request here.
``GET /devices/overlay``
    The other devices on the private network, to pick the join form's address from.
``GET /devices/events``
    Server-Sent Events (``?token=`` since ``EventSource`` sends no headers): ``pair.requested``,
    ``peer.changed``, ``pair.opened``. A stream quiet for 15 s ends with ``retry: 1000``.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import BaseRoute, Route

from athena.peer.listener import DEFAULT_PEER_PORT, PeerHost, Reply, peer_error
from athena.peer.overlay import overlay_peers
from athena.peer.pairing import PairingRefused
from athena.peer.registry import GRANTS, KINDS, PeerRow
from athena.peer.replicate import memory_view

__all__ = ["EVENTS_PATH", "routes"]

EVENTS_PATH = "/devices/events"
#: The longest an approval may be given for. ``null`` is "until revoked".
MAX_EXPIRES_DAYS = 3650


def _reply(answer: Reply) -> Response:
    return JSONResponse(answer[1], status_code=answer[0])


def _bad(detail: str) -> Response:
    return _reply(peer_error(400, "bad_request", detail))


async def _body(request: Request) -> dict[str, Any] | None:
    try:
        data = await request.json()
    except ValueError:
        return None
    return cast("dict[str, Any]", data) if isinstance(data, dict) else None


def devices(host: PeerHost) -> Reply:
    me = host.identity.identity
    bound = host.bound
    base = host.base_url()
    return 200, {
        "ok": True,
        "self": {"device_id": me.device_id, "name": me.name, "vitals": host.presence.own()},
        "peers": [_peer(host, row) for row in host.registry.rows()],
        "pending": [host.pending_view(record) for record in host.pairings.pending()],
        "beacon": {"on": host.beacon, "url": f"{base}/m/" if host.beacon and base else None},
        "overlay": {"state": host.overlay().state},
        "listener": {
            "up": bound is not None,
            "address": bound[0] if bound else None,
            "port": bound[1] if bound else host.port,
            "error": host.bind_error,
        },
        "joining": host.join_views(),
    }


def _peer(host: PeerHost, row: PeerRow) -> dict[str, Any]:
    memory = memory_view(host, row.peer_id)
    return {**row.view(), "memory": memory, "vitals": None, **host.presence.view(row.peer_id)}


def rename(host: PeerHost, body: dict[str, Any]) -> Reply:
    try:
        renamed = host.identity.rename(body.get("name"))
    except ValueError as exc:
        return peer_error(400, "bad_request", str(exc))
    host.publish("peer.changed", peer_id=None)
    return 200, {"ok": True, "self": {"device_id": renamed.device_id, "name": renamed.name}}


def open_pairing(host: PeerHost, body: dict[str, Any]) -> Reply:
    kind = body.get("kind")
    if kind not in KINDS:
        return peer_error(400, "bad_request", f"kind must be one of {', '.join(KINDS)}")
    record = host.pairings.open_window(str(kind))
    host.reconcile()
    base = host.base_url()
    return 200, {
        "ok": True,
        "pairing_id": record.pairing_id,
        "code": record.code,
        "url": f"{base}/m/#claim={record.pairing_id}.{record.nonce}" if base else None,
        "expires_at": record.pending_view()["expires_at"],
    }


def answer_pending(host: PeerHost, body: dict[str, Any], pairing_id: str) -> Reply:
    choice = body.get("choice")
    if choice not in ("approve", "decline"):
        return peer_error(400, "bad_request", "choice must be approve or decline")
    try:
        if choice == "decline":
            record = host.pairings.decline(pairing_id)
            host.audit.record("decline", pairing_id=record.pairing_id, kind=record.kind, name=record.name)
            host.publish("peer.changed", peer_id=None)
            return 200, {"ok": True, "state": record.state, "peer": None}
        days = body.get("expires_days")
        if days is not None and (
            isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_EXPIRES_DAYS
        ):
            return peer_error(400, "bad_request", f"expires_days is null or 1..{MAX_EXPIRES_DAYS}")
        grants = body.get("grants")
        if grants is not None and not isinstance(grants, list):
            return peer_error(400, "bad_request", f"grants is a list of {', '.join(GRANTS)}")
        current = host.pairings.get(pairing_id)
        asked = list(current.requested_grants) if current is not None else []
        record = host.pairings.approve(pairing_id, asked if grants is None else grants, days)
    except PairingRefused as refusal:
        return peer_error(refusal.status, refusal.error, refusal.detail, state=refusal.state)
    except ValueError as exc:
        return peer_error(400, "bad_request", str(exc))
    row = host.admit(record)
    host.audit.record(
        "approve",
        pairing_id=record.pairing_id,
        peer_id=row.peer_id,
        kind=record.kind,
        name=record.name,
        grants=list(record.granted),
    )
    host.reconcile()
    if record.direction == "pair_back":
        host.deliver(record)
    host.publish("peer.changed", peer_id=row.peer_id)
    return 200, {"ok": True, "state": record.state, "peer": row.view()}


def revoke(host: PeerHost, peer_id: str) -> Reply:
    if not host.revoke(peer_id):
        return peer_error(404, "unknown_ref", "No such device.")
    return 200, {"ok": True, "revoked": peer_id}


def beacon(host: PeerHost, body: dict[str, Any]) -> Reply:
    on = body.get("on")
    if not isinstance(on, bool):
        return peer_error(400, "bad_request", "on must be true or false")
    host.beacon = on
    host.reconcile()
    base = host.base_url()
    host.publish("peer.changed", peer_id=None)
    return 200, {"ok": True, "beacon": {"on": on, "url": f"{base}/m/" if on and base else None}}


def join(host: PeerHost, body: dict[str, Any]) -> Reply:
    address, code = body.get("address"), body.get("code")
    port = body.get("port", DEFAULT_PEER_PORT)
    grants = body.get("requested_grants", list(GRANTS))
    if not isinstance(address, str) or not isinstance(code, str) or not code.strip():
        return peer_error(400, "bad_request", "An address and a code are both needed.")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        return peer_error(400, "bad_request", "port must be a port number")
    if not isinstance(grants, list) or any(g not in GRANTS for g in grants):
        return peer_error(400, "bad_request", f"requested_grants is a list of {', '.join(GRANTS)}")
    return host.join(address.strip(), port, code, [str(g) for g in grants])


def routes(host: PeerHost) -> list[BaseRoute]:
    """The loopback routes, the fixed paths before the two with a trailing id."""

    # The host's calls block (a peer's answer, the overlay's); each runs in a worker thread so the
    # loopback server keeps answering the window meanwhile.
    async def run(fn: Any, *args: Any) -> Response:
        return _reply(await asyncio.to_thread(fn, *args))

    async def get_devices(_: Request) -> Response:
        return await run(devices, host)

    async def get_overlay(_: Request) -> Response:
        return JSONResponse(await asyncio.to_thread(overlay_peers))

    async def put_self(request: Request) -> Response:
        body = await _body(request)
        return _bad("send a JSON object") if body is None else await run(rename, host, body)

    async def post_pairing(request: Request) -> Response:
        body = await _body(request)
        return _bad("send a JSON object") if body is None else await run(open_pairing, host, body)

    async def put_beacon(request: Request) -> Response:
        body = await _body(request)
        return _bad("send a JSON object") if body is None else await run(beacon, host, body)

    async def post_join(request: Request) -> Response:
        body = await _body(request)
        return _bad("send a JSON object") if body is None else await run(join, host, body)

    async def post_pending(request: Request) -> Response:
        body = await _body(request)
        if body is None:
            return _bad("send a JSON object")
        return await run(answer_pending, host, body, request.path_params["pairing_id"])

    async def delete_peer(request: Request) -> Response:
        return await run(revoke, host, request.path_params["peer_id"])

    async def events(_: Request) -> Response:
        return StreamingResponse(
            host.bus.frames(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    return [
        Route("/devices", get_devices, methods=["GET"]),
        Route("/devices/self", put_self, methods=["PUT"]),
        Route("/devices/pairing", post_pairing, methods=["POST"]),
        Route("/devices/beacon", put_beacon, methods=["PUT"]),
        Route("/devices/join", post_join, methods=["POST"]),
        Route("/devices/overlay", get_overlay, methods=["GET"]),
        Route(EVENTS_PATH, events, methods=["GET"]),
        Route("/devices/pending/{pairing_id}", post_pending, methods=["POST"]),
        Route("/devices/{peer_id}", delete_peer, methods=["DELETE"]),
    ]
