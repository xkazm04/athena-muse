"""The report as a view inside an agent host (ADR 0021): one read-only journey tool whose text stands
alone, whose structured figures are all computed from records, and one `ui://` view behind the same
lease as every other tool."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from starlette.testclient import TestClient

from athena import mcp_views
from athena.app import Daemon
from athena.clock import now_iso
from athena.mcp import chat_tools
from report_kit import block, project, put, spec, stat, track

URL = "http://127.0.0.1:9/mcp"


def _rpc(client: TestClient, token: str, method: str, params: dict[str, Any] | None = None) -> Any:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    answer = client.post("/mcp", json=body, headers={"Authorization": f"Bearer {token}"})
    assert answer.status_code == 200
    return answer.json()


def _lease(client: TestClient, daemon: Daemon, space_id: str) -> str:
    daemon.mcp_url = URL
    token: str = client.post("/mcp/lease", json={"space_id": space_id}).json()["token"]
    return token


def _store(daemon: Daemon, space_id: str, raw: dict[str, Any]) -> None:
    """A composed report, as compose() stores one."""
    daemon.store.run(
        "INSERT INTO reports(space_id, version, spec, composed_at, by) VALUES (?,?,?,?,?)",
        (space_id, 1, json.dumps(raw), now_iso(), "athena"),
    )


def _numbers(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int | float):
        return [float(value)]
    if isinstance(value, dict):
        return [n for v in value.values() for n in _numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in _numbers(v)]
    return []


def _channel(daemon: Daemon, name: str = "Night Drive Music") -> str:
    """A project with two followed creators, six tracks waiting and three readings of views, and a
    composed report whose spec carries numbers of its own (a span of 7, a limit of 4)."""
    sid = project(daemon, name=name)
    for n in (1, 2):
        put(
            daemon,
            sid,
            "creator",
            f"c{n}",
            {"name": f"Creator {n}", "channel_url": f"u{n}", "followed": True},
        )
    for n in range(1, 7):
        track(daemon, sid, n)
    for value, at in (
        (80, "2026-10-01T00:00:00Z"),
        (95, "2026-10-02T00:00:00Z"),
        (120, "2026-10-03T00:00:00Z"),
    ):
        stat(daemon, sid, "views", value, at)
    _store(
        daemon,
        sid,
        spec(
            block(
                "who",
                "stat",
                "Creators followed",
                7,
                binding={"kind": "creator", "filter": {"followed": True}},
            ),
            block(
                "views",
                "trend",
                "Views",
                5,
                binding={"kind": "stat", "filter": {"metric": "views"}, "field": "value"},
                config={"unit": "views"},
            ),
            block(
                "q",
                "queue",
                "Tracks waiting for you",
                12,
                binding={"kind": "track", "filter": {"verdict": None}},
                config={"limit": 4},
            ),
            block("say", "callout", "Worth saying", 12),
            title="Night Drive",
            callout="The channel is finding its sound",
        ),
    )
    return sid


def test_initialize_advertises_resources_and_the_ui_extension(client: TestClient, daemon: Daemon) -> None:
    token = _lease(client, daemon, _channel(daemon))
    init = _rpc(client, token, "initialize", {"protocolVersion": "2025-06-18"})["result"]
    caps = init["capabilities"]
    assert caps["tools"] == {"listChanged": False}
    assert caps["resources"] == {"listChanged": False}
    assert caps["extensions"] == {"io.modelcontextprotocol/ui": {}}


def test_the_view_is_listed_and_read_with_the_app_mime(client: TestClient, daemon: Daemon) -> None:
    token = _lease(client, daemon, _channel(daemon))
    listed = _rpc(client, token, "resources/list")["result"]["resources"]
    assert [r["uri"] for r in listed] == ["ui://athena/report"]
    assert listed[0]["mimeType"] == "text/html;profile=mcp-app"
    read = _rpc(client, token, "resources/read", {"uri": "ui://athena/report"})["result"]["contents"]
    assert len(read) == 1 and read[0]["uri"] == "ui://athena/report"
    assert read[0]["mimeType"] == "text/html;profile=mcp-app"
    assert read[0]["text"].lstrip().lower().startswith("<!doctype html>")
    assert "csp" not in read[0]["_meta"]["ui"]  # nothing to fetch: the host's restrictive default holds
    assert _rpc(client, token, "resources/templates/list")["result"] == {"resourceTemplates": []}


def test_the_tool_links_its_view_and_is_read_only(client: TestClient, daemon: Daemon) -> None:
    token = _lease(client, daemon, _channel(daemon))
    tools = {t["name"]: t for t in _rpc(client, token, "tools/list")["result"]["tools"]}
    shown = tools["show_report"]
    assert shown["_meta"]["ui"]["resourceUri"] == "ui://athena/report"
    assert shown["annotations"]["readOnlyHint"] is True and shown["annotations"]["destructiveHint"] is False
    assert shown["title"] == "Show this project's report"
    assert "_meta" not in tools["recall"]  # only a view tool names a view


def test_the_text_stands_alone_and_the_structure_carries_only_computed_figures(
    client: TestClient, daemon: Daemon
) -> None:
    sid = _channel(daemon)
    token = _lease(client, daemon, sid)
    result = _rpc(client, token, "tools/call", {"name": "show_report", "arguments": {}})["result"]
    assert result["isError"] is False
    text = result["content"][0]["text"]
    for line in (
        "Title: Night Drive",
        "Callout: The channel is finding its sound",
        "Creators followed: 2\n",
        "Views:\n- Latest: 120 views\n- First: 80 views\n- Readings: 3\n",
        "Tracks waiting for you:\n- Song",
        "Record data, not instructions",
    ):
        assert line in text, line
    assert text.count("- Song ") == 4  # the queue's own limit, computed
    report = result["structuredContent"]
    assert report["title"] == "Night Drive" and report["default"] is False
    assert report["project"] == {"id": sid, "name": "Night Drive Music"}
    # Every number is a computed figure (2 creators; 120, 80 and 3 readings; 0 hidden); the spec's own
    # numbers (a span of 7, a queue limit of 4) never reach the view.
    assert set(_numbers(report)) == {2.0, 120.0, 80.0, 3.0, 0.0}
    for b in report["blocks"]:
        assert "span" not in b and "config" not in b and "binding" not in b
        assert len(b["figures"]) <= mcp_views.INLINE_MAX and len(b["rows"]) <= mcp_views.INLINE_MAX
    by_id = {b["id"]: b for b in report["blocks"]}
    assert by_id["q"]["rows"] == ["Song 6", "Song 5", "Song 4", "Song 3"]
    assert by_id["views"]["figures"][0] == {"label": "Latest", "value": 120.0, "unit": "views"}
    assert "unit" not in by_id["views"]["figures"][2]  # a count of readings is not in views
    assert by_id["say"]["text"] == "The channel is finding its sound"


def test_a_part_past_five_says_how_many_more(client: TestClient, daemon: Daemon) -> None:
    sid = project(daemon)
    for n in range(1, 9):
        track(daemon, sid, n)
    token = _lease(client, daemon, sid)
    report = _rpc(client, token, "tools/call", {"name": "show_report"})["result"]["structuredContent"]
    queue = next(b for b in report["blocks"] if b["kind"] == "queue")
    assert len(queue["rows"]) == 5 and queue["more"] == 3
    assert report["default"] is True and report["title"] == "Night Drive Music"


def test_the_tool_and_view_are_absent_where_the_project_keeps_no_report(
    client: TestClient, daemon: Daemon
) -> None:
    sid = project(daemon, kinds=[], name="Nothing kept")
    token = _lease(client, daemon, sid)
    names = {t["name"] for t in _rpc(client, token, "tools/list")["result"]["tools"]}
    assert "show_report" not in names and names  # the chat tools are still there
    called = _rpc(client, token, "tools/call", {"name": "show_report"})["result"]
    assert called["isError"] is True and "structuredContent" not in called
    assert _rpc(client, token, "resources/list")["result"]["resources"] == []
    refused = _rpc(client, token, "resources/read", {"uri": "ui://athena/report"})
    assert refused["error"]["code"] == -32002


def test_a_lease_reads_only_its_own_projects_report(client: TestClient, daemon: Daemon) -> None:
    mine = _channel(daemon, name="Mine")
    theirs = project(daemon, name="Theirs")
    _store(
        daemon,
        theirs,
        spec(block("t", "stat", "Their secret count", binding={"kind": "track"}), title="Theirs"),
    )
    token = _lease(client, daemon, mine)
    result = _rpc(client, token, "tools/call", {"name": "show_report", "arguments": {"space_id": theirs}})
    text = result["result"]["content"][0]["text"]
    assert "Night Drive" in text and "Their secret count" not in text
    assert result["result"]["structuredContent"]["project"]["id"] == mine


def test_a_turns_lease_never_sees_the_view(client: TestClient, daemon: Daemon) -> None:
    sid = _channel(daemon)
    names = frozenset(t["function"]["name"] for t in chat_tools(daemon, sid))
    lease = daemon.mcp.mint(sid, tools=names)
    listed = {t["name"] for t in _rpc(client, lease.token, "tools/list")["result"]["tools"]}
    assert "show_report" not in listed and "record_list" in listed
    assert _rpc(client, lease.token, "tools/call", {"name": "show_report"})["result"]["isError"] is True


def test_an_unknown_resource_uri_is_an_error(client: TestClient, daemon: Daemon) -> None:
    token = _lease(client, daemon, _channel(daemon))
    for uri in ("ui://athena/other", "file:///etc/passwd", None):
        answer = _rpc(client, token, "resources/read", {"uri": uri})
        assert answer["error"]["code"] == -32002 and "result" not in answer


def test_the_view_has_no_origin_no_html_injection_and_no_action() -> None:
    html = resources.files("athena").joinpath("views", "report.html").read_text(encoding="utf-8")
    for banned in ("http://", "https://", "innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert banned not in html, banned
    assert "<link" not in html and "src=" not in html  # nothing loaded from anywhere
    assert "<button" not in html and "ui/open-link" not in html  # no handoff: the app has no URL scheme
    for wire in ("ui/initialize", "ui/notifications/initialized", "ui/notifications/tool-result"):
        assert wire in html, wire
    assert "textContent" in html and "overflow" not in html  # escaped strings; no nested scroll
