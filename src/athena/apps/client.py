"""The app transports (ADR 0025).

- mcp_http: Streamable HTTP on a loopback URL only, ported from athena-portable's
  ``connectors/mcp/client.py`` (initialize, notifications/initialized, tools/list with nextCursor,
  tools/call; no redirects and no proxy; 1 MiB reply cap; :data:`~athena.contracts.APP_CALL_TIMEOUT_S`).
  The token rides in the ``Authorization`` header only and is redacted from every sentence.
- mcp_stdio: a child process this module spawns from argv (never a shell) on first use, owns, and
  reaps: after :data:`~athena.contracts.APP_IDLE_S` unused and at :meth:`AppClients.shutdown` (its
  process tree ended). Stdout is the protocol, one JSON-RPC message per line; stderr is drained on a
  thread and its last lines kept for a reason. A child that died is started again on the next call,
  once; when that one fails too the app answers unreachable until it is checked again.
- The class of a tool: readOnlyHint, or destructiveHint false and openWorldHint false -> auto; else
  gated. A hint counts only as the JSON boolean it is spelled as.

Every reason here can reach the screen, so it is plain words and never says "MCP".
"""

from __future__ import annotations

import atexit
import contextlib
import http.client
import ipaddress
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import IO, Any
from urllib.parse import urlsplit

from athena.apps.store import AppRow
from athena.connectors.vault import MAX_RESPONSE_BYTES, redact
from athena.contracts import (
    APP_CALL_TIMEOUT_S,
    APP_IDLE_S,
    APP_TOOLS_MAX,
    ActionClass,
    AppAnswer,
    AppStatus,
    AppTool,
)

#: The protocol versions this client speaks, newest first; the first is the one it asks for.
PROTOCOL_VERSIONS: tuple[str, ...] = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
#: ``tools/list`` pages followed before the listing is called too long.
MAX_PAGES = 10
CLIENT_INFO = {"name": "athena", "version": "0"}
#: The last lines of a child's stderr kept for a reason, and how much of them a reason quotes.
STDERR_LINES = 20
STDERR_QUOTED = 300
#: A description longer than this is cut: it reaches her tool list.
DESCRIPTION_MAX = 1000
AGAIN = "The tool stopped again after it was started again; check the app to try once more."


class AppFailure(Exception):
    """A call that did not reach the app, or got no usable answer. The sentence is plain words, safe
    to show (never a token). `refused` = the app answered and said no (a token it does not take)."""

    def __init__(self, sentence: str, *, refused: bool = False, status: int | None = None) -> None:
        super().__init__(sentence)
        self.sentence = sentence
        self.refused = refused
        self.status = status


@dataclass(frozen=True)
class Probe:
    status: AppStatus
    tools: list[AppTool]
    reason: str | None  # plain words; None when ok (or when every tool it listed is kept)


# --- the class of a tool ---------------------------------------------------------------------------


def access_of(annotations: Any) -> ActionClass:
    """auto for readOnlyHint true, or destructiveHint false and openWorldHint false; gated otherwise
    (MCP's own defaults are the fail-closed ones: a hint left out reads as the dangerous answer)."""
    if not isinstance(annotations, Mapping):
        return "gated"
    if annotations.get("readOnlyHint") is True:
        return "auto"
    if annotations.get("destructiveHint") is False and annotations.get("openWorldHint") is False:
        return "auto"
    return "gated"


def _tools_of(raw: list[dict[str, Any]]) -> tuple[list[AppTool], str | None]:
    """The tools as kept, capped at APP_TOOLS_MAX, and a reason when some were dropped."""
    kept: list[AppTool] = []
    seen: set[str] = set()
    for t in raw:
        name = t.get("name")
        if not isinstance(name, str) or not name or name in seen:
            continue
        schema = t.get("inputSchema")
        if schema is not None and not isinstance(schema, dict):
            continue  # read as "no schema" it would admit anything; a listed schema must be an object
        description = t.get("description")
        if not isinstance(description, str) or not description.strip():
            title = t.get("title")
            description = title if isinstance(title, str) else ""
        tool: AppTool = {
            "name": name,
            "description": " ".join(description.split())[:DESCRIPTION_MAX],
            "access": access_of(t.get("annotations")),
        }
        if isinstance(schema, dict):
            tool["input_schema"] = schema
        seen.add(name)
        kept.append(tool)
    if len(kept) > APP_TOOLS_MAX:
        return kept[:APP_TOOLS_MAX], f"It lists {len(kept)} tools; the first {APP_TOOLS_MAX} are offered."
    return kept, None


