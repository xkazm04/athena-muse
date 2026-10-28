"""Authoring (ADR 0007): an agreed draft becomes a chore folder `load_chore` accepts; the loader's
problems come back to the person in plain words and to the model whole, up to REPAIRS_MAX repairs."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import engine as engine_mod
from athena.app import Daemon
from athena.chores.spec import PLAYBOOKS_ENV, library_dir, load_chore
from athena.contracts import REPAIRS_MAX
from athena.drafts import author, shape
from athena.errors import ApiError
from athena.server import create_app
from drafts_kit import NEED, Fake, agreed_draft, broken_table, chore_answer, data_daemon

H = {"Authorization": "Bearer t"}


@pytest.fixture
def daemon(tmp_path: Path) -> Iterator[Daemon]:
    d = data_daemon(tmp_path)
    yield d
    d.store.close()


def write(daemon: Daemon, engine: Fake, draft_id: str) -> list[dict[str, Any]]:
    return list(author.write(daemon, engine, draft_id))


# --- acceptance 1 ---------------------------------------------------------------------------------


def test_write_from_an_agreed_draft_yields_a_folder_load_chore_accepts(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    events = write(daemon, Fake(), draft["id"])
    assert [e["type"] for e in events] == ["writing", "written"]
    chore_id = events[-1]["chore_id"]
    assert chore_id == "the-club-invoice-checked-against"
    root = daemon.drafts.folder(draft["id"]) / chore_id  # type: ignore[operator]
    chore = load_chore(root)
    assert chore.id == chore_id and [a.app_id for a in chore.apps] == ["school", "club"]
    assert json.loads((root / "truth.json").read_text(encoding="utf-8")) == {"targets": [], "forbidden": []}
    stored = daemon.drafts.get(draft["id"])
    assert stored["step"] == "preview" and stored["chore_id"] == chore_id
    rows = daemon.ledger.page(10)["rows"]
    assert [(r["surface"], r["space_id"], r["ok"]) for r in rows] == [("design", draft["space_id"], True)]


def test_the_author_is_given_the_sketch_the_example_and_the_rules_never_a_key(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    fake = Fake()
    write(daemon, fake, draft["id"])
    system, user = (str(m["content"]) for m in fake.asked[0])
    assert '"Each dispute waits for my signature" (the person\'s words)' in user
    assert NEED in user
    assert "An example chore from Athena's library" in system and '"key": true' in system
    assert "category" in system and "contest" in system  # the taxonomy ids
    for root in library_dir().iterdir():  # no library chore's answer key reaches the author
        if (root / "truth.json").is_file():
            for target in json.loads((root / "truth.json").read_text(encoding="utf-8"))["targets"]:
                assert all(entry["why"] not in system for entry in target["eligible"].values())


def test_a_fenced_answer_with_words_around_it_is_read(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    events = write(daemon, Fake([chore_answer(fenced=True)]), draft["id"])
    assert events[-1]["type"] == "written"


def test_an_invalid_first_answer_is_repaired_with_the_validators_problems(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    fake = Fake([chore_answer(broken_table), chore_answer()])
    events = write(daemon, fake, draft["id"])
    assert [e["type"] for e in events] == ["writing", "repair", "written"]
    assert events[1]["problems"] == [
        "List attendance on school reads register, a table the apps do not have.",
        "The test run has no steps: it opens none of her practice apps.",
    ]
    fed_back = str(fake.asked[1][-1]["content"])  # the model gets the loader's own lines, whole
    assert "school.list_attendance: reads table 'register', which no world or sensed table has" in fed_back
    assert "world.json has no phases" in fed_back
    assert daemon.drafts.get(draft["id"])["step"] == "preview"


def test_an_answer_that_never_loads_ends_author_failed_back_at_shape(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    fake = Fake([chore_answer(broken_table)])
    events = write(daemon, fake, draft["id"])
    assert [e["type"] for e in events] == ["writing"] + ["repair"] * REPAIRS_MAX + ["author_failed"]
    assert len(fake.asked) == REPAIRS_MAX + 1
    assert events[-1]["problems"][0].startswith("List attendance on school reads register")
    stored = daemon.drafts.get(draft["id"])
    assert stored["step"] == "shape" and "chore_id" not in stored
    folder = daemon.drafts.folder(draft["id"])
    assert folder is not None and list(folder.iterdir()) == []


def test_an_unreadable_answer_is_a_problem_like_any_other(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    events = write(daemon, Fake(["I would rather not.", chore_answer()]), draft["id"])
    assert events[1] == {"type": "repair", "problems": ["Her answer could not be read as a chore."]}
    assert events[-1]["type"] == "written"


def test_an_engine_error_is_an_error_event_and_the_draft_goes_back_to_shape(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    events = write(daemon, Fake(fail="author"), draft["id"])
    assert events[-1] == {"type": "error", "error": "engine_unavailable", "reason": "Claude Code stopped"}
    assert daemon.drafts.get(draft["id"])["step"] == "shape"
    assert [r["ok"] for r in daemon.ledger.page(10)["rows"]] == [False]


def test_write_is_allowed_at_any_coverage_and_skips_the_open_slots(daemon: Daemon) -> None:
    draft = shape.start(daemon, NEED)
    sketch = {"nodes": [agreed_draft_node()], "edges": []}
    daemon.drafts.put({**draft, "sketch": sketch, "step": "shape"})  # type: ignore[typeddict-item]
    write(daemon, Fake(), draft["id"])
    cov = daemon.drafts.get(draft["id"])["coverage"]
    assert cov["need"] == 1 and {cov[s] for s in cov if s != "need"} == {"skipped"}


def agreed_draft_node() -> dict[str, Any]:
    return {
        "id": "n1",
        "kind": "step",
        "slot": "need",
        "label": "Check the invoice",
        "origin": "you",
        "confirmed": True,
    }


def test_the_chore_id_is_unique_across_both_libraries(
    daemon: Daemon, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = tmp_path / "library"
    (library / "the-club-invoice-checked-against").mkdir(parents=True)
    (library / "taxonomy.json").write_text(
        json.dumps({"categories": [{"id": "family"}], "jobs": [{"id": "contest"}]})
    )
    (tmp_path / "data" / "chores" / "the-club-invoice-checked-against-2").mkdir(parents=True)
    monkeypatch.setenv(PLAYBOOKS_ENV, str(library))
    draft = agreed_draft(daemon)
    events = write(daemon, Fake(), draft["id"])
    assert events[-1] == {"type": "written", "chore_id": "the-club-invoice-checked-against-3"}


def test_slugs_are_short_ids_cut_at_a_word() -> None:
    assert author.slug("  Ça va? The CLUB's invoice!! ") == "a-va-the-club-s-invoice"
    assert author.slug("!!!") == "my-chore"
    title = "The after-school club's October invoice, held to the school portal's attendance"
    assert author.slug(title) == "the-after-school-club-s-october-invoice"
    long = author.slug("word " * 40)
    assert len(long) <= author.SLUG_MAX and not long.endswith("-")
    assert len(author.unique_id("x" * 80, {"x" * 80})) == 80


def test_every_loader_problem_reads_in_plain_words() -> None:
    samples = {
        "playbook.json is missing": "The chore's description is missing.",
        "world.json cannot be read as JSON: Expecting value": "Her practice apps could not be read.",
        "playbook.json has no promise": "The chore does not say what it promises.",
        "category 'space' is not in taxonomy.json": (
            "The chore's kind of work, space, is not one Athena knows."
        ),
        "club.dispute_day: a REACHES_A_PERSON tool needs says": (
            "Dispute day on club does not say what the app answers once it runs."
        ),
        "club.read_invoice: matches on child, which are not its params": (
            "Read invoice on club looks rows up by child, which it does not take."
        ),
        "a phase opens app 'bank', which the world does not have": (
            "A step of the test run opens bank, which is not one of her practice apps."
        ),
        "truth target 'refund' is a tool no app has": (
            "What you expect names refund, which no practice app has."
        ),
        "something new in world.json": "Something new in her practice apps.",
    }
    for problem, said in samples.items():
        assert author.plain(problem) == said, problem
    for said in map(author.plain, samples):
        assert ".json" not in said and "truth" not in said.casefold()


def test_the_routes_refuse_a_draft_that_is_not_ready_or_has_no_data_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: Fake())
    nowhere = Daemon.open(None)
    client = TestClient(create_app(nowhere, "t"))
    draft = agreed_draft(nowhere)
    r = client.post(f"/drafts/{draft['id']}/write", headers=H)
    assert r.status_code == 400 and "data folder" in r.json()["reason"]
    nowhere.store.close()

    daemon = data_daemon(tmp_path)
    client = TestClient(create_app(daemon, "t"))
    fresh = shape.start(daemon, NEED)  # still at describe
    assert client.post(f"/drafts/{fresh['id']}/write", headers=H).status_code == 400
    assert client.post("/drafts/drf_000000000000/write", headers=H).status_code == 404
    for path in ("preview", "rehearse"):
        assert client.post(f"/drafts/{fresh['id']}/{path}", headers=H).status_code == 400
    daemon.store.close()


def test_the_write_route_streams_ndjson(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: Fake())
    daemon = data_daemon(tmp_path)
    client = TestClient(create_app(daemon, "t"))
    draft = agreed_draft(daemon)
    r = client.post(f"/drafts/{draft['id']}/write", headers=H)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    assert [json.loads(line)["type"] for line in r.text.splitlines()] == ["writing", "written"]
    daemon.store.close()


def test_a_busy_project_refuses_a_write(daemon: Daemon) -> None:
    draft = agreed_draft(daemon)
    with daemon.busy.turn(draft["space_id"]), pytest.raises(ApiError) as info:
        author.write(daemon, Fake(), draft["id"])
    assert info.value.error == "space_busy"
