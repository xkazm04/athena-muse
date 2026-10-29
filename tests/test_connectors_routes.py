"""Every connector route answers its contract shape, in plain words, and never with a secret: the list,
Google's sign-in from Connect to the browser's callback, a sign-in refused, run out or turned down by
Google, a Notion key, the probe and disconnect. Google and Notion are fakes; the browser is a list."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import contracts
from athena.app import Daemon
from athena.connectors.part import Connectors
from athena.contracts import ConnectFlow, Connection, ConnectionList
from connectors_kit import (
    ACCOUNT,
    CLIENT_ID,
    CLIENT_SECRET,
    NOTION_KEY,
    FakeProvider,
    assert_plain,
    callback,
    conforms,
    connectors_over,
    google,
    state_of,
)

SECRETS = (CLIENT_SECRET, NOTION_KEY, "ya29.test_access", "1//test_refresh")


def notion_me(*_: Any) -> tuple[int, Any]:
    return 200, {"id": "0123456789abcdef0123456789abcdef", "name": "Test User"}


class Setup:
    def __init__(self, daemon: Daemon, client: TestClient, root: Path, script: Any = None) -> None:
        self.provider = FakeProvider(script=script)
        self.opened: list[str] = []
        self.root = root
        daemon.connectors = connectors_over(root, self.provider, self.opened)
        self.connectors: Connectors = daemon.connectors
        self.client = client
        self.answers: list[str] = []

    def call(self, method: str, key: str, kind: str = "gmail", body: Any = None) -> Any:
        url = contracts.ROUTES[key].format(kind=kind)
        r = self.client.request(method, url, json=body)
        self.answers.append(r.text)
        return r

    def connect(self, kind: str, body: dict[str, str]) -> ConnectFlow:
        r = self.call("POST", "connector_connect", kind, body)
        assert r.status_code == 200, r.text
        conforms(r.json(), ConnectFlow)
        flow: ConnectFlow = r.json()
        assert_plain(flow.get("detail", ""))
        return flow

    def flow(self, kind: str = "gmail") -> ConnectFlow:
        r = self.call("GET", "connector_flow", kind)
        assert r.status_code == 200, r.text
        conforms(r.json(), ConnectFlow)
        assert_plain(r.json().get("detail", ""))
        return r.json()  # type: ignore[no-any-return]

    def settled(self, kind: str = "gmail") -> ConnectFlow:
        sign_in = self.connectors.vault.flows.for_connector(kind)
        assert sign_in is not None and sign_in.wait(5)
        return self.flow(kind)

    def connection(self, kind: str) -> Connection:
        r = self.call("GET", "connectors")
        assert r.status_code == 200, r.text
        conforms(r.json(), ConnectionList)
        listed: list[Connection] = r.json()["connections"]
        assert [c["kind"] for c in listed] == ["gmail", "notion"]
        for found in listed:
            conforms(found, Connection)
            assert_plain(found.get("problem", ""))
        return next(c for c in listed if c["kind"] == kind)

    def act(self, key: str, kind: str) -> Connection:
        r = self.call("POST", key, kind)
        assert r.status_code == 200, r.text
        conforms(r.json(), Connection)
        assert_plain(r.json().get("problem", ""))
        return r.json()  # type: ignore[no-any-return]


@pytest.fixture
def setup(daemon: Daemon, client: TestClient, tmp_path: Path) -> Iterator[Setup]:
    built = Setup(daemon, client, tmp_path / "connectors", google(extra=notion_me))
    yield built
    built.connectors.close()
    # No answer and no record on disk ever carries a secret. (The test seal is the owner-only file, so
    # the sealed directory is left out here; the platform seal's ciphertext is test_connectors_seal's.)
    on_disk = [p.read_bytes() for p in built.root.rglob("*") if p.is_file() and p.parent.name != "sealed"]
    for secret in SECRETS:
        assert all(secret not in text for text in built.answers), secret
        assert all(secret.encode() not in blob for blob in on_disk), secret


# -- the list -------------------------------------------------------------------------------------


def test_nothing_is_connected_on_a_fresh_daemon_and_nothing_is_dialled(
    client: TestClient, daemon: Daemon
) -> None:
    r = client.get("/connectors")
    assert r.status_code == 200
    conforms(r.json(), ConnectionList)
    seen = r.json()["connections"]
    assert [{k: v for k, v in c.items() if k != "guide"} for c in seen] == [
        {"kind": "gmail", "status": "disconnected", "writes": False},
        {"kind": "notion", "status": "disconnected", "writes": False},
    ]
    # Until connected, each says how to connect: Gmail names the person's own Google client.
    assert "Google client" in seen[0]["guide"] and seen[1]["guide"]
    # A daemon with no data dir reaches no service: a key is refused without leaving the process.
    flow = client.post("/connectors/notion/connect", json={"key": NOTION_KEY}).json()
    assert flow["state"] == "failed" and "could not be reached" in flow["detail"]
    assert client.get("/connectors").json()["connections"][1]["status"] == "disconnected"


def test_an_unknown_kind_is_a_404_on_every_route(client: TestClient) -> None:
    for method, key in (
        ("POST", "connector_connect"),
        ("GET", "connector_flow"),
        ("POST", "connector_disconnect"),
        ("POST", "connector_probe"),
    ):
        r = client.request(method, contracts.ROUTES[key].format(kind="slack"), json={})
        assert r.status_code == 404 and r.json()["error"] == "unknown_ref", key


def test_the_routes_are_behind_the_token(client: TestClient) -> None:
    r = client.get("/connectors", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


# -- Google's sign-in -----------------------------------------------------------------------------


def test_google_sign_in_from_connect_to_connected(setup: Setup) -> None:
    assert setup.flow() == {"state": "idle"}
    flow = setup.connect("gmail", {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET})
    url = flow.pop("url")
    assert flow == {"state": "waiting", "detail": "Finish signing in with Google in your browser."}
    # The sign-in page, for when the browser did not open: Google's page, never the client secret.
    assert url.startswith("https://accounts.google.com/") and CLIENT_SECRET not in url
    (url,) = setup.opened
    assert url.startswith("https://accounts.google.com/") and "gmail.send" in url
    assert setup.flow()["state"] == "waiting"
    assert setup.connection("gmail")["status"] == "disconnected"

    status, page = callback(url, state=state_of(url), code="the-code")
    assert status == 200 and "connected" in page
    assert setup.settled() == {"state": "done", "detail": f"Connected as {ACCOUNT}."}

    exchange = next(s for s in setup.provider.seen if s.path == "/token")
    assert exchange.form["code"] == "the-code" and exchange.form["client_secret"] == CLIENT_SECRET
    assert exchange.form["code_verifier"], "the sign-in proves it began here"
    gmail = setup.connection("gmail")
    assert gmail["status"] == "connected" and gmail["account"] == ACCOUNT
    assert gmail["writes"] is False, "a connection is created read-only"
    assert gmail["last_checked"] and "problem" not in gmail


def test_a_second_sign_in_reuses_the_kept_client(setup: Setup) -> None:
    setup.connect("gmail", {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET})
    callback(setup.opened[0], state=state_of(setup.opened[0]), code="c1")
    assert setup.settled()["state"] == "done"
    assert setup.connect("gmail", {})["state"] == "waiting"
    callback(setup.opened[1], state=state_of(setup.opened[1]), code="c2")
    assert setup.settled()["state"] == "done"
    second = [s for s in setup.provider.seen if s.path == "/token"][-1]
    assert second.form["client_id"] == CLIENT_ID and second.form["code"] == "c2"


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ({}, "Paste the client id and the client secret"),
        ({"client_id": CLIENT_ID}, "Paste both"),
        ({"key": NOTION_KEY}, "not with a key"),
        ({"client_id": 7, "client_secret": "x"}, "as text"),
        ({"client_id": "x", "client_secret": "y", "scope": "all"}, "as text"),
        ({"client_id": "x" * 600, "client_secret": "y"}, "too long"),
    ],
)
def test_a_connect_body_that_cannot_be_used_is_a_400(setup: Setup, body: dict[str, Any], said: str) -> None:
    r = setup.call("POST", "connector_connect", "gmail", body)
    assert r.status_code == 400 and r.json()["error"] == "bad_request"
    assert said in r.json()["reason"]
    assert setup.opened == []


def test_a_sign_in_turned_down_on_googles_page_keeps_nothing(setup: Setup) -> None:
    setup.connect("gmail", {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET})
    status, page = callback(setup.opened[0], state=state_of(setup.opened[0]), error="access_denied")
    assert status == 200 and "could not finish" in page
    assert setup.settled() == {
        "state": "failed",
        "detail": "You said no on Google's page, so nothing was connected.",
    }
    assert setup.connection("gmail")["status"] == "disconnected"
    assert not setup.connectors.vault.client_kept("gmail"), "a failed sign-in seals nothing"


def test_a_sign_in_left_unanswered_runs_out(setup: Setup) -> None:
    setup.connect("gmail", {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET})
    sign_in = setup.connectors.vault.flows.for_connector("gmail")
    assert sign_in is not None
    sign_in.ttl_s = 0.0  # the page has been open longer than a sign-in may wait
    assert setup.settled() == {
        "state": "failed",
        "detail": "Google's page was not answered in time. Try again.",
    }
    assert setup.connection("gmail")["status"] == "disconnected"


def test_a_sign_in_google_will_not_exchange_fails_in_plain_words(
    daemon: Daemon, client: TestClient, tmp_path: Path
) -> None:
    setup = Setup(daemon, client, tmp_path / "connectors", google(token_status=400))
    setup.connect("gmail", {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET})
    callback(setup.opened[0], state=state_of(setup.opened[0]), code="stale")
    flow = setup.settled()
    assert flow["state"] == "failed" and "Check the client id and secret" in flow.get("detail", "")
    assert setup.connection("gmail")["status"] == "disconnected"
    assert list((tmp_path / "connectors" / "sealed").glob("*")) == []
    setup.connectors.close()


def test_an_expired_grant_google_will_not_renew_asks_to_sign_in_again(
    daemon: Daemon, client: TestClient, tmp_path: Path
) -> None:
    setup = Setup(daemon, client, tmp_path / "connectors", google(token_status=400))
    vault = setup.connectors.vault
    vault._admit(vault.specs["gmail"], "ya29.access", refresh="1//r", expires_in=1, client=("cid", "cs"))
    gmail = setup.act("connector_probe", "gmail")
    assert gmail["status"] == "needs_sign_in"
    assert gmail.get("problem") == "Google asked you to sign in again."
    assert setup.connection("gmail") == gmail


# -- a Notion key ---------------------------------------------------------------------------------


def test_a_notion_key_is_checked_at_once_and_kept_only_when_accepted(setup: Setup) -> None:
    flow = setup.connect("notion", {"key": NOTION_KEY})
    assert flow == {"state": "done", "detail": "Connected as Test User."}
    assert setup.flow("notion") == {"state": "idle"}
    notion = setup.connection("notion")
    assert notion["status"] == "connected" and notion["account"] == "Test User" and notion["writes"] is False


def test_a_notion_key_notion_refuses_is_a_failed_flow(
    daemon: Daemon, client: TestClient, tmp_path: Path
) -> None:
    setup = Setup(daemon, client, tmp_path / "connectors", lambda *_: (401, {"message": "unauthorized"}))
    flow = setup.connect("notion", {"key": NOTION_KEY})
    assert flow == {
        "state": "failed",
        "detail": "Notion did not accept that key. Check that you copied all of it.",
    }
    assert setup.connection("notion")["status"] == "disconnected"


@pytest.mark.parametrize(
    ("body", "said"),
    [
        ({}, "Paste your Notion key"),
        ({"key": "  "}, "Paste your Notion key"),
        ({"client_id": "x"}, "not a Google"),
    ],
)
def test_a_notion_body_that_cannot_be_used_is_a_400(setup: Setup, body: dict[str, str], said: str) -> None:
    r = setup.call("POST", "connector_connect", "notion", body)
    assert r.status_code == 400 and said in r.json()["reason"]


def test_a_body_that_is_not_an_object_is_a_400(setup: Setup) -> None:
    r = setup.client.post(
        "/connectors/notion/connect", content=b"[1]", headers={"content-type": "application/json"}
    )
    assert r.status_code == 400 and r.json()["error"] == "bad_request"


# -- probe and disconnect -------------------------------------------------------------------------


def test_probe_rechecks_and_disconnect_forgets(setup: Setup) -> None:
    setup.connect("notion", {"key": NOTION_KEY})
    probes = len(setup.provider.seen)
    notion = setup.act("connector_probe", "notion")
    assert notion["status"] == "connected" and len(setup.provider.seen) == probes + 1
    gone = setup.act("connector_disconnect", "notion")
    assert {k: v for k, v in gone.items() if k != "guide"} == {
        "kind": "notion",
        "status": "disconnected",
        "writes": False,
    }
    assert list((setup.root / "sealed").glob("*")) == [], "every sealed value was destroyed"
    assert setup.act("connector_probe", "notion")["status"] == "disconnected"


def test_disconnecting_google_tells_google_to_forget_and_clears_the_sign_in(setup: Setup) -> None:
    setup.connect("gmail", {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET})
    callback(setup.opened[0], state=state_of(setup.opened[0]), code="c")
    assert setup.settled()["state"] == "done"
    gone = setup.act("connector_disconnect", "gmail")
    assert gone["status"] == "disconnected" and "account" not in gone
    assert any(s.path == "/revoke" for s in setup.provider.seen)
    assert setup.flow() == {"state": "idle"}


def test_writes_switched_on_for_a_twin_show_on_the_wire(setup: Setup) -> None:
    setup.connect("notion", {"key": NOTION_KEY})
    on = setup.connectors.set_writes("notion", True)
    assert on["writes"] is True and setup.connection("notion")["writes"] is True


def test_a_connection_has_no_field_that_could_hold_a_secret() -> None:
    fields = set(Connection.__annotations__) | set(ConnectFlow.__annotations__)
    assert fields == {
        "kind",
        "status",
        "writes",
        "account",
        "last_checked",
        "problem",
        "guide",
        "state",
        "detail",
        "url",
    }
    assert json.dumps(sorted(fields))  # the whole of what a surface can see
