"""The records routes (business Phase 1): a project's records, a record's history, a track's verdict and
the kinds a project keeps; an unknown project or record is unknown_ref; erasing a project takes its
records with it."""

from __future__ import annotations

from starlette.testclient import TestClient

from athena.app import Daemon
from records_kit import CREATOR, TRACK, creator, project, stat, track

NOBODY = "spc_000000000000"


def test_space_records_lists_the_latest_and_filters_by_kind_and_key(
    client: TestClient, daemon: Daemon
) -> None:
    space = project(daemon)
    daemon.records.put(space, "creator", creator(), "athena")
    found = daemon.records.put(space, "track", track(), "athena")
    daemon.records.put(space, "track", track(note="again"), "athena")
    daemon.records.put(space, "stat", stat(3), "routine")
    listed = client.get(f"/spaces/{space}/records").json()
    assert list(listed) == ["records"] and len(listed["records"]) == 3
    assert listed["records"][0]["kind"] == "stat"
    tracks = client.get(f"/spaces/{space}/records", params={"kind": "track"}).json()["records"]
    assert len(tracks) == 1 and tracks[0]["rev"] == 2 and tracks[0]["key"] == found["key"]
    one = client.get(f"/spaces/{space}/records", params={"kind": "creator", "key": CREATOR}).json()
    assert [r["key"] for r in one["records"]] == [CREATOR]
    bad = client.get(f"/spaces/{space}/records", params={"kind": "invoice"})
    assert bad.status_code == 400 and bad.json()["error"] == "bad_request"
    assert client.get(f"/spaces/{NOBODY}/records").json()["error"] == "unknown_ref"


def test_record_history_is_oldest_first(client: TestClient, daemon: Daemon) -> None:
    space = project(daemon)
    first = daemon.records.put(space, "track", track(), "athena")
    daemon.records.put(space, "track", track(note="again"), "athena")
    history = client.get(f"/records/{first['id']}/history").json()["records"]
    assert [r["rev"] for r in history] == [1, 2]
    missing = client.get("/records/rec_000000000000/history")
    assert missing.status_code == 404 and missing.json()["error"] == "unknown_ref"


def test_record_verdict_appends_a_revision_and_refuses_a_non_track(
    client: TestClient, daemon: Daemon
) -> None:
    space = project(daemon)
    found = daemon.records.put(space, "track", track(), "athena")
    judged = client.post(f"/records/{found['id']}/verdict", json={"verdict": "keep", "genre": "lo-fi"})
    assert judged.status_code == 200
    body = judged.json()
    assert body["rev"] == 2 and body["by"] == "person" and body["body"]["verdict"] == "keep"
    assert body["key"] == TRACK
    person = daemon.records.put(space, "creator", creator(), "athena")
    refused = client.post(f"/records/{person['id']}/verdict", json={"verdict": "keep"})
    assert refused.status_code == 400 and refused.json()["error"] == "bad_request"
    wrong = client.post(f"/records/{found['id']}/verdict", json={"verdict": "maybe"})
    assert wrong.status_code == 400
    assert client.post(f"/records/{found['id']}/verdict", json=["keep"]).status_code == 400
    missing = client.post("/records/rec_000000000000/verdict", json={"verdict": "keep"})
    assert missing.status_code == 404 and missing.json()["error"] == "unknown_ref"


def test_space_kinds_sets_what_a_project_keeps(client: TestClient, daemon: Daemon) -> None:
    space = client.post("/spaces", json={"name": "Channel"}).json()["id"]
    put = client.put(f"/spaces/{space}/kinds", json={"kinds": ["track", "creator", "track"]})
    assert put.status_code == 200 and put.json() == {"kinds": ["track", "creator"]}
    assert client.get(f"/spaces/{space}").json()["kinds"] == ["track", "creator"]
    assert client.put(f"/spaces/{space}/kinds", json={"kinds": ["invoice"]}).status_code == 400
    assert client.put(f"/spaces/{space}/kinds", json={"kinds": "track"}).status_code == 400
    cleared = client.put(f"/spaces/{space}/kinds", json={"kinds": []}).json()
    assert cleared == {"kinds": []} and "kinds" not in client.get(f"/spaces/{space}").json()
    missing = client.put(f"/spaces/{NOBODY}/kinds", json={"kinds": ["track"]})
    assert missing.status_code == 404 and missing.json()["error"] == "unknown_ref"


def test_erasing_a_project_erases_its_records(client: TestClient, daemon: Daemon) -> None:
    space = project(daemon)
    first = daemon.records.put(space, "creator", creator(), "athena")
    assert client.delete(f"/spaces/{space}").status_code == 200
    assert client.get(f"/records/{first['id']}/history").status_code == 404
    assert daemon.store.query("SELECT COUNT(*) AS n FROM records")[0]["n"] == 0
