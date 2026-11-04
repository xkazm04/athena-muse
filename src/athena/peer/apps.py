"""Apps offered across paired devices (ADR 0026).

**The offering side (B)** serves, on the overlay listener, with the ``apps`` grant:

- ``GET /peer/apps`` -> :class:`~athena.contracts.OfferedList`: the device-level apps marked offered,
  each as label, kind, tools and whether it names an output folder; never an address, argv, token or
  the folder itself.
- ``POST /peer/apps/{app_id}/call`` (:class:`~athena.contracts.PeerAppCall`) ->
  :class:`~athena.contracts.AppAnswer`. The app must be offered (404 ``not_offered``), the tool in B's
  own listing (404 ``no_such_tool``), and a tool B's listing marks gated must carry the approving
  card's id (403 ``approval_missing``), which B records and cannot verify. An app that did not answer
  is 502 ``app_unreachable``. Every call and every refusal is a row in B's peer audit (``app_call``);
  an ``agent`` in the body (the outside agent that asked on A) is kept in that row as text, beside the
  approval, and never decides anything.
- ``GET /peer/apps/{app_id}/file?path=`` -> the bytes of one file under the app's output folder
  (resolved with its links, so a link out of the folder is outside it: 403 ``outside_output``), at
  most :data:`~athena.contracts.APP_FILE_MAX_BYTES` (413 ``too_large``).

**The calling side (A)** uses :func:`offers`, :func:`call_remote` and :func:`fetch_remote`. Each
raises :class:`~athena.errors.ApiError` in plain words when the call did not reach the app (the
device unknown or silent, or a refusal at its door); :func:`call_remote` answers the app's
:class:`~athena.contracts.AppAnswer` whenever the app itself answered, its own errors included.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import suppress
from http.client import HTTPConnection
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast, get_args
from urllib.parse import quote, urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena.apps.store import PROCESS_KINDS, AppRow
from athena.contracts import (
    APP_CALL_TIMEOUT_S,
    APP_FILE_MAX_BYTES,
    ActionClass,
    AppAnswer,
    AppKind,
    AppTool,
    ErrorWord,
    OfferedApp,
    OfferedList,
)
from athena.errors import ApiError
from athena.peer.client import MAX_ANSWER_BYTES, call
from athena.peer.listener import BinaryReply, PeerRequest, PeerRoute, Reply, peer_error, peer_of

if TYPE_CHECKING:
    from athena.app import Daemon
    from athena.peer.listener import PeerHost

PREFIX = "/peer/apps/"
#: How long A waits for B's answer to one call: the app's own limit, and room for the trip.
CALL_WAIT_S = float(APP_CALL_TIMEOUT_S) + 10.0
#: How long one read of a file's bytes may stall before the pull is given up.
FILE_WAIT_S = 30.0
CHUNK = 1 << 20
#: The most offered apps (and tools of each) A reads from one answer: a cap on a broken peer.
OFFERED_MAX = 64
TOOLS_MAX = 200
REASON_MAX = 200
#: The longest agent name B keeps in its audit row.
AGENT_MAX = 40
TOO_LARGE = "that file is larger than a file brought in may be"
OVER_ALLOWANCE = "that file is larger than the agent may still bring in"
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ACCESS: tuple[str, ...] = get_args(ActionClass)


# --- the offering side (B) ------------------------------------------------------------------------


def _offered_row(daemon: Daemon, app_id: str) -> AppRow | None:
    return next((r for r in daemon.apps.offered() if r.app_id == app_id and r.kind in PROCESS_KINDS), None)


def offered_view(row: AppRow) -> OfferedApp:
    """What a paired device sees of one offered app: never its address, argv, token or folder."""
    return {
        "app_id": row.app_id,
        "kind": row.kind,
        "label": row.label,
        "tools": list(row.tools),
        "has_output": bool(row.output_dir),
    }


def list_route(daemon: Daemon) -> Reply:
    listed: OfferedList = {
        "offered": [offered_view(r) for r in daemon.apps.offered() if r.kind in PROCESS_KINDS]
    }
    return 200, dict(listed)


def _split(path: str) -> tuple[str, str]:
    """``/peer/apps/<app_id>/<tail>`` -> (app_id, tail); ("", "") when it is not that shape."""
    app_id, _, tail = path[len(PREFIX) :].partition("/")
    return (app_id, tail) if _ID.fullmatch(app_id) else ("", "")


def call_route(host: PeerHost, daemon: Daemon, request: PeerRequest) -> Reply:
    peer = peer_of(request)
    app_id, tail = _split(request.path)
    if tail != "call":
        return peer_error(404, "not_found", "no such app route")
    body = request.body
    tool, arguments, approval_id = body.get("tool"), body.get("arguments", {}), body.get("approval_id")
    # Audit text only: who asked on A, in A's words. Nothing below reads it.
    raw_agent = body.get("agent")
    agent = " ".join(raw_agent.split())[:AGENT_MAX] if isinstance(raw_agent, str) else ""

    def audit(outcome: str) -> None:
        host.audit.record(
            "app_call",
            peer=peer.peer_id,
            app=app_id,
            tool=tool if isinstance(tool, str) else None,
            approval_id=approval_id if isinstance(approval_id, str) else None,
            agent=agent or None,
            outcome=outcome,
        )

    if not isinstance(tool, str) or not tool or not isinstance(arguments, dict):
        audit("bad_request")
        return peer_error(400, "bad_request", "send the tool and its arguments")
    if approval_id is not None and (not isinstance(approval_id, str) or not _ID.fullmatch(approval_id)):
        audit("bad_request")
        return peer_error(400, "bad_request", "an approval is named by its card's id")
    row = _offered_row(daemon, app_id)
    if row is None:
        audit("not_offered")
        return peer_error(404, "not_offered", "this computer does not offer that app")
    listed = next((t for t in row.tools if t["name"] == tool), None)
    if listed is None:
        audit("no_such_tool")
        return peer_error(404, "no_such_tool", f"{row.label} does not list that tool")
    if listed["access"] != "auto" and approval_id is None:
        audit("approval_missing")
        return peer_error(403, "approval_missing", "that tool needs the person's signature first")
    token = daemon.apps.token("", row.app_id)
    answer, reached = daemon.app_clients.attempt(row, token, tool, arguments)
    if not reached:
        audit("app_unreachable")
        return peer_error(502, "app_unreachable", answer["text"])
    audit("error" if answer["is_error"] else "ran")
    out: AppAnswer = {"text": answer["text"], "is_error": bool(answer["is_error"])}
    return 200, dict(out)


def _resolve(row: AppRow, raw: str) -> Path | None:
    """The file `raw` names under the app's output folder, its links resolved; None when outside."""
    if not row.output_dir or not raw or "\x00" in raw:
        return None
    try:
        base = Path(row.output_dir).resolve(strict=True)
        source = (base / raw).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if source == base or not source.is_relative_to(base):
        return None
    return source