def answer_of(result: Mapping[str, Any]) -> AppAnswer:
    """A tools/call result as an AppAnswer: its text parts joined, other parts named."""
    lines: list[str] = []
    content = result.get("content")
    for part in content if isinstance(content, list) else []:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text" and isinstance(part.get("text"), str):
            lines.append(part["text"])
        elif part.get("type") in ("image", "audio"):
            lines.append(f"[an {part['type']} the app sent]")
        elif part.get("type") in ("resource", "resource_link"):
            res = part.get("resource") if isinstance(part.get("resource"), dict) else part
            uri = res.get("uri") if isinstance(res, dict) else None
            lines.append(
                f"[a file the app named: {uri}]" if isinstance(uri, str) else "[a file the app named]"
            )
    if not lines and isinstance(result.get("structuredContent"), dict):
        lines.append(json.dumps(result["structuredContent"], ensure_ascii=False))
    return {"text": "\n".join(lines), "is_error": result.get("isError") is True}


# --- loopback --------------------------------------------------------------------------------------


def is_loopback_url(url: str) -> bool:
    """An http(s) URL whose host is this computer (localhost or a loopback address), with no user."""
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises on a bad port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.hostname or "@" in parts.netloc:
        return False
    host = parts.hostname
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


# --- HTTP ------------------------------------------------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A 3xx is the answer: the token never rides to an address the owner did not name."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


#: No proxy either (a proxy from the environment would carry the token off this computer), and no
#: redirect. The vault's transport keeps the environment's proxies, so it is not reused here.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)

HttpTransport = Callable[[str, Mapping[str, str], bytes, float], tuple[int, bytes, Mapping[str, str]]]


def _post(
    url: str, headers: Mapping[str, str], body: bytes, timeout: float
) -> tuple[int, bytes, Mapping[str, str]]:
    request = urllib.request.Request(url, data=body, method="POST", headers=dict(headers))
    try:
        with _OPENER.open(request, timeout=timeout) as reply:
            return int(reply.status), reply.read(MAX_RESPONSE_BYTES + 1), dict(reply.headers.items())
    except urllib.error.HTTPError as exc:
        return (
            int(exc.code),
            exc.read(MAX_RESPONSE_BYTES + 1),
            dict(exc.headers.items()) if exc.headers else {},
        )
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise AppFailure("It did not answer in time.") from None
        raise AppFailure("Nothing answered at its address.") from None
    except (TimeoutError, ConnectionError, http.client.HTTPException):
        raise AppFailure("It stopped answering in the middle of a reply.") from None
    except OSError:
        raise AppFailure("Nothing answered at its address.") from None


def _header(headers: Mapping[str, str], name: str) -> str:
    lowered = name.lower()
    return next((v for k, v in headers.items() if k.lower() == lowered), "")


def _sse_messages(text: str) -> list[Any]:
    """The JSON payload of every ``data:`` event in an event-stream body."""
    out: list[Any] = []
    data: list[str] = []
    for line in [*text.splitlines(), ""]:
        if line.startswith("data:"):
            data.append(line[5:].removeprefix(" "))
        elif not line.strip() and data:
            with contextlib.suppress(json.JSONDecodeError):
                out.append(json.loads("\n".join(data)))
            data = []
    return out


