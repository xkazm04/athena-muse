"""The setup conversation: "Set up with Athena" on the Devices page (ADR 0017, portable ADR 0140 WP4).

A person who is not technical sets several devices up by talking to her. Her window opens a
conversation that speaks first, reads the private network's state, explains what Tailscale is before
it proposes installing it, and walks the steps. It is its own conversation (``SETUP_SPACE``), not a
project's, and its seven tools exist only in it: ``run_turn`` and the MCP server never offer them.

Three read, answered at once. Four change this machine, and each is a card the person signs
(``setup_act``); nothing runs until the signature, and the signed card runs the fixed command here.

**No string a model wrote ever reaches a command line.** Every command is an argv list fixed in this
file. The only parameters the tools take are an enum (``open_pairing``'s ``kind``) and an address
(``probe_peer``'s ``peer_ip``) that is checked to be inside the overlay ranges and is only ever
*dialled* (``athena.peer.client.call``), never passed to a process. The peer port in the firewall rule
is the host's own integer. The sign-in URL that is opened in the browser comes from ``tailscale``'s own
status and is opened only when it is ``https`` on ``tailscale.com``.

What each does (the three that change the machine run on Windows only; elsewhere they answer
:data:`NOT_HERE` and run nothing):

``overlay_status``, ``list_overlay_peers``, ``probe_peer`` (READ)
    ``{installed, logged_in, ip, tailnet_name}``; the other devices and whether Athena answers on each
    (a 401 ``unauthorized`` from an unauthenticated ``GET /peer/hello`` is "Athena is there"); one of
    ``no_overlay`` / ``logged_out`` / ``peer_unreachable`` / ``athena_asleep`` / ``ok`` for one device.
``install_overlay``
    ``winget install --id Tailscale.Tailscale -e ...``, started and not awaited.
``overlay_login``
    ``tailscale login`` started, the sign-in URL read back from ``tailscale status --json``.
``firewall_allow``
    One inbound rule, ``Athena peer``, TCP on the peer port from ``100.64.0.0/10`` only: looked for
    first, added through an elevated ``netsh`` (Windows asks the person), looked for again.
``open_pairing``
    Opens a window as ``POST /devices/pairing`` does. The card's outcome (which the next turn reads)
    carries the code for a PC and **never** the phone URL: its nonce is a claim credential. The window,
    its code and its URL go to this device's own window as ``pair.opened`` on the peer bus.

``GET /peer/hello`` reports ``setup_phase`` from :class:`SetupState`, and while the conversation is
open the peer listener stays up for :data:`SETUP_LISTEN_S`, so the other computer's probe finds Athena.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import weakref
import webbrowser
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urlsplit

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import BaseRoute, Route

from athena.app import Daemon
from athena.clock import mint
from athena.contracts import TEXT_MAX, Card, Surface, tool_event
from athena.engine import Engine, ToolCall
from athena.errors import ApiError
from athena.peer.classify import peer_class
from athena.peer.client import call
from athena.peer.overlay import NO_WINDOW, _find_tailscale
from athena.peer.registry import KINDS

if TYPE_CHECKING:
    from athena.peer.listener import PeerHost

__all__ = [
    "FIREWALL_RULE",
    "GATED",
    "NOT_HERE",
    "PROBE_STATES",
    "READS",
    "SETUP_LISTEN_S",
    "SETUP_OPENING",
    "SETUP_SPACE",
    "Done",
    "Ran",
    "Setup",
    "SetupState",
    "SetupTools",
    "SubprocessRunner",
    "firewall_add_argv",
    "firewall_show_argv",
    "of",
    "routes",
    "run_setup_turn",
    "sign",
]

#: The setup conversation's own space id. Not a project, so no project's turn, memory or tools meet it.
SETUP_SPACE = "setup"
NOT_HERE = "not on this computer yet: setup runs on Windows"
FIREWALL_RULE = "Athena peer"
FIREWALL_REMOTE = "100.64.0.0/10"
WINGET_ARGV: tuple[str, ...] = (
    "winget",
    "install",
    "--id",
    "Tailscale.Tailscale",
    "-e",
    "--accept-source-agreements",
    "--accept-package-agreements",
)
PROBE_STATES: tuple[str, ...] = ("no_overlay", "logged_out", "peer_unreachable", "athena_asleep", "ok")
READS: tuple[str, ...] = ("overlay_status", "list_overlay_peers", "probe_peer")
GATED: tuple[str, ...] = ("install_overlay", "overlay_login", "firewall_allow", "open_pairing")
PEER_LIMIT = 20
KNOCK_TIMEOUT_S = 1.5
STATUS_TIMEOUT_S = 5.0
ELEVATED_TIMEOUT_S = 120.0
LOGIN_WAIT_S = 8.0
LOGIN_POLL_S = 0.5
#: How long "Set up with Athena" keeps the peer listener up with nothing paired and no window open:
#: long enough to walk to the other computer and press it there too, so each probe finds Athena there.
SETUP_LISTEN_S = 30 * 60
HISTORY_TURNS = 30
CARDS_LISTED = 12


# --- running commands -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Ran:
    code: int
    stdout: str = ""


class CommandRunner(Protocol):
    """How a fixed argv is run. The real one is :class:`SubprocessRunner`; a test records argv."""

    def run(self, argv: Sequence[str], timeout: float) -> Ran | None: ...

    def spawn(self, argv: Sequence[str]) -> bool: ...


class SubprocessRunner:
    """``subprocess`` with no shell, no window, and every failure reduced to "it did not run"."""

    def run(self, argv: Sequence[str], timeout: float) -> Ran | None:
        try:
            done = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return Ran(done.returncode, done.stdout or "")

    def spawn(self, argv: Sequence[str]) -> bool:
        try:
            subprocess.Popen(
                list(argv),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return True


def firewall_show_argv() -> list[str]:
    return ["netsh", "advfirewall", "firewall", "show", "rule", f"name={FIREWALL_RULE}"]


def firewall_add_argv(port: int) -> list[str]:
    """The elevated ``netsh`` that adds the rule. ``port`` is the host's own integer."""
    rule = (
        f'advfirewall firewall add rule name="{FIREWALL_RULE}" dir=in action=allow '
        f"protocol=TCP localport={int(port)} remoteip={FIREWALL_REMOTE}"
    )
    command = f"Start-Process -FilePath netsh -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList '{rule}'"
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]


