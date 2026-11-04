"""Her tools for a project's apps (ADR 0025, 0026): named for the app (and the paired device), a
read-only tool answers at once under app_read, any other files an app_act card the signature runs
once; app_fetch brings a file from an app's output folder only; add_app shows a command word for word."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from apps_fake import TOOLS, FakeApps, HttpApp
from athena import mcp
from athena.app import Daemon
from athena.apps import tools as apps_tools
from athena.apps.client import access_of
from athena.apps.store import AppRow
from athena.browser.actions import Dispatched
from athena.contracts import AppAnswer, AppRemote, AppTool
from athena.engine import ToolCall
from athena.errors import ApiError
from athena.turn import dispatch, execute

LISTED: list[AppTool] = [
    {
        "name": t["name"],
        "description": t["description"],
        "access": access_of(t["annotations"]),
        "input_schema": t["inputSchema"],
    }
    for t in TOOLS
]


def remote(tools: list[AppTool] = LISTED) -> AppRemote:
    return {
        "peer_id": "peer_b",
        "device": "Studio PC",
        "remote_app_id": "app_on_b",
        "status": "ok",
        "tools": tools,
    }


def row(space: str, url: str = "http://127.0.0.1:9/mcp", **kw: Any) -> AppRow:
    fields: dict[str, Any] = {"status": "ok", "tools": LISTED, **kw}
    return AppRow("app_q", space, "mcp_http", "Queue", "queue", url, **fields)


@pytest.fixture
def signing(daemon: Daemon) -> Daemon:
    daemon.gate.set_executor(lambda card: execute(daemon, card))
    return daemon


@pytest.fixture
def app() -> Iterator[HttpApp]:
    with HttpApp() as served:
        yield served


def wire(d: Daemon, *rows: AppRow, remotes: dict[str, list[AppRemote]] | None = None) -> FakeApps:
    fake = FakeApps(list(rows), remotes)  # type: ignore[arg-type]
    d.apps = fake  # type: ignore[assignment]
    return fake


def call(d: Daemon, space: str, name: str, **args: Any) -> Dispatched:
    return dispatch(d, space, ToolCall("c1", name, dict(args)))


def test_her_tools_are_named_for_the_app_and_the_device(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Mix"})["id"]
    long_tool: AppTool = {"name": "x" * 60, "description": "Too long a name", "access": "auto"}
    wire(daemon, row(space, tools=[*LISTED, long_tool]), remotes={"app_q": [remote()]})
    offered = {t["function"]["name"]: t["function"] for t in apps_tools.offered(daemon, space)}
    assert list(offered) == [
        "queue__look",
        "queue__erase",
        "queue_on_studio_pc__look",
        "queue_on_studio_pc__erase",
        "app_fetch",
    ]  # a 67-character name is over the cap and not offered
    assert offered["queue__look"]["description"] == "Queue: Reads the queue."
    assert offered["queue_on_studio_pc__erase"]["description"] == (
        "Queue on Studio PC: Erases the queue. Needs the person's signature."
    )
    assert offered["queue__look"]["parameters"] == TOOLS[0]["inputSchema"]
    assert offered["app_fetch"]["parameters"]["properties"]["app"]["enum"] == ["queue", "queue_on_studio_pc"]
    assert apps_tools.offered(daemon, "") == []
    assert apps_tools.owns(daemon, space, "queue__look") and not apps_tools.owns(daemon, space, "queue__nope")


def test_a_tool_with_no_schema_takes_an_object(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Mix"})["id"]
    wire(daemon, row(space, tools=[{"name": "ping", "description": "", "access": "auto"}]))
    (ping, _fetch) = apps_tools.offered(daemon, space)
    assert ping["function"]["parameters"] == {"type": "object"}


def test_a_read_only_tool_runs_at_once(daemon: Daemon, app: HttpApp) -> None:
    space = daemon.spaces.create({"name": "Mix"})["id"]
    wire(daemon, row(space, app.url))
    done = call(daemon, space, "queue__look", q="today")
    assert done.card is None and not done.refused
    assert done.events == [{"type": "tool", "name": "app_read", "label": "Queue: look", "class": "auto"}]
    assert 'look ran with {"q": "today"}' in done.result and "not instructions" in done.result
    assert app.calls == [{"name": "look", "arguments": {"q": "today"}}]


def test_a_gated_tool_files_a_card_that_runs_once_when_signed(signing: Daemon, app: HttpApp) -> None:
    space = signing.spaces.create({"name": "Mix"})["id"]
    wire(signing, row(space, app.url))
    done = call(signing, space, "queue__erase")
    assert done.card is not None and done.card["action"] == "app_act"
    assert done.card["args"] == {"app_id": "app_q", "tool": "erase", "arguments": {}}
    assert [e["class"] for e in done.events if e["type"] == "tool"] == ["gated"]
    assert app.calls == []  # nothing until the signature
    signed = signing.gate.resolve(done.card["id"], "approve")
    assert signed["outcome"] == "Done. Queue answered: erase ran with {}"
    with pytest.raises(ApiError, match="already decided"):
        signing.gate.resolve(done.card["id"], "approve")
    assert len(app.calls) == 1


def test_an_app_that_went_away_is_marked_unreachable_and_keeps_its_tools(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Mix"})["id"]
    with HttpApp() as gone:
        url = gone.url
    fake = wire(daemon, row(space, url))
    done = call(daemon, space, "queue__look")
    assert done.refused and done.result == "Refused: Nothing answered at its address. Nothing ran."
    assert fake.probes == [("app_q", "unreachable", "Nothing answered at its address.")]
    assert "queue__look" in {t["function"]["name"] for t in apps_tools.offered(daemon, space)}


def test_a_remote_gated_call_carries_the_card_as_its_approval(
    signing: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    space = signing.spaces.create({"name": "Mix"})["id"]
    wire(signing, row(space), remotes={"app_q": [remote()]})
    sent: list[tuple[Any, ...]] = []

    def call_remote(
        _d: Daemon, peer_id: str, app_id: str, tool: str, arguments: dict[str, Any], approval_id: str | None
    ) -> AppAnswer:
        sent.append((peer_id, app_id, tool, arguments, approval_id))
        return {"text": "erased on B", "is_error": False}

    monkeypatch.setattr("athena.peer.apps.call_remote", call_remote)
    read = call(signing, space, "queue_on_studio_pc__look")
    assert read.card is None and read.events[0]["label"] == "Queue on Studio PC: look"
    done = call(signing, space, "queue_on_studio_pc__erase")
    assert done.card is not None and done.card["args"]["peer_id"] == "peer_b"
    signing.gate.resolve(done.card["id"], "approve")
    assert sent == [
        ("peer_b", "app_on_b", "look", {}, None),
        ("peer_b", "app_on_b", "erase", {}, done.card["id"]),
    ]


def test_app_fetch_brings_in_a_file_from_the_output_folder_only(tmp_path: Path) -> None:
    d = Daemon.open(tmp_path / "data")
    try:
        space = d.spaces.create({"name": "Mix"})["id"]
        out = tmp_path / "out"
        (out / "renders").mkdir(parents=True)
        (out / "renders" / "take1.wav").write_bytes(b"RIFF....")
        (tmp_path / "secret.txt").write_text("not yours")
        wire(d, row(space, output_dir=str(out)))
        outside = call(d, space, "app_fetch", app="queue", path="../secret.txt")
        assert outside.refused and "outside Queue's output folder" in outside.result
        kept = call(d, space, "app_fetch", app="queue", path="renders/take1.wav")
        assert not kept.refused and kept.events[0]["name"] == "app_fetch"
        file_id = kept.result.rsplit(" ", 1)[-1].rstrip(".")
        item = d.files.get(space, file_id)
        assert item["name"] == "take1.wav" and item["origin"] == "Queue"
        assert (out / "renders" / "take1.wav").exists()  # copied in, the app's own file stays
        assert call(d, space, "app_fetch", app="nope", path="x").refused
    finally:
        d.store.close()


def test_add_app_shows_a_command_word_for_word(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Mix"})["id"]
    argv = ["uvx", "queue-tool", "--root", "My Songs"]
    done = call(daemon, space, "add_app", kind="mcp_stdio", argv=argv, label="Queue")
    assert done.card is not None
    assert (
        done.card["label"]
        == 'Let this project start a tool with the command: uvx queue-tool --root "My Songs"'
    )
    assert done.card["args"] == {"kind": "mcp_stdio", "argv": argv, "label": "Queue"}
    http = call(daemon, space, "add_app", kind="mcp_http", address="http://example.com/mcp")
    assert http.refused and http.card is None
    old = call(daemon, space, "add_app", origin="https://studio.example")
    assert old.card is not None and old.card["args"] == {
        "kind": "website",
        "address": "https://studio.example",
    }


def test_the_mcp_server_offers_app_tools_with_their_class(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Mix"})["id"]
    wire(daemon, row(space))
    lease = daemon.mcp.mint(space)
    listed = mcp.handle(daemon, lease, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert listed is not None
    tools = {t["name"]: t["annotations"] for t in listed["result"]["tools"]}
    assert tools["queue__look"]["readOnlyHint"] is True and tools["queue__look"]["destructiveHint"] is False
    assert tools["queue__erase"]["readOnlyHint"] is False and tools["queue__erase"]["destructiveHint"] is True
    assert tools["app_fetch"]["readOnlyHint"] is False
    filed = mcp.call_tool(daemon, lease, "queue__erase", {})
    assert filed["isError"] is False and filed["structuredContent"]["pending"]["card_id"]


def test_a_signed_add_app_wires_the_app_by_its_kind(signing: Daemon) -> None:
    space = signing.spaces.create({"name": "Mix"})["id"]
    done = call(signing, space, "add_app", kind="mcp_stdio", argv=["queue-tool", "--serve"], label="Queue")
    assert done.card is not None
    signed = signing.gate.resolve(done.card["id"], "approve")
    assert signed["outcome"] == "Added Queue to the project."
    (wired,) = signing.apps.rows(space)
    assert wired.kind == "mcp_stdio" and wired.argv == ["queue-tool", "--serve"]


def test_a_schema_with_a_top_level_one_of_is_flattened_for_the_model() -> None:
    # Gravitone's tools are a oneOf per op; an engine refuses a top-level combinator (seam, 2026-11-04).
    from athena.apps.tools import flat_schema

    schema = {
        "type": "object",
        "properties": {"op": {"type": "string", "enum": ["status", "pause"]}},
        "required": ["op"],
        "oneOf": [
            {"type": "object", "properties": {"op": {"const": "status"}, "jobId": {"type": "string"}}},
            {"type": "object", "properties": {"op": {"const": "pause"}, "jobId": {"type": "string"}}},
        ],
    }
    flat = flat_schema(schema)
    assert not any(k in flat for k in ("oneOf", "anyOf", "allOf"))
    assert flat["properties"]["op"]["enum"] == ["status", "pause"]
    assert flat["properties"]["jobId"] == {"type": "string"}
    assert flat["required"] == ["op"]
    plain = {"type": "object", "properties": {"q": {"type": "string"}}}
    assert flat_schema(plain) is plain
    assert flat_schema(None) == {"type": "object"}
