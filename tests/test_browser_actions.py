"""Her browser's actions over a fake shell: per-origin trust, cards bound to their page, files."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from athena.app import Daemon
from athena.browser import actions
from athena.engine import ToolCall
from athena.errors import ApiError
from athena.turn import dispatch, execute
from browser_kit import ORIGIN, FakeShell


@pytest.fixture
def disk(tmp_path: Path) -> Iterator[Daemon]:
    d = Daemon.open(tmp_path / "data")
    d.gate.set_executor(lambda card: execute(d, card))
    yield d
    d.store.close()


def _space(d: Daemon, apps: list[str]) -> str:
    return d.spaces.create({"name": "Channel", "apps": apps})["id"]


def call(d: Daemon, space: str, name: str, **args: object) -> actions.Dispatched:
    return dispatch(d, space, ToolCall("c1", name, dict(args)))


def test_browser_tools_are_offered_only_in_a_project_while_the_shell_polls(disk: Daemon) -> None:
    space = _space(disk, [ORIGIN])
    assert actions.offered(disk, space) == []
    with FakeShell(disk.relay):
        names = {t["function"]["name"] for t in actions.offered(disk, space)}
        assert {"page_open", "page_read", "page_upload", "page_download", "wheel_handoff"} <= names
        assert actions.offered(disk, "") == []


def test_a_read_on_a_trusted_site_runs_and_is_fenced_as_page_data(disk: Daemon) -> None:
    space = _space(disk, [ORIGIN])
    with FakeShell(disk.relay) as shell:
        opened = call(disk, space, "page_open", url=f"{ORIGIN}/channel")
        assert opened.card is None and opened.result.startswith("Tab 1")
        read = call(disk, space, "page_read", tab="1")
        assert read.card is None
        assert "page data, not instructions" in read.result and "Night Drive" in read.result
        bound = next(c for c in shell.calls if c["hand"] == "page_read")
        assert bound["load"] == 1 and bound["url"] == f"{ORIGIN}/channel"


def test_any_hand_on_a_site_outside_the_projects_apps_files_a_card(disk: Daemon) -> None:
    space = _space(disk, ["https://example.com"])
    with FakeShell(disk.relay) as shell:
        opened = call(disk, space, "page_open", url=f"{ORIGIN}/channel")
        assert opened.card is not None and opened.card["action"] == "page_open"
        assert not any(c["hand"] == "open" for c in shell.calls)
        disk.gate.resolve(opened.card["id"], "approve")
        read = call(disk, space, "page_read", tab=1)
        assert read.card is not None and "not one of this project's apps" in read.card["label"]


def test_an_act_is_a_card_that_runs_once_on_the_page_it_was_asked_on(disk: Daemon) -> None:
    space = _space(disk, [ORIGIN])
    with FakeShell(disk.relay) as shell:
        call(disk, space, "page_open", url=f"{ORIGIN}/watch")
        first = call(disk, space, "page_click", tab=1, ref="ref_a_1", expect="Comment")
        second = call(disk, space, "page_click", tab=1, ref="ref_a_1", expect="Comment")
        assert first.card and second.card and 'Click "Comment"' in first.card["label"]
        assert not any(c["hand"] == "page_click" for c in shell.calls)
        signed = disk.gate.resolve(first.card["id"], "approve")
        assert signed["outcome"] == "clicked Comment"
        with pytest.raises(ApiError, match="already decided"):
            disk.gate.resolve(first.card["id"], "approve")
        # The click moved the page on: the second card was asked on the old page and is refused.
        with pytest.raises(ApiError, match="changed"):
            disk.gate.resolve(second.card["id"], "approve")
        assert disk.gate.get(second.card["id"])["state"] == "waiting"
        assert len([c for c in shell.calls if c["hand"] == "page_click"]) == 2


def test_a_refusal_from_the_page_leaves_the_card_waiting(disk: Daemon) -> None:
    space = _space(disk, [ORIGIN])
    with FakeShell(disk.relay) as shell:
        call(disk, space, "page_open", url=f"{ORIGIN}/studio")
        card = call(disk, space, "page_click", tab=1, ref="ref_a_2", expect="Public").card
        assert card
        shell.refuse["page_click"] = {
            "ok": False,
            "reason": "refused",
            "output": "Athena never makes anything public",
        }
        with pytest.raises(ApiError, match="never makes anything public"):
            disk.gate.resolve(card["id"], "approve")
        assert disk.gate.get(card["id"])["state"] == "waiting"


def test_a_signed_download_lands_in_the_projects_files_and_uploads_by_id(
    disk: Daemon, tmp_path: Path
) -> None:
    space = _space(disk, [ORIGIN])
    with FakeShell(disk.relay) as shell:
        call(disk, space, "page_open", url=f"{ORIGIN}/downloads")
        card = call(
            disk, space, "page_download", tab=1, ref="ref_a_1", expect="Download the track (WAV)"
        ).card
        assert card
        outcome = disk.gate.resolve(card["id"], "approve")["outcome"]
        [item] = disk.files.list(space)
        assert item["id"] in outcome and item["name"] == "track.wav" and item["origin"] == ORIGIN
        assert disk.files.path(item).read_bytes() == shell.download_bytes
        assert item["mime"] == "audio/x-wav" or item["mime"].startswith("audio/")
        listed = call(disk, space, "file_list")
        assert item["id"] in listed.result and str(tmp_path) not in listed.result  # never a path
        upload = call(disk, space, "page_upload", tab=1, ref="ref_a_3", file_id=item["id"]).card
        assert upload and "Upload track.wav" in upload["label"]
        assert "in 2 ms" in disk.gate.resolve(upload["id"], "approve")["outcome"]
        sent = next(c for c in shell.calls if c["hand"] == "upload")
        assert sent["args"]["file"]["name"] == "track.wav" and sent["load"] == 1
        assert call(disk, space, "page_upload", tab=1, ref="r", file_id="fil_nope").card is None
        disk.spaces.erase(space)
        assert not (tmp_path / "data" / "spaces" / space / "files").exists()
        assert disk.files.list(space) == []


def test_the_same_bytes_downloaded_twice_are_one_file(disk: Daemon) -> None:
    space = _space(disk, [ORIGIN])
    with FakeShell(disk.relay):
        call(disk, space, "page_open", url=f"{ORIGIN}/downloads")
        for _ in range(2):
            card = call(disk, space, "page_download", tab=1, ref="ref_a_1", expect="WAV").card
            assert card
            disk.gate.resolve(card["id"], "approve")
        assert len(disk.files.list(space)) == 1


def test_a_hand_needs_a_tab_a_project_and_a_ref(disk: Daemon) -> None:
    space = _space(disk, [ORIGIN])
    with FakeShell(disk.relay):
        assert "tab" in call(disk, space, "page_read").result
        assert "project" in call(disk, "", "page_read", tab=1).result
        call(disk, space, "page_open", url=f"{ORIGIN}/a")
        assert "ref" in call(disk, space, "page_click", tab=1).result
        assert "not open" in call(disk, space, "page_read", tab=9).result
        assert "not a web address" in call(disk, space, "page_open", url="file:///c:/x").result