class _HttpSession:
    """One app's HTTP conversation: the protocol version and the session id it was handed."""

    def __init__(self, url: str, transport: HttpTransport) -> None:
        self.url = url
        self.transport = transport
        self.token: str | None = None
        self.protocol_version = ""
        self.session_id = ""
        self.next_id = 0
        self.lock = threading.Lock()

    def _send(self, message: dict[str, Any], *, initialized: bool) -> tuple[int, bytes, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if initialized:
            headers["MCP-Protocol-Version"] = self.protocol_version
            if self.session_id:
                headers["Mcp-Session-Id"] = self.session_id
        status, raw, reply_headers = self.transport(
            self.url, headers, json.dumps(message).encode("utf-8"), float(APP_CALL_TIMEOUT_S)
        )
        if len(raw) > MAX_RESPONSE_BYTES:
            raise AppFailure("Its answer was larger than the 1 MiB an answer may be.", status=status)
        if message.get("method") == "initialize":
            self.session_id = _header(reply_headers, "Mcp-Session-Id").strip()
        if status in (401, 403):
            raise AppFailure("It refused the token it was given.", refused=True, status=status)
        return status, raw, _header(reply_headers, "Content-Type")

    def request(self, method: str, params: dict[str, Any], *, initialized: bool = True) -> dict[str, Any]:
        self.next_id += 1
        ident = self.next_id
        message = {"jsonrpc": "2.0", "id": ident, "method": method, "params": params}
        status, raw, content_type = self._send(message, initialized=initialized)
        if not 200 <= status < 300:
            raise AppFailure(f"It answered with an error (HTTP {status}).", status=status)
        text = raw.decode("utf-8", errors="replace")
        if "text/event-stream" in content_type.lower():
            candidates = _sse_messages(text)
        else:
            try:
                candidates = [json.loads(text)]
            except json.JSONDecodeError:
                candidates = []
        reply = next((m for m in candidates if isinstance(m, dict) and m.get("id") == ident), None)
        if reply is None:
            raise AppFailure("Its answer could not be read.", status=status)
        return _result(reply)

    def notify(self, method: str) -> None:
        status, _raw, _ = self._send({"jsonrpc": "2.0", "method": method}, initialized=True)
        if not 200 <= status < 300:
            raise AppFailure(f"It answered with an error (HTTP {status}).", status=status)

    def initialize(self) -> None:
        self.protocol_version = ""
        self.session_id = ""
        result = self.request("initialize", _init_params(), initialized=False)
        self.protocol_version = _version(result)
        self.notify("notifications/initialized")

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """A session the app ended (404 with a session id) is opened again once: nothing ran."""
        if not self.protocol_version:
            self.initialize()
        params = {"name": name, "arguments": arguments}
        try:
            return self.request("tools/call", params)
        except AppFailure as e:
            if e.status != 404 or not self.session_id:
                raise
        self.initialize()
        return self.request("tools/call", params)


def _init_params() -> dict[str, Any]:
    return {"protocolVersion": PROTOCOL_VERSIONS[0], "capabilities": {}, "clientInfo": CLIENT_INFO}


def _version(result: Mapping[str, Any]) -> str:
    version = result.get("protocolVersion")
    if version not in PROTOCOL_VERSIONS:
        raise AppFailure("It speaks a version of the tool protocol Athena does not.")
    return str(version)


class _RpcError(AppFailure):
    """The app answered and refused the request: it was reached."""


def _result(reply: Mapping[str, Any]) -> dict[str, Any]:
    error = reply.get("error")
    if isinstance(error, dict):
        said = str(error.get("message", ""))[:300]
        raise _RpcError(f"It refused the request: {said}" if said else "It refused the request.")
    result = reply.get("result")
    if not isinstance(result, dict):
        raise AppFailure("Its answer could not be read.")
    return result


def _list(request: Callable[[str, dict[str, Any]], dict[str, Any]]) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(MAX_PAGES):
        result = request("tools/list", {"cursor": cursor} if cursor else {})
        page = result.get("tools")
        if not isinstance(page, list):
            raise AppFailure("It listed no tools.")
        tools.extend(t for t in page if isinstance(t, dict))
        nxt = result.get("nextCursor")
        if not isinstance(nxt, str) or not nxt:
            return tools
        cursor = nxt
    raise AppFailure(f"It lists more than {MAX_PAGES} pages of tools.")


# --- stdio -----------------------------------------------------------------------------------------


@dataclass
class _Child:
    """One started tool: its process, its protocol state, and the last lines it wrote to stderr."""

    proc: subprocess.Popen[bytes]
    lines: queue.Queue[bytes | None]
    tail: deque[str] = field(default_factory=lambda: deque(maxlen=STDERR_LINES))
    protocol_version: str = ""
    next_id: int = 0
    last_used: float = 0.0
    drain: threading.Thread | None = None

    def alive(self) -> bool:
        return self.proc.poll() is None

    def said(self) -> str:
        """The child's last stderr lines, short, for a reason (once it ended, all it wrote)."""
        if self.drain is not None and not self.alive():
            self.drain.join(timeout=2)
        text = " ".join(" ".join(self.tail).split())
        return text[-STDERR_QUOTED:]


def _pump_lines(stream: IO[bytes], into: queue.Queue[bytes | None]) -> None:
    try:
        while True:
            line = stream.readline(MAX_RESPONSE_BYTES + 1)
            if not line:
                break
            into.put(line)
    except (OSError, ValueError):
        pass
    into.put(None)  # end of stream


def _drain(stream: IO[bytes], tail: deque[str]) -> None:
    try:
        for raw in iter(stream.readline, b""):
            tail.append(raw.decode("utf-8", errors="replace").rstrip())
    except (OSError, ValueError):
        pass


def _spawn(argv: list[str]) -> _Child:
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True  # its own process group, ended as one
    try:
        proc = subprocess.Popen(  # argv, never a shell: the owner signed this exact command
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            **kwargs,
        )
    except FileNotFoundError:
        raise AppFailure(f"The command {argv[0]!r} was not found on this computer.") from None
    except OSError as e:
        raise AppFailure(f"The command could not be started ({type(e).__name__}).") from None
    assert proc.stdout is not None and proc.stderr is not None
    child = _Child(proc, queue.Queue())
    threading.Thread(target=_pump_lines, args=(proc.stdout, child.lines), daemon=True).start()
    child.drain = threading.Thread(target=_drain, args=(proc.stderr, child.tail), daemon=True)
    child.drain.start()
    return child


def end_tree(proc: subprocess.Popen[bytes]) -> None:
    """Ends a child and every process it started: `taskkill /T /F` on Windows, its group elsewhere."""
    if proc.poll() is None:
        if sys.platform == "win32":
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
        else:
            with contextlib.suppress(OSError):
                os.killpg(proc.pid, signal.SIGKILL)
        with contextlib.suppress(OSError):
            proc.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=10)
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        if stream is not None:
            with contextlib.suppress(OSError):
                stream.close()


