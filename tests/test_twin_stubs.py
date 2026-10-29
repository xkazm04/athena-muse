"""Every twin route not built yet is mounted and answers 501 naming the package that builds it.

A package that builds a route deletes its rows here, so a stub left behind fails this test.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from athena import contracts

# (method, route key, the package that builds it)
STUBS = (
    ("POST", "twin_missions", "WP4"),
    ("GET", "twin_mission", "WP4"),
)

PARAMS = {"id": "tw_000000000000", "mid": "ms_000000000000"}


@pytest.mark.parametrize(("method", "key", "package"), STUBS)
def test_stub_answers_501_naming_its_package(client: TestClient, method: str, key: str, package: str) -> None:
    r = client.request(method, contracts.ROUTES[key].format(**PARAMS), json={})
    assert r.status_code == 501, (key, r.status_code)
    assert r.json() == {"error": "bad_request", "reason": f"not built yet: {package}"}


def test_stubs_are_behind_the_token(client: TestClient) -> None:
    r = client.post("/twins/tw_000000000000/missions", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401 and r.json()["error"] == "unauthorized"