def file_route(daemon: Daemon, request: PeerRequest) -> Reply | BinaryReply:
    app_id, tail = _split(request.path)
    if tail != "file":
        return peer_error(404, "not_found", "no such app route")
    row = _offered_row(daemon, app_id)
    if row is None:
        return peer_error(404, "not_offered", "this computer does not offer that app")
    if not row.output_dir:
        return peer_error(404, "no_output", f"{row.label} has no output folder to bring files from")
    source = _resolve(row, request.query.get("path", "").strip())
    if source is None:
        return peer_error(403, "outside_output", f"that file is outside {row.label}'s output folder")
    try:
        if not source.is_file():
            return peer_error(404, "not_found", f"there is no such file in {row.label}'s output folder")
        size = source.stat().st_size
        if size > APP_FILE_MAX_BYTES:
            return peer_error(413, "too_large", "that file is larger than a file brought in may be")
    except OSError:
        return peer_error(404, "not_found", f"that file in {row.label}'s output folder could not be read")
    # Written from the file in chunks by the listener, never held in memory.
    return BinaryReply(200, b"", "application/octet-stream", {"Cache-Control": "no-store"}, path=source)


def peer_routes(host: PeerHost, daemon: Daemon) -> list[PeerRoute]:
    return [
        PeerRoute("GET", "/peer/apps", lambda r: list_route(daemon), grant="apps"),
        PeerRoute("POST", PREFIX, lambda r: call_route(host, daemon, r), grant="apps", prefix=True),
        PeerRoute("GET", PREFIX, lambda r: file_route(daemon, r), grant="apps", prefix=True),
    ]