class _Died(AppFailure):
    """The child was gone before the request was written: nothing reached it, so a restart is safe."""


def _rpc(
    child: _Child, method: str, params: dict[str, Any] | None, *, notify: bool = False
) -> dict[str, Any]:
    if not child.alive():
        raise _Died("The tool had stopped.")
    message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        message["params"] = params
    ident = 0
    if not notify:
        child.next_id += 1
        ident = child.next_id
        message["id"] = ident
    assert child.proc.stdin is not None
    try:
        child.proc.stdin.write(json.dumps(message).encode("utf-8") + b"\n")
        child.proc.stdin.flush()
    except (OSError, ValueError):
        raise _Died("The tool had stopped.") from None
    if notify:
        return {}
    deadline = time.monotonic() + APP_CALL_TIMEOUT_S
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            raise AppFailure("It did not answer in time.")
        try:
            line = child.lines.get(timeout=left)
        except queue.Empty:
            raise AppFailure("It did not answer in time.") from None
        if line is None:  # its output ended: it is exiting, so its last words are waited for
            with contextlib.suppress(subprocess.TimeoutExpired):
                child.proc.wait(timeout=2)
            raise AppFailure("The tool stopped before it answered.")
        if len(line) > MAX_RESPONSE_BYTES:
            raise AppFailure("Its answer was larger than the 1 MiB an answer may be.")
        try:
            reply = json.loads(line)
        except json.JSONDecodeError:
            continue  # a line that is not the protocol (a stray print) is skipped
        if not isinstance(reply, dict):
            continue
        if "method" in reply and "id" in reply:  # a request from the tool: Athena serves none
            _answer_unsupported(child, reply["id"])
            continue
        if reply.get("id") == ident:
            return _result(reply)


