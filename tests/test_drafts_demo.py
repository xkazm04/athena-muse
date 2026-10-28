"""The staged-need demo walks write -> preview -> key -> test run and keeps a record; an older database
gains the drafts' `expected` column."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from athena.drafts import demo
from athena.store import Store
from drafts_kit import Fake


def test_the_demo_walks_the_staged_need_to_a_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(demo, "build_engine", lambda *a, **k: Fake())
    assert demo.main(["--data", str(tmp_path / "data")]) == 0
    out = capsys.readouterr().out
    for line in ("written: the-club-invoice", "preview: 3 cards", "phase 2 on club", "  card: ", "scored: "):
        assert line in out, line
    (record,) = (tmp_path / "data" / "runs").glob("*/demo.json")
    doc = json.loads(record.read_text(encoding="utf-8"))
    assert doc["draft"]["step"] == "verdict" and doc["events"]["rehearse"][-1]["type"] == "scored"
    assert {r["surface"] for r in doc["model_calls"]} == {"design", "rehearsal"}


def test_the_demo_on_the_scripted_engine_stops_at_authoring_and_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ATHENA_ENGINE", "scripted")
    assert demo.main(["--data", str(tmp_path / "data")]) == 1
    out = capsys.readouterr().out
    assert "author_failed" in out and "cannot write a chore" in out


def test_an_older_database_gains_the_expected_column(tmp_path: Path) -> None:
    path = tmp_path / "athena.db"
    db = sqlite3.connect(path)
    columns = (
        "id TEXT PRIMARY KEY, space_id TEXT NOT NULL, step TEXT NOT NULL, need TEXT NOT NULL,"
        " sketch TEXT NOT NULL, coverage TEXT NOT NULL, skipped TEXT NOT NULL DEFAULT '[]',"
        " asked TEXT NOT NULL DEFAULT '{}', chore_id TEXT, key TEXT, bench TEXT, verdict TEXT, note TEXT,"
        " created TEXT NOT NULL, updated TEXT NOT NULL"
    )
    db.execute(f"CREATE TABLE drafts ({columns})")  # as WP1 shipped it, before `expected`
    db.close()
    store = Store(path)
    assert "expected" in {r["name"] for r in store.query("PRAGMA table_info(drafts)")}
    store.close()
