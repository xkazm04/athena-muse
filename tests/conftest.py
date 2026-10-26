from __future__ import annotations

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.server import create_app

TOKEN = "t"


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    d = Daemon.open(None)
    yield d
    d.store.close()


@pytest.fixture
def client(daemon: Daemon) -> TestClient:
    return TestClient(create_app(daemon, token=TOKEN), headers={"Authorization": f"Bearer {TOKEN}"})
