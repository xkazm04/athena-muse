"""Every twin and connector route is mounted and answers 501 naming the package that builds it.

A package that builds a route deletes its rows here, so a stub left behind fails this test.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from athena import contracts
from athena.twins import decide

# (method, route key, the package that builds it)
STUBS = (
    ("GET", "twins", "WP3"),
    ("POST", "twins", "WP3"),
    ("GET", "twin", "WP3"),
    ("POST", "twin_say", "WP3"),
    ("POST", "twin_confirm", "WP3"),
    ("POST", "twin_drop", "WP3"),
    ("POST", "twin_samples", "WP3"),
    ("POST", "twin_dials", "WP3"),
    ("POST", "twin_pages", "WP3"),
    ("POST", "twin_chores", "WP3"),
    ("POST", "twin_autonomy", "WP3"),
    ("POST", "twin_memory", "WP3"),
    ("POST", "twin_rehearse", "WP3"),
    ("POST", "twin_mark", "WP3"),
    ("POST", "twin_golive", "WP3"),
    ("POST", "twin_pause", "WP3"),
    ("POST", "twin_missions", "WP4"),
    ("GET", "twin_mission", "WP4"),
    ("GET", "connectors", "WP2"),
    ("POST", "connector_connect", "WP2"),
    ("GET", "connector_flow", "WP2"),
    ("POST", "connector_disconnect", "WP2"),
    ("POST", "connector_probe", "WP2"),
)

PARAMS = {"id": "tw_000000000000", "mid": "ms_000000000000", "kind": "gmail"}


@pytest.mark.parametrize(("method", "key", "package"), STUBS)
def test_stub_answers_501_naming_its_package(client: TestClient, method: str, key: str, package: str) -> None:
    r = client.request(method, contracts.ROUTES[key].format(**PARAMS), json={})
    assert r.status_code == 501, (key, r.status_code)
    assert r.json() == {"error": "bad_request", "reason": f"not built yet: {package}"}


def test_stubs_are_behind_the_token(client: TestClient) -> None:
    r = client.get("/twins", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401 and r.json()["error"] == "unauthorized"


def test_send_rule_is_not_built_yet() -> None:
    channel: contracts.TwinChannel = {
        "kind": "gmail",
        "account": "someone@example.com",
        "status": "connected",
        "autonomy": "auto",
        "bar": contracts.BAR_DEFAULT,
    }
    facts = decide.DraftFacts(kind="reply", confidence=91, risks=())
    with pytest.raises(NotImplementedError, match="WP4"):
        decide.decide(channel, facts, twin_live=True)
