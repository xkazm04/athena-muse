"""`python -m athena.bench <id> [--engine E] [--model M] [--no-write] [--wall-min N]`."""

from __future__ import annotations

import argparse
import os
import sys

from athena.bench import runner
from athena.chores.spec import ChoreError, library_dir, load_chore
from athena.engine import EngineError, build_engine
from athena.keys import KeyStore

ENGINE_ENV = "ATHENA_ENGINE"
MODEL_ENV = "ATHENA_MODEL"


def _money(v: float) -> str:
    return f"${v:,.2f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m athena.bench", description="Rehearse one chore.")
    parser.add_argument("chore", help="the chore id, a folder under playbooks/")
    parser.add_argument("--engine", help="muse, muse_code, claude_code or scripted (sets ATHENA_ENGINE)")
    parser.add_argument("--model", help="the model the engine runs (sets ATHENA_MODEL)")
    parser.add_argument("--no-write", action="store_true", help="do not write playbooks/<id>/bench.json")
    parser.add_argument("--wall-min", type=float, default=runner.WALL_MIN_DEFAULT, help="wall clock cap")
    args = parser.parse_args(argv)

    if args.engine:
        os.environ[ENGINE_ENV] = args.engine
    if args.model:
        os.environ[MODEL_ENV] = args.model
    try:
        chore = load_chore(library_dir() / args.chore)
    except ChoreError as e:
        print(f"that chore does not load: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"no chore {args.chore!r}: {e}", file=sys.stderr)
        return 2
    try:
        engine = build_engine(KeyStore(None))
    except EngineError as e:
        print(f"no engine: {e.reason}", file=sys.stderr)
        return 2

    print(f"bench {chore.id} on {engine.id} ({engine.model}), wall clock {args.wall_min:g} min", flush=True)

    def line(t: runner.TurnLog) -> None:
        cards = f"{t.cards} card" + ("" if t.cards == 1 else "s")
        calls = f"{t.calls} call" + ("" if t.calls == 1 else "s")
        tail = f" - error: {t.error}" if t.error else ""
        print(f"phase {t.phase} turn {t.turn}: {calls}, {cards}{tail}", flush=True)

    run = runner.rehearse(chore, engine, wall_min=args.wall_min, on_turn=line)
    s = run.summary
    cost = _money(s["cost_usd"]) if "cost_usd" in s else "$?"
    value = f"{_money(s['value_found_usd'])} of {_money(s['value_total_usd'])}"
    print(
        f"found {s['found']}/{s['eligible']} ({value}),"
        f" exact {run.exact}, false {s['false_claims']}, dup {s['duplicates']};"
        f" {s['turns']} turns, {s['minutes']:.1f} min, {cost}"
    )
    print(f"verdict: {s['verdict']}")
    for reason in s["reasons"]:
        print(f"  - {reason}")
    for key in run.missed:
        print(f"  missed {key}")
    if not args.no_write:
        print(f"wrote {runner.write_bench(chore, run)}")
    print(f"report {runner.write_report(chore, run)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
