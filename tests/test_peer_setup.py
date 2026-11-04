"""The setup conversation (ADR 0017): fixed argv, the five probe states, the gate, the phase, the hold."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import turn
from athena.app import Daemon
from athena.engine import TextDelta, ToolCall, Usage
from athena.errors import ApiError
from athena.peer import setup
from athena.peer.listener import PeerHost
from athena.peer.overlay import Overlay
from athena.peer.setup import Ran, SetupTools
from athena.server import create_app
from test_peer import MemorySeal

TOKEN = "t"


def status_doc(
    *, running: bool = True, peers: Sequence[tuple[str, str, bool]] = (), auth: str | None = None
) -> str:
    doc: dict[str, Any] = {
        "BackendState": "Running" if running else "NeedsLogin",
        "Self": {"TailscaleIPs": ["100.64.0.1"]},
        "CurrentTailnet": {"Name": "me@example.com"},
        "Peer": {
            f"k{i}": {"HostName": name, "TailscaleIPs": [ip], "OS": "windows", "Online": online}
            for i, (name, ip, online) in enumerate(peers)
        },
    }
    if auth:
        doc["AuthURL"] = auth
    return json.dumps(doc)


class Recorder:
    """A CommandRunner that records every argv and answers from a table."""

    def __init__(self, status: str = "", rule: bool = False) -> None:
        self.status = status
        self.rule = rule
        self.ran: list[list[str]] = []
        self.spawned: list[list[str]] = []
        self.spawn_ok = True

    def run(self, argv: Sequence[str], timeout: float) -> Ran | None:
        self.ran.append(list(argv))
        if argv[1:3] == ["status", "--json"]:
            return Ran(0, self.status)
        if argv[0] == "netsh":
            return Ran(0 if self.rule else 1, "Rule Name: Athena peer" if self.rule else "")
        if argv[0] == "powershell":
            self.rule = True  # the person said yes to Windows' prompt
        return Ran(0)

    def spawn(self, argv: Sequence[str]) -> bool:
        self.spawned.append(list(argv))
        return self.spawn_ok


def peer_host(root: Path, overlay: Overlay | None = None) -> PeerHost:
    up = overlay or Overlay("up", "127.0.0.1")
    return PeerHost(root, port=17491, probe=lambda: up, seal=MemorySeal(), admit_loopback=True)  # type: ignore[arg-type]


def tools(
    host: PeerHost,
    runner: Recorder,
    *,
    binary: str | None = "tailscale",
    platform: str = "win32",
    knock: Callable[[str, int], bool] = lambda ip, port: True,
    opened: list[str] | None = None,
) -> SetupTools:
    return SetupTools(
        host,
        runner=runner,
        knock=knock,
        opener=(opened if opened is not None else []).append,
        platform=platform,
        binary=lambda: binary,
        sleep=lambda s: None,
    )


@pytest.fixture
def host(tmp_path: Path) -> Iterator[PeerHost]:
    h = peer_host(tmp_path / "peer")
    yield h
    h.close()


# --- the executors: argv fixed and exact --------------------------------------------------------


def test_install_is_exactly_winget_and_is_started_not_awaited(host: PeerHost) -> None:
    runner = Recorder()
    done = tools(host, runner, binary=None).install_overlay({"argv": ["calc"], "x": "; rm -rf"})
    assert done.ok and done.data["state"] == "started"
    assert runner.spawned == [
        ["winget", "install", "--id", "Tailscale.Tailscale", "-e", "--accept-source-agreements",
         "--accept-package-agreements"]
    ]  # fmt: skip
    assert runner.ran == []


def test_login_opens_only_tailscales_own_https_page(host: PeerHost) -> None:
    for url, opens in [
        ("https://login.tailscale.com/a/abc", True),
        ("http://login.tailscale.com/a/abc", False),
        ("https://evil.example/tailscale.com", False),
        ("https://tailscale.com.evil.example/a", False),
    ]:
        opened: list[str] = []
        runner = Recorder(status_doc(running=False, auth=url))
        done = tools(host, runner, opened=opened).overlay_login({})
        assert done.ok
        assert runner.spawned == [["tailscale", "login"]]
        assert opened == ([url] if opens else [])


def test_firewall_checks_then_adds_one_elevated_rule_then_checks_again(host: PeerHost) -> None:
    runner = Recorder()
    done = tools(host, runner).firewall_allow({"port": 1, "remote": "0.0.0.0/0"})
    assert done.ok and done.data == {"state": "allowed", "port": 17491}
    show = ["netsh", "advfirewall", "firewall", "show", "rule", "name=Athena peer"]
    assert runner.ran[0] == show and runner.ran[-1] == show
    add = runner.ran[1]
    assert add[:4] == ["powershell", "-NoProfile", "-NonInteractive", "-Command"]
    assert "-Verb RunAs" in add[4]
    assert "protocol=TCP localport=17491 remoteip=100.64.0.0/10" in add[4]
    assert "0.0.0.0" not in add[4]
    assert len(runner.ran) == 3


def test_firewall_that_is_already_there_adds_nothing_and_a_refusal_fails(host: PeerHost) -> None:
    present = Recorder(rule=True)
    assert tools(host, present).firewall_allow({}).data["state"] == "already_allowed"
    assert len(present.ran) == 1
    refused = Recorder()
    refused.run = lambda argv, timeout: Ran(1, "")  # type: ignore[method-assign]
    done = tools(host, refused).firewall_allow({})
    assert not done.ok and done.data["state"] == "not_allowed"


@pytest.mark.parametrize("name", ["install_overlay", "overlay_login", "firewall_allow"])
def test_off_windows_the_machine_changing_steps_run_nothing(host: PeerHost, name: str) -> None:
    runner = Recorder()
    done = tools(host, runner, platform="linux").run(name, {})
    assert done.ok and done.detail == setup.NOT_HERE
    assert runner.ran == [] and runner.spawned == []


def test_only_the_seven_names_are_setup_tools(host: PeerHost) -> None:
    runner = Recorder()
    done = tools(host, runner).run("rm", {})
    assert not done.ok and runner.ran == [] and runner.spawned == []
    assert {t["function"]["name"] for t in setup.tools()} == set(setup.READS + setup.GATED)


# --- probe_peer ---------------------------------------------------------------------------------


def probe(
    host: PeerHost, runner: Recorder, ip: str, *, binary: str | None = "tailscale", knock: bool = True
) -> str:
    done = tools(host, runner, binary=binary, knock=lambda a, p: knock).probe_peer({"peer_ip": ip})
    return str(done.data["state"])


def test_probe_peer_reports_the_five_states(host: PeerHost) -> None:
    peers = [("Laptop", "100.64.0.2", True), ("Old", "100.64.0.3", False)]
    up = Recorder(status_doc(peers=peers))
    assert probe(host, up, "100.64.0.2") == "ok"
    assert probe(host, up, "100.64.0.2", knock=False) == "athena_asleep"
    assert probe(host, up, "100.64.0.3") == "peer_unreachable"
    assert probe(host, up, "100.64.0.9") == "peer_unreachable"
    assert probe(host, Recorder(status_doc(running=False)), "100.64.0.2") == "logged_out"
    assert probe(host, Recorder(), "100.64.0.2", binary=None) == "no_overlay"


@pytest.mark.parametrize(
    "ip", ["192.168.1.5", "8.8.8.8", "127.0.0.1", "evil.example", "", "100.128.0.1", "10.0.0.1"]
)
def test_probe_peer_refuses_anything_outside_the_overlay_and_dials_nothing(host: PeerHost, ip: str) -> None:
    dialled: list[str] = []
    runner = Recorder(status_doc(peers=[("Laptop", "100.64.0.2", True)]))
    done = tools(host, runner, knock=lambda a, p: dialled.append(a) or True).probe_peer({"peer_ip": ip})
    assert not done.ok and dialled == [] and runner.ran == []


def test_list_overlay_peers_names_who_answers(host: PeerHost) -> None:
    runner = Recorder(status_doc(peers=[("Laptop", "100.64.0.2", True), ("Phone", "100.64.0.3", False)]))
    done = tools(host, runner, knock=lambda ip, port: ip == "100.64.0.2").list_overlay_peers({})
    rows = {r["name"]: r for r in done.data["peers"]}
    assert rows["Laptop"]["athena"] is True and rows["Phone"]["athena"] is None
    assert tools(host, Recorder(), binary=None).list_overlay_peers({}).data["state"] == "no_overlay"


# --- open_pairing never hands the url to the model ----------------------------------------------


def test_open_pairing_keeps_the_phone_url_off_the_answer_and_on_the_bus(host: PeerHost) -> None:
    host.reconcile()
    inbox = host.bus.subscribe()
    t = tools(host, Recorder())
    phone = t.open_pairing({"kind": "phone"})
    pc = t.open_pairing({"kind": "pc"})
    assert "url" not in phone.data and "code" not in phone.data and "claim=" not in json.dumps(phone.data)
    assert "claim=" not in phone.detail and "claim=" not in pc.text()
    assert pc.data["code"] and pc.data["code"] in pc.detail
    frames = [inbox.get_nowait(), inbox.get_nowait()]
    opened = [f for f in frames if f["kind"] == "pair.opened"]
    assert [f["device_kind"] for f in opened] == ["phone", "pc"]
    assert set(opened[0]) >= {"pairing_id", "device_kind", "code", "url", "expires_at"}
    assert opened[0]["url"] is None or "#claim=" in opened[0]["url"]
    assert t.open_pairing({"kind": "tablet"}).ok is False


# --- the gate: a card, and nothing runs until it is signed --------------------------------------


class Script:
    id = "scripted"
    model = "scripted"
    simulated = True
    cost_estimated = False

    def __init__(self, rounds: list[list[ToolCall]]) -> None:
        self.rounds = rounds
        self.seen: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []

    def probe(self) -> dict[str, Any]:
        return {"ok": True}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        self.seen.append(([dict(m) for m in messages], tools))
        n = len(self.seen)
        calls = self.rounds[n - 1] if n <= len(self.rounds) else []
        yield TextDelta("Here is what I found. " if calls else "It waits for you.")
        yield from calls
        yield Usage(input_tokens=1, output_tokens=1)


@pytest.fixture
def setup_daemon(daemon: Daemon, host: PeerHost) -> Daemon:
    daemon.peers = host
    daemon.gate.set_executor(lambda card: turn.execute(daemon, card))
    return daemon


def test_a_gated_step_files_a_card_and_runs_nothing_until_it_is_signed(
    setup_daemon: Daemon, host: PeerHost
) -> None:
    runner = Recorder(status_doc(running=False))
    setup.of(setup_daemon, tools(host, runner, binary=None))
    engine = Script(
        [[ToolCall("c1", "install_overlay", {"cmd": "calc.exe"}), ToolCall("c2", "overlay_status", {})]]
    )
    events = list(setup.run_setup_turn(setup_daemon, engine, None, start=True))  # type: ignore[arg-type]
    assert (
        runner.spawned == [] and runner.ran == []
    )  # the read ran (no binary: nothing to ask); nothing changed
    card = next(e["card"] for e in events if e["type"] == "card")
    assert (
        card["action"] == "setup_act"
        and card["state"] == "waiting"
        and card["args"] == {"tool": "install_overlay"}
    )
    assert events[-1] == {"type": "done", "turn_id": events[0]["turn_id"], "waiting": True} | (
        {"cost_usd": events[-1]["cost_usd"]} if "cost_usd" in events[-1] else {}
    )
    # the same step is not filed twice while it waits
    again = Script([[ToolCall("c3", "install_overlay", {})]])
    list(setup.run_setup_turn(setup_daemon, again, "go on", start=False))  # type: ignore[arg-type]
    assert len(setup_daemon.gate.list("waiting")) == 1

    runner_after = setup_daemon.gate.resolve(card["id"], "approve")
    assert runner_after["state"] == "approved" and "Tailscale is installing" in runner_after["outcome"]
    assert runner.spawned and runner.spawned[0][0] == "winget"


def test_a_declined_card_runs_nothing_and_a_failed_one_waits_again(
    setup_daemon: Daemon, host: PeerHost
) -> None:
    runner = Recorder()
    runner.spawn_ok = False
    setup.of(setup_daemon, tools(host, runner, binary=None))
    engine = Script([[ToolCall("c1", "install_overlay", {})]])
    events = list(setup.run_setup_turn(setup_daemon, engine, None, start=True))  # type: ignore[arg-type]
    card = next(e["card"] for e in events if e["type"] == "card")
    with pytest.raises(ApiError):
        setup_daemon.gate.resolve(card["id"], "approve")  # winget did not start
    assert setup_daemon.gate.get(card["id"])["state"] == "waiting"
    setup_daemon.gate.resolve(card["id"], "decline")
    assert setup_daemon.gate.get(card["id"])["state"] == "declined" and runner.ran == []


def test_a_model_cannot_reach_a_project_tool_or_a_bad_pairing_kind(
    setup_daemon: Daemon, host: PeerHost
) -> None:
    setup.of(setup_daemon, tools(host, Recorder()))
    engine = Script(
        [[ToolCall("a", "remember", {"text": "x"}), ToolCall("b", "open_pairing", {"kind": "../../x"}),
          ToolCall("c", "probe_peer", {"peer_ip": "192.168.0.4"})]]
    )  # fmt: skip
    list(setup.run_setup_turn(setup_daemon, engine, "hi"))  # type: ignore[arg-type]
    assert setup_daemon.gate.list() == []
    assert setup_daemon.memory.kept("") == []
    offered = {t["function"]["name"] for t in engine.seen[0][1]}
    assert offered == set(setup.READS + setup.GATED)


def test_project_turns_never_offer_the_setup_tools(daemon: Daemon) -> None:
    engine = Script([])
    list(turn.run_turn(daemon, engine, "hello", ""))  # type: ignore[arg-type]
    offered = {t["function"]["name"] for t in engine.seen[0][1]}
    assert offered.isdisjoint(set(setup.READS + setup.GATED))


def test_she_speaks_first_and_picks_up_after_a_card(setup_daemon: Daemon, host: PeerHost) -> None:
    setup.of(setup_daemon, tools(host, Recorder()))
    first = Script([])
    list(setup.run_setup_turn(setup_daemon, first, None, start=True))  # type: ignore[arg-type]
    messages = first.seen[0][0]
    assert messages[0]["role"] == "system" and "Tailscale" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": setup.SETUP_OPENING}
    turns = setup_daemon.conversation.list(setup.SETUP_SPACE)
    assert [t["role"] for t in turns] == ["athena"]  # the opening instruction is not a person's line
    second = Script([])
    list(setup.run_setup_turn(setup_daemon, second, None, start=True))  # type: ignore[arg-type]
    assert second.seen[0][0][-1]["content"] == setup.CONTINUE
    assert setup_daemon.conversation.list("") == []  # no project saw any of it
    with pytest.raises(ApiError):
        setup.run_setup_turn(setup_daemon, first, "  ", start=False)  # type: ignore[arg-type]


def test_the_next_turn_reads_what_a_signed_card_came_to(setup_daemon: Daemon, host: PeerHost) -> None:
    setup.of(setup_daemon, tools(host, Recorder()))
    engine = Script([[ToolCall("c1", "open_pairing", {"kind": "pc"})]])
    events = list(setup.run_setup_turn(setup_daemon, engine, None, start=True))  # type: ignore[arg-type]
    card = next(e["card"] for e in events if e["type"] == "card")
    signed = setup_daemon.gate.resolve(card["id"], "approve")
    code = signed["outcome"].rsplit(" ", 1)[1].rstrip(".")
    follow = Script([])
    list(setup.run_setup_turn(setup_daemon, follow, None, start=True))  # type: ignore[arg-type]
    system = follow.seen[0][0][0]["content"]
    assert "Cards so far" in system and code in system and "claim=" not in system


# --- the phase and the hold ---------------------------------------------------------------------


def test_setup_phase_is_null_until_opened_then_follows_the_device(tmp_path: Path) -> None:
    states = {"now": Overlay("absent")}
    host = PeerHost(
        tmp_path / "p", port=0, probe=lambda: states["now"], seal=MemorySeal(), admit_loopback=True
    )  # type: ignore[arg-type]
    try:
        state = setup.SetupState(host)
        assert state.phase() is None
        state.opened()
        assert state.phase() == "installing"
        states["now"] = Overlay("logged_out")
        host.overlay(fresh=True)
        assert state.phase() == "signing_in"
        states["now"] = Overlay("up", "127.0.0.1")
        host.overlay(fresh=True)
        assert state.phase() == "ready"
        host.pairings.open_window("pc")
        assert state.phase() == "pairing"
    finally:
        host.close()


def test_the_listener_stays_up_for_thirty_minutes_after_setup_opens(tmp_path: Path) -> None:
    clock = {"t": 1_000_000.0}
    from datetime import UTC, datetime

    host = PeerHost(
        tmp_path / "q",
        port=0,
        probe=lambda: Overlay("up", "127.0.0.1"),
        seal=MemorySeal(),  # type: ignore[arg-type]
        admit_loopback=True,
        now=lambda: datetime.fromtimestamp(clock["t"], UTC),
    )
    try:
        service = setup.Setup(host)
        host.setup_phase, host.listen_for_setup = service.state.phase, service.state.listening
        host.reconcile()
        assert host.bound is None and not host.wanted()
        service.state.opened()
        assert host.wanted() and host.bound is not None
        clock["t"] += setup.SETUP_LISTEN_S - 1
        assert host.wanted()
        clock["t"] += 2
        assert not host.wanted()
        host.reconcile()
        assert host.bound is None
    finally:
        host.close()


# --- the loopback routes ------------------------------------------------------------------------


def test_the_routes_open_the_conversation_and_hello_reports_the_phase(
    setup_daemon: Daemon, host: PeerHost, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = TestClient(create_app(setup_daemon, token=TOKEN), headers={"Authorization": f"Bearer {TOKEN}"})
    from athena.peer import routes as peer_routes
    from athena.peer.listener import PeerRequest

    def hello_phase() -> object:
        request = PeerRequest("GET", "/peer/hello", {}, {}, "127.0.0.1", None)  # type: ignore[arg-type]
        return peer_routes.hello(host, request)[1]["setup_phase"]

    assert hello_phase() is None
    opened = client.post("/devices/setup").json()
    assert (
        opened["ok"]
        and opened["space_id"] == "setup"
        and opened["phase"] in {"ready", "signing_in", "installing"}
    )
    assert hello_phase() == opened["phase"]
    assert client.get("/devices/setup/conversation").json() == {"turns": []}
    assert client.post("/devices/setup/run", json={}).status_code == 400
    assert client.post("/devices/setup/run", json={"text": 5}).status_code == 400
    run = client.post("/devices/setup/run", json={"start": True})
    kinds = [json.loads(line)["type"] for line in run.text.splitlines()]
    assert kinds[0] == "start" and kinds[-1] == "done"
    assert [t["role"] for t in client.get("/devices/setup/conversation").json()["turns"]] == ["athena"]


def test_hello_carries_the_look_chosen_in_settings_and_nothing_else_of_it(
    setup_daemon: Daemon, host: PeerHost
) -> None:
    from athena.peer import routes as peer_routes
    from athena.peer.listener import PeerRequest

    create_app(setup_daemon, token=TOKEN)

    def hello_look() -> object:
        request = PeerRequest("GET", "/peer/hello", {}, {}, "127.0.0.1", None)  # type: ignore[arg-type]
        return peer_routes.hello(host, request)[1]["look"]

    assert hello_look() == {"theme": "auto", "type_scale": "standard", "motion": "system"}
    setup_daemon.settings.set_look({"theme": "light", "motion": "calm"})
    assert hello_look() == {"theme": "light", "type_scale": "standard", "motion": "calm"}
