"""The app client (ADR 0025): an app answering at a loopback address and a tool started as a child
process each list their tools with their class; a call answers; the token stays in its header; a child
is reaped when unused and at shutdown, and a dead one is started again once."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from apps_fake import HttpApp, stdio_argv
from athena.apps.client import AppClients, access_of
from athena.apps.store import AppRow
from athena.contracts import APP_IDLE_S

TOKEN = "tok_" + "s3cret" * 4


def http_row(url: str) -> AppRow:
    return AppRow("app_http", "spc_1", "mcp_http", "Queue", "queue", url, "unchecked")


def stdio_row(*flags: str) -> AppRow:
    argv = stdio_argv(*flags)
    return AppRow("app_cli", "spc_1", "mcp_stdio", "Queue", "queue", " ".join(argv), "unchecked", argv=argv)


@pytest.fixture
def clients() -> Iterator[AppClients]:
    c = AppClients()
    yield c
    c.shutdown()


def by_name(tools: list[dict[str, object]]) -> dict[str, object]:
    return {str(t["name"]): t["access"] for t in tools}


def test_the_class_comes_from_the_annotations_and_fails_closed() -> None:
    assert access_of({"readOnlyHint": True}) == "auto"
    assert access_of({"destructiveHint": False, "openWorldHint": False}) == "auto"
    assert access_of({"destructiveHint": False}) == "gated"  # open world by default
    assert access_of({"readOnlyHint": "true"}) == "gated"  # only the JSON boolean counts
    assert access_of(None) == "gated"


def test_an_http_app_is_probed_and_called(clients: AppClients) -> None:
    with HttpApp() as app:
        probe = clients.probe(http_row(app.url), TOKEN)
        assert probe.status == "ok" and probe.reason is None
        assert by_name(probe.tools) == {"look": "auto", "erase": "gated"}  # type: ignore[arg-type]
        assert probe.tools[0]["input_schema"]["properties"] == {"q": {"type": "string"}}
        answer = clients.call(http_row(app.url), TOKEN, "look", {"q": "x"})
        assert answer == {"text": 'look ran with {"q": "x"}', "is_error": False}
        assert app.calls == [{"name": "look", "arguments": {"q": "x"}}]
        assert set(app.auth) == {f"Bearer {TOKEN}"}  # the token rides in its header, every request


def test_a_stdio_app_is_probed_and_called(clients: AppClients) -> None:
    probe = clients.probe(stdio_row(), None)
    assert probe.status == "ok"
    assert by_name(probe.tools) == {"look": "auto", "erase": "gated"}  # type: ignore[arg-type]
    answer = clients.call(stdio_row(), None, "erase", {})
    assert answer == {"text": "erase ran with {}", "is_error": False}


def test_an_address_off_this_computer_is_refused(clients: AppClients) -> None:
    for url in ("http://example.com/mcp", "http://10.0.0.5:8080/mcp", "ftp://127.0.0.1/mcp"):
        probe = clients.probe(http_row(url), TOKEN)
        assert probe.status == "refused" and probe.tools == []
        assert probe.reason == "Athena calls an app only at an address on this computer."
        answer, reached = clients.attempt(http_row(url), TOKEN, "look", {})
        assert answer["is_error"] and not reached


def test_an_app_that_is_down_answers_unreachable_without_raising(clients: AppClients) -> None:
    with HttpApp() as app:
        url = app.url
    probe = clients.probe(http_row(url), TOKEN)
    assert probe.status == "unreachable" and probe.reason == "Nothing answered at its address."
    missing = AppRow(
        "app_x", "spc_1", "mcp_stdio", "X", "x", "nope", "unchecked", argv=["no-such-cmd-athena"]
    )
    probe = clients.probe(missing, None)
    assert probe.status == "unreachable" and "was not found" in (probe.reason or "")


def test_a_token_the_app_quotes_back_is_never_in_the_answer(clients: AppClients) -> None:
    with HttpApp(echo_auth=True) as app:
        answer, reached = clients.attempt(http_row(app.url), TOKEN, "look", {})
    assert reached and answer["is_error"]
    assert TOKEN not in answer["text"] and "[redacted]" in answer["text"]


def child_of(clients: AppClients, app_id: str = "app_cli"):  # type: ignore[no-untyped-def]
    slot = clients._stdio[app_id]
    assert slot.child is not None
    return slot.child.proc


def test_an_unused_child_is_reaped_after_the_idle_time() -> None:
    now = [1000.0]
    clients = AppClients(clock=lambda: now[0])
    try:
        assert clients.probe(stdio_row(), None).status == "ok"
        proc = child_of(clients)
        now[0] += APP_IDLE_S - 1
        clients.reap_idle()
        assert proc.poll() is None  # still in its idle time
        now[0] += 2
        clients.reap_idle()
        assert proc.poll() is not None and clients._stdio["app_cli"].child is None
        # the next use starts it again
        assert clients.call(stdio_row(), None, "look", {})["is_error"] is False
    finally:
        clients.shutdown()


def test_shutdown_ends_every_child() -> None:
    clients = AppClients()
    clients.probe(stdio_row(), None)
    proc = child_of(clients)
    assert proc.poll() is None
    clients.shutdown()
    assert proc.poll() is not None


def test_a_dead_child_is_started_again_once(clients: AppClients) -> None:
    clients.probe(stdio_row(), None)
    first = child_of(clients)
    first.kill()
    first.wait(timeout=10)
    assert clients.call(stdio_row(), None, "look", {}) == {"text": "look ran with {}", "is_error": False}
    assert child_of(clients).pid != first.pid


def test_a_child_that_keeps_dying_answers_unreachable(clients: AppClients) -> None:
    row = stdio_row("--crash-on-call")
    assert clients.probe(row, None).status == "ok"
    died, reached = clients.attempt(row, None, "look", {})
    assert not reached and "the fake fell over" in died["text"]  # its last words are the reason
    again, reached = clients.attempt(row, None, "look", {})  # started again once, and it dies again
    assert not reached and again["is_error"]
    spent, reached = clients.attempt(row, None, "look", {})
    assert not reached and "stopped again" in spent["text"]
    assert clients._stdio["app_cli"].child is None  # nothing was started for the third
    assert clients.probe(row, None).status == "ok"  # checking it again starts it afresh
