"""`python -m athena.senses build|prove|render|status <chore>`, with `--segmenter`, `--transcriber`
and `--reader` choosing each role's backend for this run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from athena.engine import EngineError
from athena.senses import build as b
from athena.senses.contract import READERS, SEGMENTERS, TRANSCRIBERS
from athena.senses.render import render_sheets


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m athena.senses", description="Build and prove a chore's senses."
    )
    p.add_argument("command", choices=["build", "prove", "render", "status"])
    p.add_argument("chore", help="a chore id under playbooks/, or a path to a chore folder")
    p.add_argument("--segmenter", choices=SEGMENTERS)
    p.add_argument("--transcriber", choices=TRANSCRIBERS)
    p.add_argument("--reader", choices=READERS)
    p.add_argument("--out", type=Path, help="write the result here instead of senses/ (prove and build)")
    return p


def _status(root: Path) -> str:
    senses = root / "senses"
    media, _ = b.load_media(senses)
    kinds: dict[str, int] = {}
    for m in media:
        kinds[f"{m.sense}/{m.kind}"] = kinds.get(f"{m.sense}/{m.kind}", 0) + 1
    lines = [f"{root.name}: " + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items()))]
    for name in ("sensed.json", "proofs.json"):
        path = senses / name
        if not path.is_file():
            lines.append(f"  {name}: not built")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        roles = ", ".join(f"{k} {v}" for k, v in data.get("backends", {}).items())
        if name == "sensed.json":
            calls, asked = len(data.get("calls", [])), len(data.get("asked", []))
            lines.append(f"  sensed.json: {calls} calls, {asked} asked; {roles}")
        else:
            rows = data.get("proofs", [])
            ok = sum(1 for r in rows if r.get("passed"))
            lines.append(f"  proofs.json: {ok} of {len(rows)} passed; {roles}")
    png = list((senses / "render").glob("*.png")) if (senses / "render").is_dir() else []
    lines.append(f"  render: {len(png)} PNG(s)")
    return "\n".join(lines)


def _proof_lines(result: dict[str, Any]) -> list[str]:
    out = []
    for r in result.get("proofs", []):
        mark = "pass" if r["passed"] else "FAIL"
        got = r.get("measured", "-")
        head = f"  {mark}  {r['sense']:<6} {r['id']:<4} {got} {r['op']} {r['bar']}  n={r['n']}"
        out.append(f"{head}  {r.get('note', '')}")
    return out


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        root = b.chore_dir(args.chore)
        if args.command == "status":
            print(_status(root))
            return 0
        chosen = {"segmenter": args.segmenter, "transcriber": args.transcriber, "reader": args.reader}
        ctx = b.context(root, chosen)
        if args.command == "render":
            written, note = render_sheets(ctx.senses_dir, ctx.media, ctx.tables)
            print(note or f"{len(written)} sheet(s) rendered to {ctx.senses_dir / 'render'}")
            return 0 if not note else 1
        built = b.build(ctx)
        if args.command == "build":
            data = b.sensed(built)
            path = args.out or ctx.senses_dir / "sensed.json"
            b.write(path, data)
            print(
                f"{root.name}: {len(data['calls'])} calls, {len(data['asked'])} asked, "
                f"${data['cost_usd']:.4f} ({data['unpriced_calls']} unpriced) -> {path}"
            )
            return 0
        result = b.prove(built)
        path = args.out or ctx.senses_dir / "proofs.json"
        b.write(path, result)
        total, unpriced = b.cost(ctx.calls)
        print(
            f"{root.name}: {'passed' if result['passed'] else 'FAILED'} on {result['backends']}; "
            f"{len(ctx.calls)} calls, ${total:.4f} ({unpriced} unpriced) -> {path}"
        )
        print("\n".join(_proof_lines(result)))
        return 0 if result["passed"] else 1
    except (b.SenseError, EngineError, ValueError) as e:
        reason = e.reason if isinstance(e, EngineError) else str(e)
        print(f"senses: {reason}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