def knock(ip: str, port: int) -> bool:
    """Does an Athena peer listener answer at ``ip:port``? Unauthenticated: a 401 is a yes."""
    host = f"[{ip}]" if ":" in ip else ip
    answer = call(f"http://{host}:{port}", "GET", "/peer/hello", timeout=KNOCK_TIMEOUT_S)
    return answer.status == 401 and answer.body.get("error") == "unauthorized"


# --- the overlay, as setup reads it -------------------------------------------------------------


@dataclass(frozen=True)
class Peer:
    name: str
    ip: str | None
    os: str
    online: bool


@dataclass(frozen=True)
class Status:
    installed: bool
    logged_in: bool = False
    ip: str | None = None
    tailnet_name: str | None = None
    auth_url: str | None = None
    peers: tuple[Peer, ...] = ()


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
    me = data["Self"] if isinstance(data.get("Self"), dict) else {}
    tailnet = data["CurrentTailnet"] if isinstance(data.get("CurrentTailnet"), dict) else {}
    name = tailnet.get("Name")
    auth = data.get("AuthURL")
    peers: list[Peer] = []
    raw_peers = data.get("Peer")
    if isinstance(raw_peers, dict):
        for row in raw_peers.values():
            if isinstance(row, dict):
                peers.append(
                    Peer(
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
        ip=_v4(me.get("TailscaleIPs")),
        tailnet_name=name if isinstance(name, str) and name else None,
        auth_url=auth if isinstance(auth, str) and auth else None,
        peers=tuple(peers),
    )


def sign_in_url(url: str | None) -> str | None:
    """The URL, when it is Tailscale's own ``https`` sign-in page; ``None`` for anything else."""
    if not url:
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not (host == "tailscale.com" or host.endswith(".tailscale.com")):
        return None
    return url


# --- the executors --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Done:
    """What one tool did. ``ok`` false means the thing did not happen (a signed card then waits again)."""

    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    #: Plain words for the person, for a signed card's outcome; the reads leave it empty.
    detail: str = ""

    def text(self) -> str:
        return json.dumps(self.data, sort_keys=True)


class SetupTools:
    """The seven executors over one peer host; everything that touches the OS is injected."""

    def __init__(
        self,
        host: PeerHost,
        *,
        runner: CommandRunner | None = None,
        knock: Callable[[str, int], bool] = knock,
        opener: Callable[[str], object] = webbrowser.open,
        platform: str = sys.platform,
        binary: Callable[[], str | None] = _find_tailscale,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.host = host
        self.runner: CommandRunner = runner or SubprocessRunner()
        self.knock = knock
        self.opener = opener
        self.windows = platform == "win32"
        self.binary = binary
        self.sleep = sleep

    def run(self, name: str, params: dict[str, Any]) -> Done:
        """One of the seven, by name; nothing else is a setup tool."""
        if name not in READS + GATED:
            return Done(False, {"state": "unknown"}, "That is not a setup step.")
        return getattr(self, name)(params)  # type: ignore[no-any-return]

    # -- reading the overlay ----------------------------------------------------------------------

    def status(self) -> tuple[str | None, Status]:
        binary = self.binary()
        if binary is None:
            return None, Status(installed=False)
        ran = self.runner.run([binary, "status", "--json"], STATUS_TIMEOUT_S)
        # ``status --json`` exits non-zero when logged out and still prints the document.
        if ran is None or not ran.stdout.strip():
            return binary, Status(installed=True)
        return binary, parse_status(ran.stdout)

    def overlay_status(self, params: dict[str, Any]) -> Done:
        _, s = self.status()
        return Done(
            True,
            {"installed": s.installed, "logged_in": s.logged_in, "ip": s.ip, "tailnet_name": s.tailnet_name},
        )

    def list_overlay_peers(self, params: dict[str, Any]) -> Done:
        _, s = self.status()
        if not s.installed:
            return Done(True, {"state": "no_overlay", "peers": []})
        if not s.logged_in:
            return Done(True, {"state": "logged_out", "peers": []})
        shown = list(s.peers[:PEER_LIMIT])
        port = self.host.port
        targets = [p.ip for p in shown if p.online and p.ip]
        knocked: dict[str, bool] = {}
        if targets:
            with ThreadPoolExecutor(max_workers=min(8, len(targets))) as pool:
                for ip, answered in zip(
                    targets, pool.map(lambda ip: self.knock(ip, port), targets), strict=True
                ):
                    knocked[ip] = answered
        rows = [
            {
                "name": p.name,
                "ip": p.ip,
                "os": p.os,
                "online": p.online,
                "athena": knocked.get(p.ip) if p.ip and p.online else None,
            }
            for p in shown
        ]
        data: dict[str, Any] = {"peers": rows}
        if len(s.peers) > len(shown):
            data["footer"] = f"(showing {len(shown)} of {len(s.peers)})"
        return Done(True, data)

    def probe_peer(self, params: dict[str, Any]) -> Done:
        ip = str(params.get("peer_ip", "")).strip()
        if peer_class(ip) != "overlay":
            return Done(False, {"state": "refused"}, "peer_ip must be an address on the private network")
        _, s = self.status()
        peer = next((p for p in s.peers if p.ip == ip), None)
        if not s.installed:
            state = "no_overlay"
        elif not s.logged_in:
            state = "logged_out"
        elif peer is None or not peer.online:
            state = "peer_unreachable"
        elif self.knock(ip, self.host.port):
            state = "ok"
        else:
            state = "athena_asleep"
        return Done(True, {"state": state, "name": peer.name if peer else None, "ip": ip})

    # -- changing this machine --------------------------------------------------------------------

    def _not_here(self) -> Done:
        return Done(True, {"state": "not_here"}, NOT_HERE)

    def install_overlay(self, params: dict[str, Any]) -> Done:
        if not self.windows:
            return self._not_here()
        if self.binary() is not None:
            return Done(True, {"state": "already_installed"}, "Tailscale is already installed.")
        if not self.runner.spawn(list(WINGET_ARGV)):
            return Done(False, {"state": "failed"}, "The Windows package manager (winget) did not start.")
        return Done(True, {"state": "started"}, "Tailscale is installing; this takes a minute or two.")

    def overlay_login(self, params: dict[str, Any]) -> Done:
        if not self.windows:
            return self._not_here()
        binary, s = self.status()
        if binary is None:
            return Done(False, {"state": "no_overlay"}, "Install Tailscale first.")
        if s.logged_in:
            return Done(True, {"state": "already_signed_in"}, "Tailscale is already signed in.")
        if not self.runner.spawn([binary, "login"]):
            return Done(False, {"state": "failed"}, "Tailscale's sign-in did not start.")
        waited = 0.0
        url = sign_in_url(s.auth_url)
        while url is None and waited < LOGIN_WAIT_S:
            self.sleep(LOGIN_POLL_S)
            waited += LOGIN_POLL_S
            url = sign_in_url(self.status()[1].auth_url)
        if url is None:
            return Done(True, {"state": "started"}, "The sign-in started; Tailscale opens its own page.")
        self.opener(url)
        return Done(True, {"state": "opened"}, "The sign-in page is open in your browser.")

    def firewall_allow(self, params: dict[str, Any]) -> Done:
        if not self.windows:
            return self._not_here()
        port = self.host.port
        if self._rule_exists():
            return Done(
                True,
                {"state": "already_allowed", "port": port},
                "Your other devices can already reach Athena here.",
            )
        self.runner.run(firewall_add_argv(port), ELEVATED_TIMEOUT_S)
        if self._rule_exists():
            return Done(
                True, {"state": "allowed", "port": port}, "Your other devices can now reach Athena here."
            )
        return Done(False, {"state": "not_allowed"}, "The rule was not added; Windows may have said no.")

    def _rule_exists(self) -> bool:
        ran = self.runner.run(firewall_show_argv(), STATUS_TIMEOUT_S)
        return ran is not None and ran.code == 0 and FIREWALL_RULE in ran.stdout

    def open_pairing(self, params: dict[str, Any]) -> Done:
        kind = params.get("kind")
        if kind not in KINDS:
            return Done(False, {"state": "refused"}, "kind must be pc or phone")
        host = self.host
        record = host.pairings.open_window(str(kind))
        host.reconcile()
        base = host.base_url()
        expires_at = record.pending_view()["expires_at"]
        # The code and the QR URL go to this device's own window only (loopback bus). ``device_kind``,
        # not ``kind``: the bus stamps every frame's ``kind`` with the event's own name.
        host.publish(
            "pair.opened",
            pairing_id=record.pairing_id,
            device_kind=record.kind,
            code=record.code,
            url=f"{base}/m/#claim={record.pairing_id}.{record.nonce}" if base else None,
            expires_at=expires_at,
        )
        data: dict[str, Any] = {
            "state": "open",
            "kind": record.kind,
            "expires_at": expires_at,
            "listening": base is not None,
        }
        if record.kind == "pc":
            data["code"] = record.code
            detail = f"A pairing window is open for five minutes. The code to read out is {record.code}."
        else:
            detail = (
                "A pairing window is open for five minutes. Scan the QR on the Devices page with the phone."
            )
        return Done(True, data, detail)


# --- the conversation's state ---------------------------------------------------------------------


class SetupState:
    """Whether this device's person opened a setup conversation, and what it is waiting for."""

    def __init__(self, host: PeerHost) -> None:
        self.host = host
        self._lock = threading.Lock()
        self.opened_at: datetime | None = None

    def opened(self) -> None:
        with self._lock:
            self.opened_at = self.host.now()
        self.host.reconcile()  # up now: the other computer's probe may already be asking

    def listening(self) -> bool:
        with self._lock:
            opened = self.opened_at
        return opened is not None and (self.host.now() - opened).total_seconds() < SETUP_LISTEN_S

    def phase(self) -> str | None:
        """``None`` until a setup conversation was opened here, then one word: ``installing`` (no
        overlay), ``signing_in`` (logged out), ``approving`` (a device waits for this person),
        ``waiting`` (this device waits on another's person), ``pairing`` (a window is open), ``paired``
        (at least one peer), ``ready`` (set up, nothing paired yet)."""
        with self._lock:
            if self.opened_at is None:
                return None
        host = self.host
        state = host.overlay().state
        if state == "absent":
            return "installing"
        if state == "logged_out":
            return "signing_in"
        if host.pairings.pending():
            return "approving"
        if any(join.get("state") == "pending" for join in host.join_views()):
            return "waiting"
        if host.pairings.window_open():
            return "pairing"
        if host.registry.live_count() > 0:
            return "paired"
        return "ready"


class Setup:
    """The setup conversation's parts for one peer host."""

    def __init__(self, host: PeerHost, tools: SetupTools | None = None) -> None:
        self.host = host
        self.tools = tools or SetupTools(host)
        self.state = SetupState(host)


_SERVICES: weakref.WeakKeyDictionary[Any, Setup] = weakref.WeakKeyDictionary()
_SERVICES_LOCK = threading.Lock()


def of(daemon: Daemon, tools: SetupTools | None = None) -> Setup:
    """This daemon's setup service, made once. ``tools`` (tests) replaces the real executors."""
    host = daemon.peers
    if host is None:
        raise ApiError("bad_request", "devices are switched off on this computer")
    with _SERVICES_LOCK:
        service = _SERVICES.get(host)
        if service is None or tools is not None:
            service = Setup(host, tools)
            _SERVICES[host] = service
            host.setup_phase = service.state.phase
            host.listen_for_setup = service.state.listening
        return service


# --- what she is told -----------------------------------------------------------------------------

LAW = (
    "You are Athena, a desktop companion who works for one person on their own computer. Be brief and "
    "plain. Some steps change this computer. Those only take effect after the person signs the card "
    "you file; until then say they are waiting, and never claim a step is done while its card waits."
)

GUIDE = """## Setting up several devices as one Athena

This conversation connects this computer, the person's other computers and their phone, over a
private network (Tailscale). The person is probably not technical. Say one step at a time, in plain
words, and wait for them. Never ask them to type a command.

The same conversation runs on the other computer too. When the person is between the two, say what
the other one is waiting for ("your laptop is waiting for you to approve it on the Devices page there").

The steps, in order. Check before you change anything; skip a step that is already done.

1. Call `overlay_status`. Not installed: explain what Tailscale is, then propose `install_overlay`
   and say a Windows prompt may ask them to allow it.
2. Installed but not signed in: propose `overlay_login`. The sign-in page is the one step only they can
   do, and every device must use the same account.
3. Signed in: propose `firewall_allow` once, so the other devices can reach Athena here. Windows may
   ask for permission.
4. `list_overlay_peers` shows the other devices; `probe_peer` checks one by its address: ok,
   athena_asleep, peer_unreachable (that device is off or offline), logged_out, no_overlay.
   athena_asleep is normal before two computers are paired: Athena listens only while someone is in
   its setup conversation or a pairing window is open. Say so in a sentence and go on to step 5.
5. To join two computers: on ONE of them propose `open_pairing` with kind pc and read the code to the
   person once the card is signed; on the OTHER, they type that code on the Devices page, with the
   first computer's address (`list_overlay_peers` on the other computer names it). Each computer's
   person approves the other on its own Devices page.
6. For the phone: propose `open_pairing` with kind phone and tell them to scan the QR on the Devices
   page, then approve the phone when it asks.

Each change is a card the person signs; file one at a time and wait. Cards already signed or waiting
are listed below, with what came of them. If a step fails, say what happened in one sentence and what
they can do next."""

#: The first turn of a setup conversation, written here and never by a window: "Set up with Athena"
#: sends ``start`` with no message and this is what she is told instead, so she speaks first. Most
#: people have never heard of Tailscale, so she says what it is before she proposes installing it.
SETUP_OPENING = (
    'The person just pressed "Set up with Athena" on the Devices page and is waiting for you to start. '
    "Call `overlay_status` first. Then, in two or three short sentences, say what you found and what the "
    "first step is. If Tailscale is not installed, say plainly what it is - a free private network that "
    "lets their own computers and phone reach each other, and nothing else - before you propose "
    "installing it, and say that Windows may ask them to allow the install. If it is installed but not "
    "signed in, tell them the sign-in page will open and that it is the one step only they can do. "
    "Propose one step, then wait for them."
)

CONTINUE = (
    "The person answered the card you filed (see the list of cards in your instructions) or came back. "
    "Call `overlay_status` if it helps, say in one sentence what came of it, and go to the next step."
)

LABELS = {
    "overlay_status": "Looked at the private network",
    "list_overlay_peers": "Looked for the other devices",
    "probe_peer": "Checked another device",
    "install_overlay": "Install Tailscale, the private network",
    "overlay_login": "Sign in to Tailscale",
    "firewall_allow": "Let your other devices reach Athena here",
    "open_pairing": "Open a pairing window",
}


def _tool(name: str, description: str, props: dict[str, str], required: list[str]) -> dict[str, Any]:
    from athena.turn import _tool as build

    return build(name, description, props, required)


def tools() -> list[dict[str, Any]]:
    """The seven function tools. They are offered nowhere but here."""
    none: dict[str, str] = {}
    return [
        _tool(
            "overlay_status",
            "Is the private network (Tailscale) installed here and signed in; this computer's address on it.",
            none,
            [],
        ),
        _tool(
            "list_overlay_peers",
            (
                "The person's other devices on the private network: online or not, and "
                "whether Athena answers on each."
            ),
            none,
            [],
        ),
        _tool(
            "probe_peer",
            (
                "Check one other computer by its private-network address: no_overlay, logged_out, "
                "peer_unreachable, athena_asleep or ok."
            ),
            {"peer_ip": "The device's address on the private network, as list_overlay_peers gave it"},
            ["peer_ip"],
        ),
        _tool(
            "install_overlay",
            "Install Tailscale with the Windows package manager. Needs the person's signature.",
            none,
            [],
        ),
        _tool(
            "overlay_login",
            "Start Tailscale's sign-in and open its page in the browser. Needs the person's signature.",
            none,
            [],
        ),
        _tool(
            "firewall_allow",
            (
                "Let the person's other devices reach Athena here: one Windows firewall rule for "
                "Athena's peer port, from the private network only. Needs the person's signature."
            ),
            none,
            [],
        ),
        _tool(
            "open_pairing",
            (
                "Open a five-minute pairing window for another computer (a code you then read out) "
                "or a phone (a QR on the Devices page). Needs the person's signature."
            ),
            {"kind": "pc or phone"},
            ["kind"],
        ),
    ]


class SetupDesign:
    """One setup turn's tool handling, shaped like a design (``turn._rounds`` hands it the calls)."""

    surface: Surface = "turn"

    def __init__(self, daemon: Daemon, service: Setup) -> None:
        self.daemon = daemon
        self.service = service
        self.cards: list[Card] = []

    progressed = False

    def owns(self, name: str) -> bool:
        return True  # nothing else is offered in this conversation, so nothing else is dispatched

    def tools(self) -> list[dict[str, Any]]:
        return tools()

    def frame(self) -> str:
        return ""

    def fallback(self) -> str:
        return "I have nothing to add."

    def record(self, reply: str) -> str:
        return reply

    def settle(self) -> list[dict[str, Any]]:
        return []

    def call(self, call: ToolCall) -> tuple[str, list[dict[str, Any]]]:
        name, args = call.name, call.arguments
        if name in READS:
            done = self.service.tools.run(name, args)
            if not done.ok:
                return done.detail, []
            return done.text(), [tool_event("setup_read", LABELS[name])]
        if name not in GATED:
            return "That is not a step this conversation offers.", []
        card_args: dict[str, Any] = {"tool": name}
        if name == "open_pairing":
            kind = args.get("kind")
            if kind not in KINDS:
                return "kind must be pc or phone.", []
            card_args["kind"] = kind
        label = LABELS[name] + (f" ({card_args['kind']})" if "kind" in card_args else "")
        for waiting in self.daemon.gate.list("waiting"):
            if waiting["space_id"] == SETUP_SPACE and waiting["args"] == card_args:
                return "That card is already waiting for the person to sign.", []
        card = self.daemon.gate.file(SETUP_SPACE, "setup_act", card_args, label)
        self.cards.append(card)
        return "Filed for the person to sign. Nothing has changed yet.", [
            tool_event("setup_act", label),
            {"type": "card", "card": card},
        ]


def _cards_frame(daemon: Daemon) -> str:
    cards = [c for c in daemon.gate.list() if c["space_id"] == SETUP_SPACE][:CARDS_LISTED]
    if not cards:
        return ""
    lines = ["", "", "## Cards so far, newest first"]
    for c in cards:
        said = c.get("outcome") or {
            "waiting": "waiting for the person's signature",
            "declined": "declined",
        }.get(c["state"], c["state"])
        lines.append(f"- {c['label']}: {c['state']} - {said}")
    return "\n".join(lines)


def _messages(daemon: Daemon, hidden: str | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": f"{LAW}\n\n{GUIDE}{_cards_frame(daemon)}"}]
    for t in daemon.conversation.list(SETUP_SPACE, HISTORY_TURNS):
        out.append({"role": "user" if t["role"] == "person" else "assistant", "content": t["text"]})
    if hidden is not None:
        out.append({"role": "user", "content": hidden})
    return out


def run_setup_turn(
    daemon: Daemon, engine: Engine, text: str | None, *, start: bool = False
) -> Iterator[dict[str, Any]]:
    """One turn of the setup conversation. Validates now (so the route can answer a 4xx), streams when
    iterated. ``start`` with no ``text`` makes her speak first (or pick up after a signed card): the
    instruction she is given for it is never stored and never shown."""
    service = of(daemon)
    said = (text or "").strip()
    if not said and not start:
        raise ApiError("bad_request", "say something, or send start")
    if len(said) > TEXT_MAX:
        raise ApiError("bad_request", f"say something between 1 and {TEXT_MAX} characters")
    return _stream(daemon, engine, service, said, start)


def _stream(
    daemon: Daemon, engine: Engine, service: Setup, text: str, start: bool
) -> Iterator[dict[str, Any]]:
    from athena.turn import _rounds

    service.state.opened()
    with daemon.busy.turn(SETUP_SPACE):
        turn_id = mint("turn_")
        yield {"type": "start", "turn_id": turn_id, "engine": engine.id, "simulated": engine.simulated}
        hidden: str | None = None
        if text:
            daemon.conversation.append(SETUP_SPACE, "person", text)
        elif start:
            hidden = CONTINUE if daemon.conversation.list(SETUP_SPACE, 1) else SETUP_OPENING
        design = SetupDesign(daemon, service)
        outcome = yield from _rounds(
            daemon, engine, _messages(daemon, hidden), tools(), SETUP_SPACE, "turn", None, design
        )
        if outcome is None:
            return
        reply_parts, _, cost_total = outcome
        cards = design.cards
        reply = "".join(reply_parts).strip()
        if not reply:
            reply = f"I filed a card for you to sign: {cards[0]['label']}" if cards else design.fallback()
            yield {"type": "text", "delta": reply}
        daemon.conversation.append(
            SETUP_SPACE, "athena", reply, cost_usd=cost_total, card_id=cards[0]["id"] if cards else None
        )
        done: dict[str, Any] = {"type": "done", "turn_id": turn_id, "waiting": bool(cards)}
        if cost_total is not None:
            done["cost_usd"] = cost_total
        yield done


# --- a signed card --------------------------------------------------------------------------------


def sign(daemon: Daemon, card: Card) -> str:
    """Run one approved ``setup_act`` card: the fixed command for its tool. Raises (so the card waits
    again) when the thing did not happen; returns the person's outcome in plain words."""
    args = card["args"]
    name = str(args.get("tool", ""))
    if name not in GATED:
        raise ApiError("bad_request", "that step cannot be signed")
    done = of(daemon).tools.run(name, {"kind": args["kind"]} if "kind" in args else {})
    if not done.ok:
        raise ApiError("bad_request", done.detail or "It could not be done, so nothing changed. Try again.")
    return done.detail


# --- the loopback routes --------------------------------------------------------------------------


def _line(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


def routes(daemon: Daemon) -> list[BaseRoute]:
    """``POST /devices/setup`` opens the conversation; ``POST /devices/setup/run`` runs a turn in it
    (``{text}`` or ``{start: true}``, NDJSON like ``/run``); ``GET /devices/setup/conversation``."""

    async def open_(_: Request) -> Response:
        service = of(daemon)
        service.state.opened()
        opened = service.state.opened_at
        return JSONResponse(
            {
                "ok": True,
                "space_id": SETUP_SPACE,
                "phase": service.state.phase(),
                "opened_at": opened.isoformat(timespec="seconds") if opened else None,
            }
        )

    async def run(request: Request) -> Response:
        from athena import engine as engine_mod
        from athena import routes_turn
        from athena.engine import EngineError
        from athena.keys import KeyStore

        try:
            data = await request.json()
        except ValueError:
            data = None
        if not isinstance(data, dict):
            raise ApiError("bad_request", "send a JSON object")
        text, start = data.get("text"), data.get("start") is True
        if text is not None and not isinstance(text, str):
            raise ApiError("bad_request", "send text as a string")
        try:
            engine = engine_mod.build_engine(
                KeyStore(daemon.data_dir),
                stored=daemon.settings.engine_choice(),
                transport=routes_turn.TRANSPORT,
            )
        except EngineError as e:
            raise ApiError("engine_unavailable", e.reason) from e
        events = run_setup_turn(daemon, engine, text, start=start)
        first = next(events)  # takes the conversation's slot now, so a second tab answers 409

        def lines() -> Iterator[bytes]:
            yield _line(first)
            for event in events:
                yield _line(event)

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    async def conversation(_: Request) -> Response:
        turns = await run_in_threadpool(daemon.conversation.list, SETUP_SPACE, 200)
        return JSONResponse({"turns": turns})

    return [
        Route("/devices/setup", open_, methods=["POST"]),
        Route("/devices/setup/run", run, methods=["POST"]),
        Route("/devices/setup/conversation", conversation, methods=["GET"]),
    ]
