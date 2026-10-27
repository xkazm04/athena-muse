"""The four chores' senses build and prove on fixtures, byte for byte, and the merge refuses clashes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from athena.senses import build as b
from athena.senses.__main__ import main

CHORES = ["paper-flip-through", "prior-auth-denial-appeal", "renovation-witness", "care-circle"]


@pytest.mark.parametrize("chore", CHORES)
def test_every_chore_proves_on_fixtures(chore: str) -> None:
    result = b.prove(b.build(b.context(b.chore_dir(chore))))
    failed = [
        f"{r['sense']} {r['id']} {r.get('measured')} ({r.get('note')})"
        for r in result["proofs"]
        if not r["passed"]
    ]
    assert result["passed"], failed
    assert result["backends"] == {"segmenter": "fixture", "transcriber": "fixture", "reader": "fixture"}


@pytest.mark.parametrize("chore", CHORES)
def test_committed_files_are_the_fixture_build(chore: str) -> None:
    root = b.chore_dir(chore)
    built = b.build(b.context(root))
    fresh_sensed = b.dump(b.sensed(built))
    fresh_proofs = b.dump(b.prove(built))
    assert fresh_sensed == b.dump(b.sensed(b.build(b.context(root)))), "a fixture build reads no clock"
    assert (root / "senses" / "sensed.json").read_text(encoding="utf-8") == fresh_sensed
    assert (root / "senses" / "proofs.json").read_text(encoding="utf-8") == fresh_proofs


def test_every_row_cites_its_media() -> None:
    for chore in CHORES:
        root = b.chore_dir(chore)
        ctx = b.context(root)
        built = b.build(ctx)
        ids = {m.id for m in ctx.media}
        for table, rows in built.tables.items():
            if table in ("signer_rules", "change_checks"):
                continue  # rules and checks over world rows, not media
            for row in rows:
                assert row["media_id"] in ids, (chore, table, row)
                assert None not in row.values(), (chore, table, row)


def test_paper_cites_best_frame_and_asks_disagreements() -> None:
    built = b.build(b.context(b.chore_dir("paper-flip-through")))
    sheets = {s["sheet_id"]: s for s in built.tables["sheets"]}
    assert sheets["S01"] | {} == {
        "sheet_id": "S01",
        "doc_type": "bill",
        "media_id": "pile-1",
        "frame": 4,
        "box": [0.2, 0.12, 0.84, 0.93],
        "track_id": "S01",
        "frames_seen": 3,
    }
    assert sheets["P1"]["media_id"] == "sheet-P1" and "track_id" not in sheets["P1"]
    assert "S02.due_date" in built.asked
    asked = [f for f in built.tables["sheet_fields"] if f["status"] == "asked"]
    assert all("value" not in f for f in asked)


def test_call_without_consent_keeps_no_turns() -> None:
    built = b.build(b.context(b.chore_dir("prior-auth-denial-appeal")))
    log = {r["media_id"]: r for r in built.tables["call_log"]}
    assert log["call-2"] == {
        "media_id": "call-2",
        "title": "Fernway member services, Thursday 22 October 2026, 1 min 16 s",
        "consent": "missing",
        "turns": 0,
    }
    assert not [t for t in built.tables["call_turns"] if t["media_id"] == "call-2"]
    assert "call-2.consent" in built.asked
    assert log["call-1"]["consent_second"] == 7.0


def test_walk_without_consent_keeps_counts_not_promises() -> None:
    built = b.build(b.context(b.chore_dir("renovation-witness")))
    counts = {(r["media_id"], r["item"]): r["count"] for r in built.tables["walk_counts"]}
    assert counts[("walk-w2", "outlet")] == 6
    assert not [p for p in built.tables["walk_promises"] if p["media_id"] == "walk-w2"]
    assert "walk-w2.consent" in built.asked
    zero = next(r for r in built.tables["walk_counts"] if r["media_id"] == "walk-w1")
    assert zero["count"] == 0 and "frame" not in zero


def _chore(tmp_path: Path, media: list[dict[str, object]], tables: dict[str, object]) -> Path:
    root = tmp_path / "toy"
    (root / "senses" / "fixtures").mkdir(parents=True)
    (root / "senses" / "media.json").write_text(json.dumps({"media": media}), encoding="utf-8")
    (root / "world.json").write_text(json.dumps({"tables": tables}), encoding="utf-8")
    return root


def test_a_sensed_table_never_shadows_a_world_table(tmp_path: Path) -> None:
    sheet = {
        "id": "s1",
        "kind": "paper",
        "sense": "paper",
        "params": {"sheet_id": "s1", "doc_type": "bill", "fields": []},
    }
    root = _chore(tmp_path, [sheet], {"sheets": []})
    with pytest.raises(b.SenseError, match="shadow"):
        b.build(b.context(root))


def test_two_senses_writing_one_table_are_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from athena.senses.contract import SenseOutput

    class Clash:
        name = "call"

        def build(self, ctx: object) -> SenseOutput:
            return SenseOutput("call", {"sheets": []})

    monkeypatch.setitem(b.SENSES, "call", Clash())
    media = [
        {
            "id": "s1",
            "kind": "paper",
            "sense": "paper",
            "params": {"sheet_id": "s1", "doc_type": "bill", "fields": []},
        },
        {"id": "c1", "kind": "audio", "sense": "call", "params": {}},
    ]
    root = _chore(tmp_path, media, {})
    with pytest.raises(b.SenseError, match="both write"):
        b.build(b.context(root))


def test_cli_writes_elsewhere_and_reports(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "proofs.json"
    assert main(["prove", "renovation-witness", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["passed"] is True
    assert "passed" in capsys.readouterr().out
    assert main(["status", "renovation-witness"]) == 0
    assert main(["build", "no-such-chore"]) == 2
