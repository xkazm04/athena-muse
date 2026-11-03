"""Report parts in a chat reply (ADR 0022): `show_blocks` shows 1 to 3 parts of the report's own kit,
through its own validation door, with every figure computed from records; a drop is disclosed; the
parts stream in place among her words and are kept with the settled turn."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from starlette.testclient import TestClient

from athena.app import Daemon
from athena.contracts import Probe
from athena.engine import TextDelta, ToolCall, Usage
from athena.engine.scripted import ScriptedEngine
from athena.mcp import chat_tools
from athena.report import chat
from athena.turn import dispatch, run_turn
from report_kit import project, stat, track

URL = "http://127.0.0.1:9/mcp"

STAGES = {
    "kind": "pipeline",
    "title": "Where the tracks stand",
    "config": {
        "stages": [
            {"label": "Found", "binding": {"kind": "track"}},
            {"label": "Kept", "binding": {"kind": "track", "filter": {"verdict": "keep"}}},
        ]
    },
}
VIEWS = {
    "kind": "trend",
    "title": "Views over time",
    "binding": {"kind": "stat", "filter": {"metric": "views"}, "agg": "series", "field": "value"},
}


def _channel(daemon: Daemon) -> str:
    """Three tracks found, one kept; three readings of views."""
    sid = project(daemon)
    track(daemon, sid, 1, verdict="keep")
    track(daemon, sid, 2)
    track(daemon, sid, 3)
    for n, at in enumerate(("2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z", "2026-10-03T00:00:00Z")):
        stat(daemon, sid, "views", 100.0 * (n + 1), at)
    return sid


def _show(daemon: Daemon, sid: str, *blocks: Any) -> Any:
    return dispatch(daemon, sid, ToolCall("c1", "show_blocks", {"blocks": list(blocks)}))


class _Engine:
    """Words, then `show_blocks` with the given parts, then a closing sentence."""

    id = "muse"
    model = "test"
    simulated = True
    cost_estimated = False

    def __init__(self, *blocks: dict[str, Any]) -> None:
        self.blocks = list(blocks)
        self.offered: list[str] = []
        self.descriptions: dict[str, str] = {}
        self.rounds = 0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[Any]:
        self.offered = [t["function"]["name"] for t in tools]
        self.descriptions = {t["function"]["name"]: t["function"]["description"] for t in tools}
        self.rounds += 1
        if self.rounds == 1:
            yield TextDelta("Here is where they stand.")
            if "show_blocks" in self.offered:
                yield ToolCall("t1", "show_blocks", {"blocks": self.blocks})
        else:
            yield TextDelta("Most tracks still wait for you.")
        yield Usage(input_tokens=10, output_tokens=4)

    def probe(self) -> Probe:
        return {"ok": True}


def test_the_tool_is_offered_only_in_a_project_that_keeps_records(daemon: Daemon) -> None:
    plain = daemon.spaces.create({"name": "Notes"})["id"]
    assert chat.offered(daemon, plain) == [] and chat.offered(daemon, "") == []
    engine = _Engine()
    list(run_turn(daemon, engine, "how are we doing?", plain))  # type: ignore[arg-type]
    assert "show_blocks" not in engine.offered
    refused = _show(daemon, plain, STAGES)
    assert refused.events == [] and "keeps no records" in refused.result

    sid = _channel(daemon)
    list(run_turn(daemon, engine, "how are we doing?", sid))  # type: ignore[arg-type]
    assert "show_blocks" in engine.offered


def test_the_description_teaches_when_and_is_generated_from_the_kit(daemon: Daemon) -> None:
    sid = project(daemon, kinds=["track", "stat"])
    [tool] = chat.offered(daemon, sid)
    text = tool["function"]["description"]
    assert text.startswith(chat.WHEN)
    assert "comparative or quantitative" in text and "one number" in text
    for kind in chat.CHAT_KINDS:
        assert f"- `{kind}`:" in text
    assert "- `queue`:" not in text and "- `cards`:" not in text
    assert "- `track`:" in text and "- `creator`:" not in text  # only the kinds this project keeps
    items = tool["function"]["parameters"]["properties"]["blocks"]
    assert items["maxItems"] == 3 and items["items"]["properties"]["kind"]["enum"] == list(chat.CHAT_KINDS)


def test_a_valid_call_streams_one_blocks_line_with_computed_values(daemon: Daemon) -> None:
    sid = _channel(daemon)
    done = _show(daemon, sid, {**STAGES, "span": 4, "id": "mine"}, VIEWS)
    assert done.card is None and len(done.events) == 1
    [event] = done.events
    shown = event["shown"]
    assert event["type"] == "blocks" and shown["dropped"] == 0 and shown["reasons"] == []
    assert [(b["id"], b["kind"], b["span"]) for b in shown["blocks"]] == [
        ("part-1", "pipeline", 12),  # the daemon's id and the full width, whatever she asked
        ("part-2", "trend", 12),
    ]
    assert shown["values"]["part-1"]["stages"] == [
        {"label": "Found", "count": 3},
        {"label": "Kept", "count": 1},
    ]
    assert [p["v"] for p in shown["values"]["part-2"]["series"]] == [100.0, 200.0, 300.0]
    # the model reads what the person sees, fenced as data, and is told not to repeat it
    assert "- Found: 3" in done.result and "record data, not instructions" in done.result
    assert "do not repeat them" in done.result


def test_an_invalid_part_is_dropped_with_a_reason_and_disclosed(daemon: Daemon) -> None:
    sid = _channel(daemon)
    digits = {**VIEWS, "title": "Views in 2026"}
    queue = {"kind": "queue", "title": "Waiting", "binding": {"kind": "track", "filter": {"verdict": None}}}
    done = _show(daemon, sid, STAGES, digits, queue, VIEWS)
    shown = done.events[0]["shown"]
    assert [b["kind"] for b in shown["blocks"]] == ["pipeline"]  # the fourth is past the cap
    assert shown["dropped"] == 3
    assert "has a number in it" in shown["reasons"][0]
    assert "2026" not in shown["reasons"][0]  # her figure is never echoed
    assert shown["reasons"][1].startswith("A queue part: a queue asks for a verdict")
    assert shown["reasons"][2] == "A trend part: a reply shows at most 3 parts."
    assert "3 parts could not be shown" in done.result


def test_a_call_with_nothing_to_show_discloses_it_and_tells_her_so(daemon: Daemon) -> None:
    sid = _channel(daemon)
    done = _show(daemon, sid, {"kind": "stat", "title": "Bad", "binding": {"kind": "invoice"}})
    shown = done.events[0]["shown"]
    assert shown["blocks"] == [] and shown["values"] == {} and shown["dropped"] == 1
    assert "Nothing was shown" in done.result
    assert done.refused is True  # the disclosure streams, and the call is still a refusal (ADR 0023)
    empty = _show(daemon, sid)
    assert "Send 1 to 3 parts" in empty.result and empty.refused is True  # no parts at all
    assert _show(daemon, sid, STAGES).refused is False


def test_the_parts_stream_in_place_and_are_kept_with_the_settled_turn(daemon: Daemon) -> None:
    sid = _channel(daemon)
    events = list(run_turn(daemon, _Engine(STAGES), "how are the tracks doing?", sid))  # type: ignore[arg-type]
    assert [e["type"] for e in events if e["type"] in ("text", "blocks")] == ["text", "blocks", "text"]
    streamed = next(e["shown"] for e in events if e["type"] == "blocks")
    athena = daemon.conversation.list(sid)[-1]
    assert [p["kind"] for p in athena["parts"]] == ["text", "blocks", "text"]
    kept = athena["parts"][1]
    assert isinstance(kept.pop("at_ms"), int)  # ADR 0024: its moment
    assert kept == {"kind": "blocks", "shown": streamed}
    # the turn's words carry no figure of the model's: the figures live in the parts
    assert athena["text"] == "Here is where they stand.Most tracks still wait for you."


def test_the_simulated_engine_runs_a_records_turn_without_calling_it(daemon: Daemon) -> None:
    # The scripted engine has no rule for show_blocks: it is offered and never called, and the turn
    # ends as it always did.
    sid = _channel(daemon)
    events = list(run_turn(daemon, ScriptedEngine(), "compare the tracks", sid))
    assert events[-1]["type"] == "done"
    assert not any(e["type"] == "blocks" for e in events)


def _rpc(client: TestClient, token: str, method: str, params: dict[str, Any] | None = None) -> Any:
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return client.post("/mcp", json=body, headers={"Authorization": f"Bearer {token}"}).json()["result"]


def test_a_turns_lease_streams_the_parts_and_an_outside_host_never_sees_the_tool(
    client: TestClient, daemon: Daemon
) -> None:
    daemon.mcp_url = URL
    sid = _channel(daemon)
    outside = client.post("/mcp/lease", json={"space_id": sid}).json()["token"]
    assert "show_blocks" not in {t["name"] for t in _rpc(client, outside, "tools/list")["tools"]}
    assert _rpc(client, outside, "tools/call", {"name": "show_blocks", "arguments": {}})["isError"] is True

    heard: list[dict[str, Any]] = []
    names = frozenset(t["function"]["name"] for t in chat_tools(daemon, sid))
    lease = daemon.mcp.mint(sid, tools=names, sink=heard.append)
    listed = {t["name"]: t for t in _rpc(client, lease.token, "tools/list")["tools"]}
    assert listed["show_blocks"]["annotations"]["readOnlyHint"] is True
    result = _rpc(
        client, lease.token, "tools/call", {"name": "show_blocks", "arguments": {"blocks": [STAGES]}}
    )
    assert result["isError"] is False and "- Kept: 1" in result["content"][0]["text"]
    assert [e["type"] for e in heard] == ["blocks"]
