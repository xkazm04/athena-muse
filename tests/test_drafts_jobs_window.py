"""A draft's writing outlives its window (ADR 0020), over a real server: the person closes the window
while she writes, and the chore is written all the same. Measured before: writing ran inside the HTTP
stream, so a closed window cut it off at the next line it sent (here: the repair after a first answer
that did not load)."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from starlette.applications import Starlette

from athena import engine as engine_mod
from athena.engine import TextDelta, ToolCall, Usage
from athena.server import create_app
from drafts_kit import Fake, agreed_draft, broken_table, chore_answer, data_daemon

H = {"Authorization": "Bearer t"}


class Held(Fake):
    """The stand-in model, whose first call waits on `gate` (a long writing call)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.gate = threading.Event()
        self.entered = threading.Event()
        self.calls = 0

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        self.calls += 1
        if self.calls == 1:
            self.entered.set()
            assert self.gate.wait(20)
        yield from super().complete(messages, tools)


@contextmanager
def serving(app: Starlette) -> Iterator[str]:
    """The app on a real loopback server, on a free port, for the test's life."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="off"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()


def test_a_closed_window_does_not_cut_her_writing_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Held([chore_answer(broken_table), chore_answer()])  # the first answer needs a repair
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: fake)
    daemon = data_daemon(tmp_path)
    draft = agreed_draft(daemon)
    try:
        with (
            serving(create_app(daemon, "t")) as base,
            httpx.Client(base_url=base, headers=H, timeout=20) as http,
        ):
            with http.stream("POST", f"/drafts/{draft['id']}/write") as r:
                assert r.status_code == 200
                first = json.loads(next(r.iter_lines()))
                assert first["type"] in ("job", "writing")
                assert fake.entered.wait(10)
            # The window is closed while the model is still writing; then the model answers.
            time.sleep(0.3)
            fake.gate.set()
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline and daemon.drafts.get(draft["id"])["step"] == "author":
                time.sleep(0.05)
            stored = daemon.drafts.get(draft["id"])
            assert stored["step"] == "preview" and "chore_id" in stored, stored["step"]
            assert fake.calls == 2  # the repair ran with nobody listening
            jobs = getattr(daemon, "jobs", None)  # (this test also runs against the code before jobs)
            job = jobs.get(draft["id"]) if jobs is not None else None
            if job is not None:
                assert job.ended.wait(10) and job.snapshot()["state"] == "done"
    finally:
        fake.gate.set()
        daemon.store.close()
