"""`python -m athena.drafts.demo --data <dir> [--runs <dir>]`: the staged need, end to end.

Seeds an agreed sketch for the staged need directly (no shaping turns), then walks write -> preview ->
key (yes to every card) -> test run on the engine `ATHENA_ENGINE` picks (ADR 0006), printing each
event. The whole record (events, cards, the draft, its model calls) is written to
`<runs>/<stamp>-<chore id>/demo.json`, `<data>/runs` by default. The scripted engine cannot write a
chore, so a run without a real engine stops at authoring and says so.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from athena.app import Daemon
from athena.contracts import Draft, KeyBody, LedgerRow, Sketch
from athena.drafts import author, key, preview, rehearse, shape
from athena.engine import EngineError, build_engine
from athena.errors import ApiError
from athena.keys import KeyStore

NEED = (
    "Each month I check the after-school club's invoice against the days my kids actually went "
    "(the school portal has attendance) and dispute the extra days."
)

_NODES = (
    ("n1", "step", "need", "Check the club invoice against attendance"),
    ("n2", "app", "apps", "The school portal"),
    ("n3", "app", "apps", "The club's billing page"),
    ("n4", "source", "inputs", "Attendance days per child"),
    ("n5", "step", "steps", "Compare each billed day with attendance"),
    ("n6", "gate", "hand", "Each dispute waits for my signature"),
    ("n7", "output", "output", "A list of disputed days"),
    ("n8", "never", "never", "Never pay the invoice"),
)


def staged_sketch() -> Sketch:
    """The staged need's sketch, agreed: every node the person's own and confirmed."""
    nodes = [
        {"id": i, "kind": k, "slot": s, "label": label, "origin": "you", "confirmed": True}
        for i, k, s, label in _NODES
    ]
    edges = [{"from": "n2", "to": "n5"}, {"from": "n3", "to": "n5"}, {"from": "n5", "to": "n6"}]
    return cast("Sketch", {"nodes": nodes, "edges": edges})


def seed(daemon: Daemon) -> Draft:
    """A draft of the staged need at `shape` with the agreed sketch."""
    draft = shape.start(daemon, NEED)
    return daemon.drafts.put(cast("Draft", {**draft, "sketch": staged_sketch(), "step": "shape"}))


def _say(event: dict[str, Any]) -> str:
    kind = event.get("type")
    if kind == "repair" or kind == "author_failed":
        return f"{kind}:\n" + "\n".join(f"  - {p}" for p in event["problems"])
    if kind == "written":
        return f"written: {event['chore_id']}"
    if kind == "phase":
        return f"phase {event['index']} on {event['app']}: {event['message']}"
    if kind == "card":
        return f"  card: {event['card']['label']}"
    if kind == "scored":
        b = event["bench"]
        return (
            f"scored: {b['verdict']} - found {b['found']} of {b['eligible']}, {b['false_claims']} false, "
            f"{b['traps_filed']} traps, {b['duplicates']} duplicates; {b['turns']} turns, {b['minutes']} min"
        )
    if kind == "error":
        return f"error ({event['error']}): {event['reason']}"
    return str(kind)


def _costs(rows: list[LedgerRow]) -> str:
    by: dict[str, list[LedgerRow]] = {}
    for r in rows:
        by.setdefault(r["surface"], []).append(r)
    parts = []
    for surface, rs in by.items():
        priced = [r["cost_usd"] for r in rs if "cost_usd" in r]
        est = " est." if any(r["cost_estimated"] for r in rs if "cost_usd" in r) else ""
        cost = f"${sum(priced):.2f}{est}" if priced else "unpriced (on the plan)"
        parts.append(f"{surface}: {len(rs)} calls, {cost}")
    return "; ".join(parts) or "no model calls"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m athena.drafts.demo", description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, required=True, help="a data folder for this run (a scratch one)")
    parser.add_argument("--runs", type=Path, help="where the record goes (default <data>/runs)")
    args = parser.parse_args(argv)
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")

    daemon = Daemon.open(args.data)
    record: dict[str, Any] = {"need": NEED, "events": {}}
    try:
        try:
            engine = build_engine(KeyStore(args.data))
        except EngineError as e:
            print(f"no engine: {e.reason}", file=sys.stderr)
            return 2
        label = " (simulated)" if engine.simulated else ""
        print(f"demo on {engine.id} ({engine.model}){label}", flush=True)
        record["engine"] = {"engine": engine.id, "model": engine.model, "simulated": engine.simulated}
        draft = seed(daemon)
        print(f"draft {draft['id']} in project {draft['space_id']}, sketch agreed: {draft['agreed']}")

        written: list[dict[str, Any]] = []
        record["events"]["write"] = written
        for event in author.write(daemon, engine, draft["id"]):
            written.append(event)
            print(_say(event), flush=True)
        if daemon.drafts.get(draft["id"])["step"] != "preview":
            if engine.simulated:
                print("the scripted engine cannot write a chore; set ATHENA_ENGINE=claude_code")
            return 1

        cards = preview.preview(daemon, engine, draft["id"])
        record["expected"] = cards
        print(f"preview: {len(cards)} cards she expects to file")
        for c in cards:
            print(f"  {c['id']} {c['app']}.{c['tool']} {c['key']}: {c['label']} - {c['why']}")

        body: KeyBody = {
            "marks": [{"expected_id": c["id"], "mark": "yes"} for c in cards],
            "missing": [],
            "never": [],
        }
        key.put_key(daemon, engine, draft["id"], body)
        print("key: yes to every card", flush=True)

        run: list[dict[str, Any]] = []
        record["events"]["rehearse"] = run
        for event in rehearse.rehearse(daemon, engine, draft["id"]):
            run.append(event)
            print(_say(event), flush=True)

        final = daemon.drafts.get(draft["id"])
        rows = [r for r in daemon.ledger.page(10_000)["rows"] if r["space_id"] == draft["space_id"]]
        record.update(draft=final, model_calls=list(reversed(rows)))
        print(f"step: {final['step']}; model calls: {_costs(rows)}")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        name = f"{stamp}-{final.get('chore_id', draft['id'])}"
        out = (args.runs or args.data / "runs") / name / "demo.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"record {out}")
        return 0 if final["step"] == "verdict" else 1
    except ApiError as e:
        print(f"stopped: {e.reason}", file=sys.stderr)
        return 1
    finally:
        daemon.store.close()


if __name__ == "__main__":
    raise SystemExit(main())