# --- the calling side (A) -------------------------------------------------------------------------


def _name(daemon: Daemon, peer_id: str) -> str:
    row = daemon.peers.registry.get(peer_id) if daemon.peers is not None else None
    return row.name if row is not None and row.name else "That device"


def _keyed(daemon: Daemon, peer_id: str) -> tuple[str, str]:
    """Where the peer listens and the token this device calls it with; ApiError when there are none."""
    host = daemon.peers
    if host is None:
        raise ApiError("unknown_ref", "this computer is not set up to work with other devices")
    url, token = host.keys.url(peer_id), host.keys.token(peer_id)
    if url is None or token is None:
        raise ApiError("unknown_ref", "that device is not paired with this computer")
    return url, token


def _refused(name: str, status: int, body: dict[str, Any]) -> ApiError:
    """B's refusal in plain words, as an ApiError with B's status."""
    word = body.get("error")
    said = body.get("reason")
    said = " ".join(said.split())[:REASON_MAX] if isinstance(said, str) else ""
    sentence = {
        "grant_missing": f"{name} has not given this computer its apps",
        "unauthorized": f"{name} no longer knows this computer",
        "not_offered": f"{name} no longer offers that app",
        "no_such_tool": f"{name}'s app does not list that tool",
        "approval_missing": f"{name} needs the person's signature for that tool",
        "outside_output": f"that file is outside the app's output folder on {name}",
        "too_large": "that file is larger than a file brought in may be",
    }.get(str(word), "")
    if not sentence:
        sentence = said or f"{name} refused ({status})"
    error: ErrorWord = "unknown_ref" if status == 404 else "bad_request"
    return ApiError(error, sentence, status if 400 <= status < 600 else 502)


def _tool(raw: object) -> AppTool | None:
    if not isinstance(raw, dict):
        return None
    name, description, access = raw.get("name"), raw.get("description", ""), raw.get("access")
    if not isinstance(name, str) or not name or not isinstance(description, str) or access not in _ACCESS:
        return None
    tool: AppTool = {"name": name, "description": description, "access": cast("ActionClass", access)}
    schema = raw.get("input_schema")
    if isinstance(schema, dict):
        tool["input_schema"] = schema
    return tool


def _offer(raw: object) -> OfferedApp | None:
    if not isinstance(raw, dict):
        return None
    app_id, kind, label = raw.get("app_id"), raw.get("kind"), raw.get("label")
    tools = raw.get("tools")
    if not isinstance(app_id, str) or not _ID.fullmatch(app_id) or kind not in PROCESS_KINDS:
        return None
    if not isinstance(label, str) or not isinstance(tools, list):
        return None
    kept = [t for t in (_tool(x) for x in tools[:TOOLS_MAX]) if t is not None]
    return {
        "app_id": app_id,
        "kind": cast("AppKind", kind),
        "label": label,
        "tools": kept,
        "has_output": raw.get("has_output") is True,
    }


def offers(daemon: Daemon, peer_id: str) -> list[OfferedApp]:
    """What a paired device offers this one (live call to its /peer/apps)."""
    url, token = _keyed(daemon, peer_id)
    name = _name(daemon, peer_id)
    answer = call(url, "GET", "/peer/apps", token=token)
    if not answer.reached:
        raise ApiError("bad_request", f"{name} did not answer", 502)
    if answer.status != 200:
        raise _refused(name, answer.status, answer.body)
    listed = answer.body.get("offered")
    if not isinstance(listed, list):
        raise ApiError("bad_request", f"{name} answered something Athena could not read", 502)
    return [o for o in (_offer(x) for x in listed[:OFFERED_MAX]) if o is not None]


