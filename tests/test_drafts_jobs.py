"""A draft's long steps are background jobs (ADR 0020): followable from any index, stoppable (the model
process is killed), no wall-clock limit on writing while the preview keeps the default, a job cut off
by the app closing found `stopped` at the next start, the person's notes, the Project's draft badge,
and her unusable answers kept."""

from __future__ import annotations

import json
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from starlette.testclient import TestClient

from athena import engine as engine_mod
from athena.app import Daemon
from athena.contracts import AppEvent, Draft
from athena.drafts import author, jobs, preview
from athena.engine import EngineError, TextDelta, ToolCall, Usage, cli
from athena.server import create_app
from drafts_kit import Fake, agreed_draft, broken_table, chore_answer, data_daemon
from test_drafts_jobs_window import Held, serving

H = {"Authorization": "Bearer t"}


@pytest.fixture
def daemon(tmp_path: Path) -> Iterator[Daemon]:
    d = data_daemon(tmp_path)
    yield d
    for job in list(d.jobs._jobs.values()):
        job.cancel.set()
        job.ended.wait(10)
    d.store.close()


def lines(r: httpx.Response) -> list[dict[str, Any]]:
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in r.text.splitlines() if line]


class SlowCli(Fake):
    """The stand-in model, each author and preview answer handed back by a real child process that
    first sleeps `delay` seconds: the CLI runner's limits and Stop apply to it as to a real CLI."""

    def __init__(self, delay: float, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.delay = delay

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        text = "".join(c.text for c in super().complete(messages, tools) if isinstance(c, TextDelta))
        code = f"import sys, time; time.sleep({self.delay}); sys.stdout.write(sys.stdin.read())"
        done = cli.run_cli(cli.CliCall([sys.executable, "-c", code], text, cli.child_env(), Path.cwd()))
        yield TextDelta("\n".join(done.stdout))
        yield Usage(input_tokens=100, output_tokens=20, cost_usd=0.01)


def follow_all(job: jobs.Job, after: int = 0) -> list[dict[str, Any]]:
    return list(jobs.follow(job, after))


# --- the call limits ------------------------------------------------------------------------------


def test_the_default_limits_are_the_old_ones_so_chat_twins_and_the_bench_are_unchanged() -> None:
    assert cli.current_limits() == cli.CallLimits(cli.CLI_TIMEOUT_S, None) and cli.CLI_TIMEOUT_S == 300.0
    with cli.call_limits(cli.CallLimits(None, threading.Event())):
        assert cli.current_limits().timeout_s is None
    assert cli.current_limits() == cli.CallLimits(cli.CLI_TIMEOUT_S, None)  # set per thread, then reset


def test_a_call_past_its_limit_is_stopped_and_a_stop_kills_the_whole_tree() -> None:
    sleep = cli.CliCall(
        [sys.executable, "-c", "import time; time.sleep(30)"], None, cli.child_env(), Path.cwd()
    )
    started = time.monotonic()
    with cli.call_limits(cli.CallLimits(0.3, None)), pytest.raises(EngineError) as info:
        cli.run_cli(sleep)
    assert "longer than 0.3 seconds" in info.value.reason and time.monotonic() - started < 10

    # A wrapper whose child holds the pipe: only a tree kill ends the read.
    nested = "import subprocess, sys; subprocess.run([sys.executable, '-c', 'import time; time.sleep(30)'])"
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    started = time.monotonic()
    with cli.call_limits(cli.CallLimits(None, cancel)), pytest.raises(EngineError) as info:
        list(cli.stream_cli(cli.CliCall([sys.executable, "-c", nested], None, cli.child_env(), Path.cwd())))
    assert info.value.reason == cli.STOPPED and time.monotonic() - started < 10


# --- writing has no limit, the preview keeps its own ----------------------------------------------


def test_writing_has_no_limit_while_a_preview_as_slow_is_stopped_by_it(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "CLI_TIMEOUT_S", 0.5)  # every call here takes 1.5 s
    fake = SlowCli(1.5)
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: fake)
    client = TestClient(create_app(daemon, "t"))
    draft = agreed_draft(daemon)

    events = lines(client.post(f"/drafts/{draft['id']}/write", headers=H))
    assert [e["type"] for e in events] == ["job", "writing", "written"]
    assert daemon.drafts.get(draft["id"])["job"]["state"] == "done"

    events = lines(client.post(f"/drafts/{draft['id']}/preview", headers=H))
    assert [e["type"] for e in events] == ["job", "previewing", "error"]
    assert "longer than 0.5 seconds" in events[-1]["reason"]
    stored = daemon.drafts.get(draft["id"])
    assert stored["step"] == "preview" and stored["job"]["state"] == "failed"  # a failed preview stays


