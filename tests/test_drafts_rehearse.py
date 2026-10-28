"""The test run, the verdict and the two libraries (ADR 0007), over the routes with a stand-in model:
write -> preview -> key -> rehearse streams phase, card and scored and copies its model calls into the
real ledger; keep moves the chore to the person's library, listed as `origin: "yours"`."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from starlette.testclient import TestClient

from athena import engine as engine_mod
from athena import turn
from athena.app import Daemon
from athena.chores.spec import PLAYBOOKS_ENV, find_chore, load_both
from athena.server import create_app
from drafts_kit import Fake, agreed_draft, data_daemon
from test_chores_spec import make_chore

H = {"Authorization": "Bearer t"}


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Fake:
    f = Fake()
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: f)
    return f


@pytest.fixture
def daemon(tmp_path: Path) -> Iterator[Daemon]:
    d = data_daemon(tmp_path)
    yield d
    d.store.close()


@pytest.fixture
def client(daemon: Daemon) -> TestClient:
    return TestClient(create_app(daemon, "t"))


def lines(r: httpx.Response) -> list[dict[str, Any]]:
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in r.text.splitlines() if line]


def to_rehearse(client: TestClient, daemon: Daemon) -> dict[str, Any]:
    """An agreed draft written, previewed and keyed (yes, yes, no) over the routes."""
    draft = agreed_draft(daemon)
    assert lines(client.post(f"/drafts/{draft['id']}/write", headers=H))[-1]["type"] == "written"
    r = client.post(f"/drafts/{draft['id']}/preview", headers=H)
    assert r.status_code == 200 and [c["id"] for c in r.json()["expected"]] == ["e1", "e2", "e3"]
    marks = [{"expected_id": "e1", "mark": "yes"}, {"expected_id": "e2", "mark": "yes"}]
    marks.append({"expected_id": "e3", "mark": "no"})
    r = client.put(f"/drafts/{draft['id']}/key", json={"marks": marks, "missing": [], "never": []}, headers=H)
    assert r.status_code == 200 and r.json()["step"] == "rehearse", r.text
    return dict(r.json())


# --- acceptance 3: the test run -------------------------------------------------------------------


def test_a_test_run_streams_phases_cards_and_the_score(
    client: TestClient, daemon: Daemon, fake: Fake
) -> None:
    draft = to_rehearse(client, daemon)
    before = daemon.ledger.page(100)["totals"]["calls"]
    events = lines(client.post(f"/drafts/{draft['id']}/rehearse", headers=H))
    assert [e["type"] for e in events] == ["phase", "phase", "card", "card", "scored"]
    assert [(e["index"], e["app"]) for e in events if e["type"] == "phase"] == [(1, "school"), (2, "club")]
    cards = [e["card"] for e in events if e["type"] == "card"]
    assert [c["args"]["params"]["line_id"] for c in cards] == ["L2", "L3"]
    assert all(c["action"] == "portal_act" and c["state"] == "waiting" for c in cards)  # nothing approved
    bench = events[-1]["bench"]
    assert (bench["found"], bench["eligible"], bench["false_claims"], bench["verdict"]) == (
        2,
        2,
        0,
        "exceeds",
    )
    assert bench["engine"] == "scripted" and bench["model"] == "fake"

    rows = daemon.ledger.page(100)["rows"]
    rehearsal = [r for r in rows if r["surface"] == "rehearsal"]
    assert len(rows) - before == len(rehearsal) > 0
    assert {r["space_id"] for r in rehearsal} == {draft["space_id"]} and all(r["ok"] for r in rehearsal)
    assert daemon.gate.list() == []  # the run's cards were filed on the throwaway daemon, not here

    stored = daemon.drafts.get(draft["id"])
    assert stored["step"] == "verdict" and stored["bench"] == bench
    root = daemon.drafts.folder(draft["id"]) / stored["chore_id"]  # type: ignore[operator]
    assert json.loads((root / "bench.json").read_text(encoding="utf-8"))["verdict"] == "exceeds"


def test_a_filed_trap_scores_as_a_false_claim(client: TestClient, daemon: Daemon, fake: Fake) -> None:
    draft = to_rehearse(client, daemon)
    fake.files = ("L2", "L1")
    bench = lines(client.post(f"/drafts/{draft['id']}/rehearse", headers=H))[-1]["bench"]
    assert (bench["found"], bench["traps_filed"], bench["verdict"]) == (1, 1, "short")


def test_a_run_that_breaks_streams_error_and_stays_at_rehearse(
    client: TestClient, daemon: Daemon, fake: Fake
) -> None:
    draft = to_rehearse(client, daemon)
    fake.fail = "run"
    events = lines(client.post(f"/drafts/{draft['id']}/rehearse", headers=H))
    assert [e["type"] for e in events] == ["phase", "error"]
    assert events[-1]["error"] == "engine_unavailable" and "not scored" in events[-1]["reason"]
    stored = daemon.drafts.get(draft["id"])
    assert stored["step"] == "rehearse" and "bench" not in stored
    failed = [r for r in daemon.ledger.page(100)["rows"] if r["surface"] == "rehearsal"]
    assert [r["ok"] for r in failed] == [False]  # the failed call is still on the record
    assert not daemon.busy.running(draft["space_id"])


def test_the_run_needs_the_key(client: TestClient, daemon: Daemon, fake: Fake) -> None:
    draft = agreed_draft(daemon)
    lines(client.post(f"/drafts/{draft['id']}/write", headers=H))
    r = client.post(f"/drafts/{draft['id']}/rehearse", headers=H)
    assert r.status_code == 400 and r.json()["error"] == "bad_request"


# --- acceptance 4: keep, and the two libraries -----------------------------------------------------


def test_keep_copies_the_chore_to_the_persons_library(
    client: TestClient, daemon: Daemon, fake: Fake, tmp_path: Path
) -> None:
    draft = to_rehearse(client, daemon)
    lines(client.post(f"/drafts/{draft['id']}/rehearse", headers=H))
    r = client.post(f"/drafts/{draft['id']}/verdict", json={"verdict": "keep", "note": "  Good. "}, headers=H)
    assert r.status_code == 200, r.text
    kept = r.json()
    assert (kept["step"], kept["verdict"], kept["note"]) == ("saved", "keep", "Good.")
    chore_id = kept["chore_id"]
    mine = tmp_path / "data" / "chores" / chore_id
    assert (mine / "truth.json").is_file() and (mine / "bench.json").is_file()
    space = client.get(f"/spaces/{draft['space_id']}", headers=H).json()
    assert space["brief"].startswith("Every billed day") and space["apps"] == []

    listed = client.get("/chores", headers=H).json()["chores"]
    origins = {c["id"]: c["origin"] for c in listed}
    assert origins[chore_id] == "yours"
    assert {o for i, o in origins.items() if i != chore_id} == {"library"} and len(origins) > 1
    ours = next(c for c in listed if c["id"] == chore_id)
    assert ours["bench"]["verdict"] == "exceeds"
    detail = client.get(f"/chores/{chore_id}", headers=H).json()
    assert detail["chore"]["origin"] == "yours" and [a["app_id"] for a in detail["apps"]] == [
        "school",
        "club",
    ]

    # A signed card for her chore finds it (turn._portal_for reads both libraries).
    args = {"app": "club", "tool": "dispute_day", "params": {"line_id": "L2"}, "chore": chore_id}
    card = daemon.gate.file(draft["space_id"], "portal_act", args, "Dispute one billed day")
    assert turn.execute(daemon, card) == "Your dispute of L2 is with the club office."

    again = client.post(f"/drafts/{draft['id']}/verdict", json={"verdict": "keep"}, headers=H)
    assert again.status_code == 400


def test_revise_goes_back_to_the_sketch_with_the_note(client: TestClient, daemon: Daemon, fake: Fake) -> None:
    draft = to_rehearse(client, daemon)
    r = client.post(
        f"/drafts/{draft['id']}/verdict", json={"verdict": "revise", "note": "Only Ben"}, headers=H
    )
    assert r.status_code == 200
    revised = r.json()
    assert (revised["step"], revised["verdict"], revised["note"]) == ("shape", "revise", "Only Ben")
    assert revised["sketch"] == draft["sketch"]
    # Keep is refused before a test run; a second write starts from the sketch with her note.
    assert (
        client.post(f"/drafts/{draft['id']}/verdict", json={"verdict": "keep"}, headers=H).status_code == 400
    )
    lines(client.post(f"/drafts/{draft['id']}/write", headers=H))
    assert "Only Ben" in str(fake.asked[-1][-1]["content"])
    assert "note" not in daemon.drafts.get(draft["id"])


def test_a_user_chore_never_shadows_the_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    library = tmp_path / "library"
    make_chore(library)
    make_chore(tmp_path / "data" / "chores")  # the same id, kept by the person
    make_chore(tmp_path / "data" / "chores", chore_id="her-own")
    monkeypatch.setenv(PLAYBOOKS_ENV, str(library))
    chores = load_both(tmp_path / "data")
    assert [(c.id, c.origin) for c in chores] == [("desk-chore", "library"), ("her-own", "yours")]
    assert "the library has a chore by that id" in caplog.text
    assert find_chore("desk-chore", tmp_path / "data") == (library / "desk-chore", "library")
    assert find_chore("her-own", tmp_path / "data") == (tmp_path / "data" / "chores" / "her-own", "yours")
    assert find_chore("her-own", None) is None and find_chore("../x", tmp_path / "data") is None
