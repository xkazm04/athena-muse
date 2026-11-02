"""The daemon's CORS origins: the desktop's, plus a test run's own port when ATHENA_EXTRA_ORIGINS lists it."""

from __future__ import annotations

from starlette.testclient import TestClient

from athena.app import Daemon
from athena.server import APP_ORIGINS, app_origins, create_app


def test_no_env_is_the_desktop_origins() -> None:
    assert app_origins({}) == APP_ORIGINS


def test_extra_origins_are_trimmed_deduplicated_and_blanks_ignored() -> None:
    got = app_origins({"ATHENA_EXTRA_ORIGINS": " http://localhost:1440 ,,http://localhost:1420, "})
    assert got == (*APP_ORIGINS, "http://localhost:1440")


def test_a_listed_origin_gets_cors_and_an_unlisted_one_does_not(daemon: Daemon) -> None:
    app = create_app(
        daemon, token="t", origins=app_origins({"ATHENA_EXTRA_ORIGINS": "http://localhost:1440"})
    )
    client = TestClient(app)
    listed = client.get("/health", headers={"Origin": "http://localhost:1440"})
    unlisted = client.get("/health", headers={"Origin": "http://localhost:1441"})
    assert listed.headers.get("access-control-allow-origin") == "http://localhost:1440"
    assert "access-control-allow-origin" not in unlisted.headers