def _answer_unsupported(child: _Child, ident: Any) -> None:
    assert child.proc.stdin is not None
    error = {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": "not supported"}}
    with contextlib.suppress(OSError, ValueError):
        child.proc.stdin.write(json.dumps(error).encode("utf-8") + b"\n")
        child.proc.stdin.flush()


def _handshake(child: _Child) -> None:
    result = _rpc(child, "initialize", _init_params())
    child.protocol_version = _version(result)
    _rpc(child, "notifications/initialized", None, notify=True)


@dataclass
class _Stdio:
    """One stdio app's slot: its child (None when not running), its lock, and the restart it has left."""

    argv: list[str]
    lock: threading.Lock = field(default_factory=threading.Lock)
    child: _Child | None = None
    restarted: bool = False  # the one restart after a death is spent until a call succeeds or a probe


# --- the clients ---------------------------------------------------------------------------------


class AppClients:
    """One live connection (or child process) per app_id, opened on demand."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        transport: HttpTransport = _post,
    ) -> None:
        self.clock = clock
        self._transport = transport
        self._lock = threading.Lock()
        self._http: dict[str, _HttpSession] = {}
        self._stdio: dict[str, _Stdio] = {}
        self._atexit = False

    # -- the four acts ------------------------------------------------------------------------------

    def probe(self, row: AppRow, token: str | None) -> Probe:
        """Connect and list tools. Never raises for an app that is down: answers `unreachable`."""
        self.reap_idle()
        try:
            if row.kind == "mcp_http":
                raw = self._http_list(row, token)
            elif row.kind == "mcp_stdio":
                raw = self._stdio_list(row)
            else:
                return Probe("unchecked", [], "Her browser opens this app; it lists no tools.")
        except AppFailure as e:
            status: AppStatus = "refused" if e.refused or isinstance(e, _RpcError) else "unreachable"
            return Probe(status, [], self._words(row, token, e))
        except Exception as e:  # a probe never raises for an app that is down
            return Probe("unreachable", [], f"It could not be checked ({type(e).__name__}).")
        tools, reason = _tools_of(raw)
        return Probe("ok", tools, reason)

    def call(self, row: AppRow, token: str | None, tool: str, arguments: dict[str, object]) -> AppAnswer:
        """One tools/call; a transport failure is `is_error` with the reason in `text`."""
        return self.attempt(row, token, tool, arguments)[0]

    def attempt(
        self, row: AppRow, token: str | None, tool: str, arguments: dict[str, object]
    ) -> tuple[AppAnswer, bool]:
        """One tools/call, and whether it reached the app: False is a transport failure (the app is
        unreachable), True an answer, the app's own error included."""
        self.reap_idle()
        try:
            if row.kind == "mcp_http":
                result = self._http_call(row, token, tool, dict(arguments))
            elif row.kind == "mcp_stdio":
                result = self._stdio_call(row, tool, dict(arguments))
            else:
                return {"text": "This app has no tools to call.", "is_error": True}, True
        except _RpcError as e:
            return {"text": self._words(row, token, e), "is_error": True}, True
        except AppFailure as e:
            return {"text": self._words(row, token, e), "is_error": True}, False
        answer = answer_of(result)
        answer["text"] = redact(answer["text"], [token or ""])
        return answer, True

    def reap_idle(self) -> None:
        """Stops stdio children unused for APP_IDLE_S."""
        now = self.clock()
        with self._lock:
            slots = list(self._stdio.values())
        for slot in slots:
            if not slot.lock.acquire(blocking=False):
                continue  # in a call right now: it is in use
            try:
                child = slot.child
                # A dead child is left for the next use, which counts its death (one restart).
                if child is not None and child.alive() and now - child.last_used >= APP_IDLE_S:
                    end_tree(child.proc)
                    slot.child = None
                    slot.restarted = False  # stopped by Athena, not dead: the next use starts it fresh
            finally:
                slot.lock.release()

    def shutdown(self) -> None:
        """Stops every child (its process tree) and closes every session."""
        with self._lock:
            slots = list(self._stdio.values())
            self._stdio.clear()
            self._http.clear()
        for slot in slots:
            with slot.lock:
                if slot.child is not None:
                    end_tree(slot.child.proc)
                    slot.child = None

    # -- http -----------------------------------------------------------------------------------

    def _session(self, row: AppRow, token: str | None) -> _HttpSession:
        if not is_loopback_url(row.address):
            raise AppFailure("Athena calls an app only at an address on this computer.", refused=True)
        with self._lock:
            session = self._http.get(row.app_id)
            if session is None or session.url != row.address or session.token != token:
                session = _HttpSession(row.address, self._transport)
                session.token = token
                self._http[row.app_id] = session
            return session

    def _http_list(self, row: AppRow, token: str | None) -> list[dict[str, Any]]:
        session = self._session(row, token)
        with session.lock:
            session.initialize()
            return _list(session.request)

    def _http_call(
        self, row: AppRow, token: str | None, tool: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        session = self._session(row, token)
        with session.lock:
            return session.call(tool, arguments)

    # -- stdio ----------------------------------------------------------------------------------

    def _slot(self, row: AppRow) -> _Stdio:
        argv = list(row.argv or [])
        if not argv or not all(isinstance(a, str) and a for a in argv):
            raise AppFailure("It has no command to start.")
        with self._lock:
            slot = self._stdio.get(row.app_id)
            if slot is None or slot.argv != argv:
                if slot is not None and slot.child is not None:
                    end_tree(slot.child.proc)
                slot = _Stdio(argv)
                self._stdio[row.app_id] = slot
            if not self._atexit:
                atexit.register(self.shutdown)  # a child never outlives the daemon
                self._atexit = True
            return slot

    def _start(self, slot: _Stdio) -> _Child:
        child = _spawn(slot.argv)
        slot.child = child
        child.last_used = self.clock()
        try:
            _handshake(child)
        except AppFailure as e:
            said = child.said()
            end_tree(child.proc)
            slot.child = None
            raise type(e)(f"{e.sentence} It said: {said}" if said else e.sentence) from None
        return child

    def _ready(self, slot: _Stdio) -> _Child:
        """The running child, started on first use; a dead one is started again once."""
        child = slot.child
        if child is not None and child.alive():
            return child
        if child is not None:  # it died on its own
            end_tree(child.proc)
            slot.child = None
            if slot.restarted:
                raise AppFailure(AGAIN)
            slot.restarted = True
        elif slot.restarted:  # the restart is spent and did not come up
            raise AppFailure(AGAIN)
        return self._start(slot)

    def _stdio_list(self, row: AppRow) -> list[dict[str, Any]]:
        slot = self._slot(row)
        with slot.lock:
            slot.restarted = False  # checking it again is the owner asking: it may start afresh
            child = self._ready(slot)
            try:
                tools = _list(lambda m, p: _rpc(child, m, p))
            finally:
                child.last_used = self.clock()
            return tools

    def _stdio_call(self, row: AppRow, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        slot = self._slot(row)
        with slot.lock:
            child = self._ready(slot)
            try:
                result = _rpc(child, "tools/call", {"name": tool, "arguments": arguments})
            except _Died:
                # Gone before the call was written: nothing ran, so it is started again once.
                if slot.restarted:
                    raise AppFailure(AGAIN) from None
                slot.restarted = True
                end_tree(child.proc)
                child = self._start(slot)
                result = _rpc(child, "tools/call", {"name": tool, "arguments": arguments})
            except AppFailure as e:
                if not child.alive():
                    said = child.said()
                    raise type(e)(f"{e.sentence} It said: {said}" if said else e.sentence) from None
                raise
            finally:
                child.last_used = self.clock()
            slot.restarted = False
            return result

    # -- words ----------------------------------------------------------------------------------

    @staticmethod
    def _words(row: AppRow, token: str | None, e: AppFailure) -> str:
        del row
        return redact(e.sentence, [token or ""])