# --- the job: follow, busy, events, her line ------------------------------------------------------


def test_a_job_is_followed_from_any_index_and_replayed_once_it_ended(daemon: Daemon) -> None:
    published: list[AppEvent] = []
    daemon.events.publish = published.append  # type: ignore[method-assign]
    draft = agreed_draft(daemon)
    fake = Fake([chore_answer(broken_table), chore_answer()])
    job = daemon.jobs.start(
        daemon, draft["id"], "write", author.write(daemon, fake, draft["id"]), timeout_s=None
    )
    events = follow_all(job)
    assert [e["type"] for e in events] == ["job", "writing", "repair", "written"]
    assert [e["type"] for e in follow_all(job, 2)] == ["job", "written"]  # from index 2 on
    snap = job.snapshot()
    assert (snap["kind"], snap["state"], snap["events"]) == ("write", "done", 3) and "ended" in snap

    stored = daemon.drafts.get(draft["id"])
    assert stored["job"] == snap and stored["step"] == "preview"
    told = [e for e in published if e["type"] == "draft_job"]
    assert [e["job"]["state"] for e in told] == ["running", "done"]
    assert all(e["draft_id"] == draft["id"] and e["space_id"] == draft["space_id"] for e in told)
    said = daemon.conversation.list(draft["space_id"])[-1]
    assert (said["role"], said["text"]) == ("athena", jobs.DONE_LINES["write"])


def test_a_second_post_while_a_job_runs_is_409_and_the_follow_reattaches(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Held()
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: fake)
    draft = agreed_draft(daemon)
    daemon.jobs.start(daemon, draft["id"], "write", author.write(daemon, fake, draft["id"]), timeout_s=None)
    assert fake.entered.wait(10)
    client = TestClient(create_app(daemon, "t"))
    r = client.post(f"/drafts/{draft['id']}/write", headers=H)
    assert r.status_code == 409 and r.json()["error"] == "space_busy"
    with pytest.raises(Exception) as info:
        daemon.jobs.start(daemon, draft["id"], "write", iter(()), timeout_s=None)
    assert getattr(info.value, "error", None) == "space_busy"
    assert daemon.drafts.get(draft["id"])["job"]["state"] == "running"
    fake.gate.set()
    events = lines(client.get(f"/drafts/{draft['id']}/job?after=1", headers=H))
    assert events[0]["type"] == "job" and [e["type"] for e in events[1:]] == ["written"]
    assert client.get(f"/drafts/{draft['id']}/job?after=x", headers=H).status_code == 400


def test_follow_with_no_job_is_404(daemon: Daemon) -> None:
    client = TestClient(create_app(daemon, "t"))
    draft = agreed_draft(daemon)
    assert client.get(f"/drafts/{draft['id']}/job", headers=H).status_code == 404


# --- Stop ----------------------------------------------------------------------------------------


