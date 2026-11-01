"""The records store (business Phase 1): append-only revisions, the latest per key, the shape trigger,
the person's verdict, the kinds a project keeps, erasing, and the rights rule (may_render)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from athena.app import Daemon
from athena.errors import ApiError
from athena.records import store as store_mod
from athena.records.store import may_render
from records_kit import ALL, CREATOR, TRACK, creator, file_row, project, renderable, stat, track


@pytest.fixture
def disk(tmp_path: Path) -> Iterator[Daemon]:
    d = Daemon.open(tmp_path / "data")
    yield d
    d.store.close()


def test_a_change_appends_a_revision_and_an_unchanged_put_appends_nothing(daemon: Daemon) -> None:
    space = project(daemon)
    first = daemon.records.put(space, "creator", creator(), "athena")
    assert first["id"].startswith("rec_") and first["rev"] == 1 and first["key"] == CREATOR
    again = daemon.records.put(space, "creator", {**creator(), "name": " Lumen "}, "athena")
    assert again == first  # the cleaned body is the same: nothing appended
    changed = daemon.records.put(space, "creator", {**creator(), "note": "answers fast"}, "person")
    assert changed["rev"] == 2 and changed["by"] == "person" and changed["id"] != first["id"]
    history = daemon.records.history(first["id"])
    assert [r["rev"] for r in history] == [1, 2]  # oldest first, from either revision's id
    assert daemon.records.history(changed["id"]) == history
    assert daemon.store.query("SELECT COUNT(*) AS n FROM records")[0]["n"] == 2


def test_latest_is_one_revision_per_key_newest_first_and_capped(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    space = project(daemon)
    for day in range(1, 6):
        daemon.records.put(space, "stat", stat(day, f"2026-10-0{day}T12:00:00Z"), "routine")
    daemon.records.put(space, "creator", creator(), "athena")
    daemon.records.put(space, "stat", stat(99, "2026-10-01T12:00:00Z"), "routine")  # a revision of the first
    latest = daemon.records.latest(space)
    assert len(latest) == 6
    assert latest[0]["key"] == "views@2026-10-01T12:00:00Z" and latest[0]["rev"] == 2
    assert latest[1]["kind"] == "creator"
    assert [r["body"]["value"] for r in daemon.records.latest(space, "stat")] == [99, 5, 4, 3, 2]
    assert daemon.records.latest(space, "creator", CREATOR + "/")[0]["key"] == CREATOR  # key normalised
    assert daemon.records.count(space, "stat") == 5
    monkeypatch.setattr(store_mod, "RECORDS_PAGE_MAX", 3)
    assert len(daemon.records.latest(space)) == 3
    other = project(daemon)
    assert daemon.records.latest(other) == []


def test_on_change_fires_on_a_new_key_only_never_on_a_revision_or_a_verdict(daemon: Daemon) -> None:
    space = project(daemon)
    seen: list[tuple[str, str, int, int]] = []
    daemon.records.on_change = lambda s, k, b, a: seen.append((s, k, b, a))
    found = daemon.records.put(space, "track", track(), "athena")
    daemon.records.put(space, "track", track(note="second look"), "athena")  # a revision
    daemon.records.verdict(found["id"], {"verdict": "keep", "genre": "lo-fi"})
    daemon.records.put(space, "track", track(), "athena")  # a whole body again: a revision
    daemon.records.put(space, "track", track(TRACK + "2"), "athena")
    assert seen == [(space, "track", 0, 1), (space, "track", 1, 2)]


def test_a_failing_on_change_never_fails_the_put(daemon: Daemon) -> None:
    space = project(daemon)

    def broken(*_: Any) -> None:
        raise RuntimeError("the report is down")

    daemon.records.on_change = broken
    assert daemon.records.put(space, "creator", creator(), "athena")["rev"] == 1


def test_a_verdict_is_a_track_revision_by_the_person(daemon: Daemon) -> None:
    space = project(daemon)
    found = daemon.records.put(space, "track", track(note="found on the channel"), "athena")
    judged = daemon.records.verdict(found["id"], {"verdict": "keep", "genre": "lo-fi"})
    assert judged["rev"] == 2 and judged["by"] == "person"
    assert judged["body"] == {**found["body"], "verdict": "keep", "genre": "lo-fi"}
    later = daemon.records.verdict(found["id"], {"verdict": "later"})  # from the first revision's id
    assert later["rev"] == 3 and later["body"]["genre"] == "lo-fi" and later["body"]["verdict"] == "later"
    assert daemon.records.verdict(found["id"], {"verdict": "later"}) == later  # the same verdict: nothing
    with pytest.raises(ApiError) as bad:
        daemon.records.verdict(found["id"], {"verdict": "maybe"})  # type: ignore[typeddict-item]
    assert bad.value.error == "bad_request"
    person = daemon.records.put(space, "creator", creator(), "athena")
    with pytest.raises(ApiError, match="only a track") as not_track:
        daemon.records.verdict(person["id"], {"verdict": "keep"})
    assert not_track.value.error == "bad_request"
    with pytest.raises(ApiError) as unknown:
        daemon.records.verdict("rec_000000000000", {"verdict": "keep"})
    assert unknown.value.error == "unknown_ref"


def test_kinds_are_checked_deduplicated_and_announced(
    daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    published: list[dict[str, Any]] = []
    monkeypatch.setattr(daemon.events, "publish", published.append)
    space = daemon.spaces.create({"name": "Channel"})["id"]
    assert daemon.records.kinds(space) == [] and "kinds" not in daemon.spaces.get(space)
    assert daemon.records.set_kinds(space, {"kinds": ["track", "creator", "track"]}) == {
        "kinds": ["track", "creator"]
    }
    assert daemon.records.kinds(space) == ["track", "creator"]
    assert daemon.spaces.get(space)["kinds"] == ["track", "creator"]
    assert published == [{"type": "space_changed", "space_id": space}]
    with pytest.raises(ApiError, match="no record kind"):
        daemon.records.set_kinds(space, {"kinds": ["invoice"]})  # type: ignore[list-item]
    with pytest.raises(ApiError) as unknown:
        daemon.records.set_kinds("spc_000000000000", {"kinds": ALL})
    assert unknown.value.error == "unknown_ref"


def test_a_put_is_refused_for_an_unknown_project_kind_or_file(daemon: Daemon) -> None:
    space = project(daemon)
    with pytest.raises(ApiError) as unknown:
        daemon.records.put("spc_000000000000", "creator", creator(), "athena")
    assert unknown.value.error == "unknown_ref"
    with pytest.raises(ApiError, match="no record kind"):
        daemon.records.put(space, "invoice", {}, "athena")  # type: ignore[arg-type]
    with pytest.raises(ApiError, match="not one of this project's files"):
        daemon.records.put(space, "file", {"file_id": "fil_000000000000"}, "person")
    with pytest.raises(ApiError, match="not one of this project's files"):
        daemon.records.put(space, "track", track(file_id="fil_000000000000"), "athena")


def test_a_file_record_points_at_a_files_row_of_its_own_project(disk: Daemon, tmp_path: Path) -> None:
    space, other = project(disk), project(disk)
    file_id = file_row(disk, space, tmp_path)
    kept = disk.records.put(space, "file", {"file_id": file_id, "track_key": TRACK}, "person")
    assert kept["key"] == file_id
    with pytest.raises(ApiError, match="not one of this project's files"):
        disk.records.put(other, "file", {"file_id": file_id}, "person")


def test_erase_removes_the_records_with_the_project(daemon: Daemon) -> None:
    space, other = project(daemon), project(daemon)
    daemon.records.put(space, "creator", creator(), "athena")
    daemon.records.put(other, "creator", creator(), "athena")
    daemon.spaces.erase(space)
    assert daemon.store.query("SELECT COUNT(*) AS n FROM records WHERE space_id = ?", (space,))[0]["n"] == 0
    assert len(daemon.records.latest(other)) == 1
    assert daemon.records.erase(other) == 1 and daemon.records.latest(other) == []


# --- may_render -----------------------------------------------------------------------------------


def test_may_render_passes_when_every_condition_holds(disk: Daemon, tmp_path: Path) -> None:
    space = project(disk)
    key = renderable(disk, space, tmp_path)
    assert may_render(disk.records, space, key) == {"ok": True, "reasons": []}
    assert may_render(disk.records, space, key.replace("youtube.example", "YouTube.Example"))[
        "ok"
    ]  # normalised


def _only(disk: Daemon, space: str, key: str, reason: str) -> None:
    assert may_render(disk.records, space, key) == {"ok": False, "reasons": [reason]}


def test_not_kept(disk: Daemon, tmp_path: Path) -> None:
    space = project(disk)
    key = renderable(disk, space, tmp_path)
    disk.records.verdict(disk.records.latest(space, "track", key)[0]["id"], {"verdict": "later"})
    _only(disk, space, key, "not kept")


def test_no_agreement(disk: Daemon, tmp_path: Path) -> None:
    space = project(disk)
    key = renderable(disk, space, tmp_path)
    disk.store.run("DELETE FROM records WHERE kind = 'agreement'")
    _only(disk, space, key, "no agreement")


def _agreement(disk: Daemon, space: str, **change: Any) -> None:
    body = {"creator_key": CREATOR, "state": "agreed", "thread_key": "offer", "plan": "pro", **change}
    disk.records.put(space, "agreement", {k: v for k, v in body.items() if v is not None}, "person")


def test_agreement_not_agreed(disk: Daemon, tmp_path: Path) -> None:
    space = project(disk)
    key = renderable(disk, space, tmp_path)
    _agreement(disk, space, state="proposed")
    _only(disk, space, key, "agreement not agreed")


def test_no_thread_as_evidence(disk: Daemon, tmp_path: Path) -> None:
    space = project(disk)
    key = renderable(disk, space, tmp_path)
    _agreement(disk, space, thread_key="a-thread-never-kept")
    _only(disk, space, key, "no thread as evidence")


@pytest.mark.parametrize("plan", [None, "unknown"])
def test_plan_tier_unknown(disk: Daemon, tmp_path: Path, plan: str | None) -> None:
    space = project(disk)
    key = renderable(disk, space, tmp_path)
    _agreement(disk, space, plan=plan)
    _only(disk, space, key, "plan tier unknown")


def test_free_plan_cannot_be_licensed(disk: Daemon, tmp_path: Path) -> None:
    space = project(disk)
    key = renderable(disk, space, tmp_path)
    _agreement(disk, space, plan="free")
    _only(disk, space, key, "free plan cannot be licensed")


def test_no_file(disk: Daemon, tmp_path: Path) -> None:
    space = project(disk)
    key = renderable(disk, space, tmp_path)
    latest = disk.records.latest(space, "track", key)[0]["body"]
    disk.records.put(space, "track", {k: v for k, v in latest.items() if k != "file_id"}, "person")
    _only(disk, space, key, "no file")
    disk.records.put(space, "track", latest, "person")  # the file back, then its row gone
    disk.store.run("DELETE FROM files")
    _only(disk, space, key, "no file")


def test_reasons_come_in_order_and_an_unknown_track_fails_closed(daemon: Daemon) -> None:
    space = project(daemon)
    assert may_render(daemon.records, space, TRACK)["reasons"] == ["not kept", "no agreement", "no file"]
    daemon.records.put(space, "track", track(), "athena")
    daemon.records.put(
        space,
        "agreement",
        {"creator_key": CREATOR, "state": "declined", "thread_key": "x", "plan": "free"},
        "person",
    )
    assert may_render(daemon.records, space, TRACK)["reasons"] == [
        "not kept",
        "agreement not agreed",
        "no thread as evidence",
        "free plan cannot be licensed",
        "no file",
    ]