def call_remote(
    daemon: Daemon,
    peer_id: str,
    remote_app_id: str,
    tool: str,
    arguments: dict[str, Any],
    approval_id: str | None,
    agent: str | None = None,
) -> AppAnswer:
    """One call to the peer's app. Raises ApiError when it did not reach the app; answers the app's
    AppAnswer (its own error included) when it did. `agent` names the outside agent that asked, for
    B's audit only; absent, the body is what it always was."""
    url, token = _keyed(daemon, peer_id)
    name = _name(daemon, peer_id)
    body: dict[str, Any] = {"tool": tool, "arguments": arguments}
    if approval_id is not None:
        body["approval_id"] = approval_id
    if agent is not None and " ".join(agent.split()):
        body["agent"] = " ".join(agent.split())[:AGENT_MAX]
    path = f"{PREFIX}{quote(remote_app_id, safe='')}/call"
    answer = call(url, "POST", path, body, token=token, timeout=CALL_WAIT_S)
    if not answer.reached:
        raise ApiError("bad_request", f"{name} did not answer", 502)
    if answer.status != 200:
        if answer.body.get("error") == "app_unreachable":
            said = answer.body.get("reason")
            why = " ".join(said.split())[:REASON_MAX] if isinstance(said, str) else ""
            raise ApiError("bad_request", f"the app on {name} did not answer. {why}".strip(), 502)
        raise _refused(name, answer.status, answer.body)
    text, is_error = answer.body.get("text"), answer.body.get("is_error")
    if not isinstance(text, str) or not isinstance(is_error, bool):
        raise ApiError("bad_request", f"{name} answered something Athena could not read", 502)
    return {"text": text, "is_error": is_error}


def fetch_remote(
    daemon: Daemon, peer_id: str, remote_app_id: str, path: str, dest: Path, max_bytes: int | None = None
) -> int:
    """Streams one file from the peer's app output folder into `dest`; returns its size in bytes.
    Nothing is left at `dest` when it fails. `max_bytes` (an agent's file allowance) stops it sooner
    than the one-file cap, as soon as the file passes it."""
    cap, too = APP_FILE_MAX_BYTES, TOO_LARGE
    if max_bytes is not None and max_bytes < cap:
        cap, too = max(0, max_bytes), OVER_ALLOWANCE
    url, token = _keyed(daemon, peer_id)
    name = _name(daemon, peer_id)
    parts = urlsplit(url)
    if parts.scheme != "http" or not parts.hostname:
        raise ApiError("bad_request", f"{name} is kept at an address Athena cannot call", 502)
    target = f"{PREFIX}{quote(remote_app_id, safe='')}/file?path={quote(path, safe='')}"
    connection = HTTPConnection(parts.hostname, parts.port or 80, timeout=FILE_WAIT_S)
    written = 0
    try:
        try:
            connection.request(
                "GET", target, headers={"Authorization": f"Bearer {token}", "Connection": "close"}
            )
            reply = connection.getresponse()
        except (OSError, ValueError):
            raise ApiError("bad_request", f"{name} did not answer", 502) from None
        if reply.status != 200:
            try:
                decoded = json.loads(reply.read(MAX_ANSWER_BYTES) or b"{}")
            except (OSError, ValueError):
                decoded = {}
            raise _refused(name, reply.status, decoded if isinstance(decoded, dict) else {})
        try:
            length = int(reply.getheader("Content-Length") or "-1")
        except ValueError:
            length = -1
        if length > cap:
            raise ApiError("bad_request", too, 413)
        try:
            with dest.open("wb") as out:
                while True:
                    block = reply.read(CHUNK)
                    if not block:
                        break
                    written += len(block)
                    if written > cap:
                        raise ApiError("bad_request", too, 413)
                    out.write(block)
        except OSError:
            raise ApiError("bad_request", f"the file from {name} could not be brought in", 502) from None
        if length >= 0 and written != length:
            raise ApiError("bad_request", f"the file from {name} arrived cut short", 502)
    except BaseException:
        with suppress(OSError):
            dest.unlink(missing_ok=True)
        raise
    finally:
        connection.close()
    return written


# --- the loopback route: what a paired device offers, for the window ------------------------------


def loopback_routes(daemon: Daemon) -> list[BaseRoute]:
    async def peer_offers(request: Request) -> Response:
        if daemon.peers is None:
            raise ApiError("unknown_ref", "this computer is not set up to work with other devices")
        found = await asyncio.to_thread(offers, daemon, str(request.path_params["peer_id"]))
        listed: OfferedList = {"offered": found}
        return JSONResponse(listed)

    return [Route("/devices/{peer_id}/apps", peer_offers, methods=["GET"])]