def test_stop_kills_her_writing_and_the_draft_goes_back_to_the_sketch(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    fake = SlowCli(30)  # a real child process, killed by Stop
    job = daemon.jobs.start(
        daemon, draft["id"], "write", author.write(daemon, fake, draft["id"]), timeout_s=None
    )
    with serving(create_app(daemon, "t")) as base, httpx.Client(base_url=base, headers=H, timeout=20) as http:
        deadline = time.monotonic() + 10
        while daemon.drafts.get(draft["id"])["step"] != "author" and time.monotonic() < deadline:
            time.sleep(0.02)
        started = time.monotonic()
        r = http.post(f"/drafts/{draft['id']}/job/stop")
        assert r.status_code == 200, r.text
        assert time.monotonic() - started < jobs.STOP_GRACE_S  # the process was killed, not waited out
        stored = r.json()
        assert stored["step"] == "shape" and stored["job"]["state"] == "stopped"
        assert stored["job"]["reason"] == "You stopped her."
        events = [json.loads(x) for x in http.get(f"/drafts/{draft['id']}/job").text.splitlines()]
        assert [e["type"] for e in events] == ["job", "writing", "stopped"]
        assert events[-1] == {"type": "stopped", "reason": "You stopped her."}
        again = http.post(f"/drafts/{draft['id']}/job/stop")
        assert again.status_code == 409 and again.json()["error"] == "bad_request"
    assert job.ended.is_set() and not daemon.busy.running(draft["space_id"])
    said = daemon.conversation.list(draft["space_id"])[-1]
    assert said["text"] == "I stopped: You stopped her."


def test_a_call_that_cannot_be_killed_is_stopped_anyway_and_its_late_answer_is_not_used(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The Muse API over HTTP finishes its call after a Stop: the job is stopped after the grace, and
    # the answer that arrives later is dropped (the draft goes back to the sketch, not on to the preview).
    monkeypatch.setattr(jobs, "STOP_GRACE_S", 0.3)
    draft = agreed_draft(daemon)
    fake = Held()
    job = daemon.jobs.start(
        daemon, draft["id"], "write", author.write(daemon, fake, draft["id"]), timeout_s=None
    )
    assert fake.entered.wait(10)
    daemon.jobs.stop(daemon, draft["id"])
    assert job.snapshot()["state"] == "stopped"
    assert daemon.busy.running(draft["space_id"])  # her call is still out; the Project waits for it
    fake.gate.set()
    deadline = time.monotonic() + 10
    while daemon.busy.running(draft["space_id"]) and time.monotonic() < deadline:
        time.sleep(0.02)
    stored = daemon.drafts.get(draft["id"])
    assert stored["step"] == "shape" and "chore_id" not in stored and stored["job"]["state"] == "stopped"
    assert [e["type"] for e in follow_all(job)][-1] == "stopped"


def test_a_stopped_preview_stays_at_the_preview(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    list(author.write(daemon, Fake(), draft["id"]))
    chore = preview.check(daemon, draft["id"])
    job = daemon.jobs.start(
        daemon, draft["id"], "preview", preview.work(daemon, SlowCli(30), draft["id"], chore), timeout_s=300
    )
    deadline = time.monotonic() + 10
    while job.snapshot()["events"] < 1 and time.monotonic() < deadline:
        time.sleep(0.02)
    daemon.jobs.stop(daemon, draft["id"])
    assert [e["type"] for e in follow_all(job)] == ["job", "previewing", "stopped"]
    assert daemon.drafts.get(draft["id"])["step"] == "preview"


# --- a restart ------------------------------------------------------------------------------------


def test_a_job_running_when_the_app_closed_is_stopped_at_the_next_start(tmp_path: Path) -> None:
    daemon = data_daemon(tmp_path)
    draft = agreed_draft(daemon)
    running = {"kind": "write", "state": "running", "started": "2026-11-02T10:00:00Z", "events": 1}
    daemon.drafts.put(cast("Draft", {**daemon.drafts.get(draft["id"]), "step": "author", "job": running}))
    daemon.store.close()

    again = data_daemon(tmp_path)
    try:
        stored = again.drafts.get(draft["id"])
        assert stored["job"]["state"] == "stopped" and stored["job"]["reason"] == jobs.APP_CLOSED
        assert stored["step"] == "shape" and "ended" in stored["job"]
        said = again.conversation.list(draft["space_id"])[-1]
        assert said["text"] == f"I stopped: {jobs.APP_CLOSED}"
        events = lines(TestClient(create_app(again, "t")).get(f"/drafts/{draft['id']}/job", headers=H))
        assert events == [{"type": "job", "job": stored["job"]}]  # after a restart: the snapshot alone
    finally:
        again.store.close()


# --- notes and the badge --------------------------------------------------------------------------


def test_notes_are_replaced_trimmed_and_refused_at_the_verdict(daemon: Daemon) -> None:
    client = TestClient(create_app(daemon, "t"))
    draft = agreed_draft(daemon)
    url = f"/drafts/{draft['id']}/notes"
    r = client.put(
        url, json={"expect": ["  Oct 6  for Ada ", "", "  "], "never": ["pay the invoice"]}, headers=H
    )
    assert r.status_code == 200 and r.json()["notes"] == {
        "expect": ["Oct 6 for Ada"],
        "never": ["pay the invoice"],
    }
    r = client.put(url, json={"expect": [], "never": []}, headers=H)
    assert r.json()["notes"] == {"expect": [], "never": []}
    assert client.put(url, json={"expect": ["x"] * 21, "never": []}, headers=H).status_code == 400
    assert client.put(url, json={"expect": ["x" * 1000], "never": []}, headers=H).status_code == 400
    assert client.put(url, json={"expect": "x", "never": []}, headers=H).status_code == 400
    daemon.drafts.put(cast("Draft", {**daemon.drafts.get(draft["id"]), "step": "verdict"}))
    assert client.put(url, json={"expect": [], "never": []}, headers=H).status_code == 400


def test_the_projects_list_carries_its_open_draft(daemon: Daemon) -> None:
    client = TestClient(create_app(daemon, "t"))
    draft = agreed_draft(daemon)

    def badge() -> Any:
        spaces = client.get("/spaces", headers=H).json()["spaces"]
        return next(s for s in spaces if s["id"] == draft["space_id"]).get("draft")

    assert badge() == {"id": draft["id"], "step": "shape"}  # no job yet
    job = daemon.jobs.start(
        daemon, draft["id"], "write", author.write(daemon, Fake(), draft["id"]), timeout_s=None
    )
    follow_all(job)
    assert badge() == {"id": draft["id"], "step": "preview", "job": "done"}
    daemon.drafts.put(cast("Draft", {**daemon.drafts.get(draft["id"]), "step": "saved"}))
    assert badge() is None


# --- her unusable answers are kept, and a fenced snippet no longer hides the answer -------------------


def test_every_unusable_answer_is_kept_the_newest_three(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    answers = ["not json at all", chore_answer(broken_table), "still not json"]  # REPAIRS_MAX + 1
    events = list(author.write(daemon, Fake(answers), draft["id"]))
    assert events[-1]["type"] == "author_failed"
    folder = daemon.drafts.folder(draft["id"])
    assert folder is not None
    kept = {p.name: p.read_text(encoding="utf-8") for p in folder.iterdir()}
    assert kept == {f"failed-{n}.txt": a for n, a in enumerate(answers, start=1)}
    # The next write's unusable answer is the fourth; the oldest goes. A written chore keeps them too.
    events = list(author.write(daemon, Fake(["{}", chore_answer()]), draft["id"]))
    assert events[-1]["type"] == "written"
    names = sorted(p.name for p in folder.iterdir() if p.is_file())
    assert names == ["failed-2.txt", "failed-3.txt", "failed-4.txt"]
    assert (folder / "failed-4.txt").read_text(encoding="utf-8") == "{}"


def test_a_fenced_snippet_does_not_hide_the_answer_outside_the_fence(daemon: Daemon) -> None:
    body = chore_answer()
    answer = f'For example:\n```json\n{{"title": "a snippet"}}\n```\nThe chore:\n{body}\n'
    assert author.first_object(answer, "world") == json.loads(body)
    draft = agreed_draft(daemon)
    events = list(author.write(daemon, Fake([answer]), draft["id"]))
    assert [e["type"] for e in events] == ["writing", "written"]
