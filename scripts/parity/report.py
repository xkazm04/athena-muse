"""Folds a parity run's run.json files, grades.json and blind.json into report.md.

    python scripts/parity/report.py runs/parity/<stamp> [--reference claude_code] [--allow-ungraded]
    python scripts/parity/report.py runs/parity/<stamp> --against runs/parity/<earlier>

--against compares two runs of the same engine set case by case instead (it writes
against-<earlier>.md next to report.md): blind ids differ between runs, so each run's blind.json maps
its folders to (case, engine).

The blind ids are revealed only here, so the report is written after grading: it refuses while any
grade is missing unless --allow-ungraded (then the grade clause reads "ungraded", never a pass).

The bar, per case, for each engine against the reference engine (the design's "parity within margin"):
  end    - the expected end state and no blocker
  grade  - overall grade (mean of the five) within 1 of the reference's
  turns  - turns to agreed <= the reference's + 2
  test   - found / of >= 0.8 where a test ran
  calls  - no model call over 60 s
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

GRADE_KEYS = ("logic", "no_repeats", "clarity", "progress", "fidelity")

# run.json: field -> type(s); a dotted name is a nested field. None means "may be null".
SCHEMA: dict[str, tuple[Any, ...]] = {
    "case": (int,),
    "blind_id": (str,),
    "engine": (str,),
    "model": (str, type(None)),
    "end": (dict,),
    "end.step": (str, type(None)),
    "end.expected": (str,),
    "end.ok": (bool,),
    "blocker": (str, type(None)),
    "turns": (dict,),
    "turns.to_agreed": (int, type(None)),
    "turns.total": (int,),
    "asks": (list,),
    "repeated_asks": (int,),
    "repairs": (int,),
    "author_failed": (bool,),
    "test": (dict, type(None)),
    "calls": (dict,),
    "calls.n": (int,),
    "calls.latency_ms_p50": (int, type(None)),
    "calls.latency_ms_max": (int, type(None)),
    "calls.over_60s": (int,),
    "calls.tokens_in": (int,),
    "calls.tokens_out": (int,),
    "calls.cost_usd": (float, int, type(None)),
    "calls.failed": (int,),
    "ui": (dict,),
    "ui.slow_notices": (int,),
    "ui.failures": (int,),
    "ui.retries": (int,),
    "ui.scroll_problems": (list,),
    "ui.console_errors": (list,),
    "ui.banned_words": (list,),
    "wall_s": (float, int),
}


def check_run(rec: dict[str, Any]) -> list[str]:
    """What in a run.json breaks the schema; empty when it is valid."""
    problems = []
    for name, types in SCHEMA.items():
        value: Any = rec
        for part in name.split("."):
            if not isinstance(value, dict) or part not in value:
                problems.append(f"{name}: missing")
                value = None
                break
            value = value[part]
        else:
            if isinstance(value, bool) and bool not in types:
                problems.append(f"{name}: a bool where {types} belongs")
            elif not isinstance(value, types):
                problems.append(f"{name}: {type(value).__name__} is not {[t.__name__ for t in types]}")
    for i, a in enumerate(rec.get("asks") or []):
        if not (isinstance(a, dict) and {"slot", "text", "suggestions"} <= set(a)):
            problems.append(f"asks[{i}]: needs slot, text, suggestions")
    test = rec.get("test")
    if isinstance(test, dict) and not {"found", "of", "verdict"} <= set(test):
        problems.append("test: needs found, of, verdict")
    return problems


def overall(g: dict[str, Any] | None) -> float | None:
    if not g:
        return None
    vals = [g.get(k) for k in GRADE_KEYS]
    if any(not isinstance(v, int | float) for v in vals):
        return None
    return sum(vals) / len(vals)  # type: ignore[arg-type]


def clauses(run: dict[str, Any], ref: dict[str, Any] | None, grades: dict[str, Any]) -> dict[str, str]:
    """Each bar clause as 'pass', 'fail (...)', 'n/a' or 'ungraded'."""
    out: dict[str, str] = {}
    ok = run["end"]["ok"] and run["blocker"] is None
    out["end"] = "pass" if ok else f"fail ({run['end']['step']}; {run['blocker'] or 'not the expected end'})"
    mine = overall(grades.get(run["blind_id"]))
    if ref is None:
        out["grade"] = out["turns"] = "n/a"
    else:
        theirs = overall(grades.get(ref["blind_id"]))
        if mine is None or theirs is None:
            out["grade"] = "ungraded"
        else:
            out["grade"] = "pass" if abs(mine - theirs) <= 1 else f"fail ({mine:.1f} vs {theirs:.1f})"
        a, b = run["turns"]["to_agreed"], ref["turns"]["to_agreed"]
        if b is None:
            out["turns"] = "n/a" if a is None else "pass"
        elif a is None:
            out["turns"] = f"fail (never agreed; reference {b})"
        else:
            out["turns"] = "pass" if a <= b + 2 else f"fail ({a} vs {b} + 2)"
    t = run.get("test")
    if not t or not t.get("of"):
        out["test"] = "n/a"
    else:
        ratio = (t.get("found") or 0) / t["of"]
        out["test"] = "pass" if ratio >= 0.8 else f"fail ({t.get('found')} of {t['of']})"
    over = run["calls"]["over_60s"]
    out["calls"] = "pass" if over == 0 else f"fail ({over} over 60 s)"
    return out


def verdict(c: dict[str, str]) -> str:
    if any(v.startswith("fail") for v in c.values()):
        return "FAIL"
    if "ungraded" in c.values():
        return "ungraded"
    return "pass"


def cell(v: Any) -> str:
    return "-" if v is None else str(v)


def load_runs(root: Path) -> dict[tuple[int, str], dict[str, Any]]:
    """(case, engine) -> run.json of one run folder, through its blind.json."""
    blind = json.loads((root / "blind.json").read_text(encoding="utf-8"))
    out: dict[tuple[int, str], dict[str, Any]] = {}
    for bid, meta in blind.items():
        path = root / f"{int(meta['case']):02d}-{bid}" / "run.json"
        if path.exists():
            out[(int(meta["case"]), str(meta["engine"]))] = json.loads(path.read_text(encoding="utf-8"))
    return out


def _metrics(r: dict[str, Any] | None, grades: dict[str, Any]) -> dict[str, Any]:
    if r is None:
        return dict.fromkeys(("grade", "turns", "test", "p50", "max", "blocker"))
    t = r.get("test")
    return {
        "grade": overall(grades.get(r["blind_id"])),
        "turns": r["turns"]["to_agreed"],
        "test": (t.get("found") or 0) / t["of"] if t and t.get("of") else None,
        "p50": r["calls"]["latency_ms_p50"],
        "max": r["calls"]["latency_ms_max"],
        "blocker": r["blocker"],
    }


def _delta(a: Any, b: Any, digits: int = 1) -> str:
    """'a (b, +d)': this run's value, the other's, the change; '-' where either is missing."""
    if a is None and b is None:
        return "-"
    if a is None or b is None:
        return f"{cell(_round(a, digits))} ({cell(_round(b, digits))})"
    d = a - b
    return f"{_round(a, digits)} ({_round(b, digits)}, {'+' if d >= 0 else ''}{_round(d, digits)})"


def _round(v: Any, digits: int) -> Any:
    if isinstance(v, float):
        return round(v, digits) if digits else round(v)
    return v


def against(root: Path, other: Path) -> str:
    """The per-case delta table between two runs: this run's value (the other's, the change)."""
    mine, theirs = load_runs(root), load_runs(other)
    gm, gt = (
        json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        for p in (root / "grades.json", other / "grades.json")
    )
    lines = [
        f"# Onboarding parity - {root.name} against {other.name}\n",
        "Each cell: this run (the other run, the change). Grade: the mean of the five; test: found / of.\n",
        "| case | engine | grade | turns to agreed | test | calls p50 ms | calls max ms | blocker |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for case, engine in sorted(set(mine) | set(theirs)):
        a, b = _metrics(mine.get((case, engine)), gm), _metrics(theirs.get((case, engine)), gt)
        if a["blocker"] == b["blocker"]:
            blocker = "same" if a["blocker"] else "-"
        else:
            blocker = f"{cell(a['blocker'])} (was {cell(b['blocker'])})"
        lines.append(
            f"| {case} | {engine} | {_delta(a['grade'], b['grade'])} | {_delta(a['turns'], b['turns'])} | "
            f"{_delta(a['test'], b['test'], 2)} | {_delta(a['p50'], b['p50'], 0)} | "
            f"{_delta(a['max'], b['max'], 0)} | {blocker} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--reference", default="claude_code", help="the engine the others are measured against")
    ap.add_argument("--allow-ungraded", action="store_true")
    ap.add_argument("--against", type=Path, help="another run's out dir: a per-case delta table instead")
    args = ap.parse_args()
    root: Path = args.out
    if args.against:
        text = against(root, args.against)
        path = root / f"against-{args.against.resolve().name}.md"
        path.write_text(text, encoding="utf-8")
        print(text)
        print(f"wrote {path}")
        return
    blind = json.loads((root / "blind.json").read_text(encoding="utf-8"))
    grades_path = root / "grades.json"
    grades = json.loads(grades_path.read_text(encoding="utf-8")) if grades_path.exists() else {}
    runs: dict[str, dict[str, Any]] = {}
    for p in sorted(root.glob("*/run.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        bad = check_run(rec)
        if bad:
            raise SystemExit(f"{p}: run.json breaks the schema: {bad}")
        runs[rec["blind_id"]] = rec
    missing = [b for b in runs if overall(grades.get(b)) is None]
    if missing and not args.allow_ungraded:
        raise SystemExit(
            f"{len(missing)} run(s) are not graded yet ({', '.join(sorted(missing))}); grade grades.json "
            "first (the report reveals the engines), or pass --allow-ungraded"
        )

    engines = sorted({m["engine"] for m in blind.values()}, key=lambda e: (e != args.reference, e))
    cases = sorted({int(m["case"]) for m in blind.values()})
    lines = [f"# Onboarding parity - {root.name}\n", f"Reference engine: `{args.reference}`.\n"]
    lines.append("| engine | model | runs | end ok | pass | fail | ungraded |\n|---|---|---|---|---|---|---|")
    summary: dict[str, list[str]] = {e: [] for e in engines}
    per_case: list[str] = []
    for case in cases:
        here = {r["engine"]: r for r in runs.values() if r["case"] == case}
        ref = here.get(args.reference)
        per_case.append(f"\n## Case {case} - {next(iter(here.values()))['extra']['name'] if here else '?'}\n")
        rows = [
            ("blind id", lambda r: r["blind_id"]),
            ("end step", lambda r: r["end"]["step"]),
            ("blocker", lambda r: r["blocker"]),
            ("turns to agreed", lambda r: r["turns"]["to_agreed"]),
            ("turns total", lambda r: r["turns"]["total"]),
            ("asks / repeated", lambda r: f"{len(r['asks'])} / {r['repeated_asks']}"),
            ("repairs", lambda r: r["repairs"]),
            (
                "test",
                lambda r: r["test"] and f"{r['test']['found']} of {r['test']['of']} ({r['test']['verdict']})",
            ),
            ("calls", lambda r: r["calls"]["n"]),
            (
                "latency p50 / max ms",
                lambda r: f"{r['calls']['latency_ms_p50']} / {r['calls']['latency_ms_max']}",
            ),
            ("calls over 60 s", lambda r: r["calls"]["over_60s"]),
            ("tokens in / out", lambda r: f"{r['calls']['tokens_in']} / {r['calls']['tokens_out']}"),
            ("cost USD", lambda r: r["calls"]["cost_usd"]),
            (
                "slow / failed / retried",
                lambda r: f"{r['ui']['slow_notices']} / {r['ui']['failures']} / {r['ui']['retries']}",
            ),
            ("banned words", lambda r: ", ".join(r["ui"]["banned_words"]) or None),
            ("scroll problems", lambda r: len(r["ui"]["scroll_problems"])),
            ("console errors", lambda r: len(r["ui"]["console_errors"])),
            ("grade (mean)", lambda r: (lambda o: o and round(o, 1))(overall(grades.get(r["blind_id"])))),
            ("wall s", lambda r: round(r["wall_s"])),
        ]
        present = [e for e in engines if e in here]
        per_case.append("| | " + " | ".join(present) + " |\n|---|" + "---|" * len(present))
        for label, fn in rows:
            per_case.append(f"| {label} | " + " | ".join(cell(fn(here[e])) for e in present) + " |")
        for e in present:
            r = here[e]
            c = clauses(r, ref if e != args.reference else None, grades)
            v = verdict(c)
            summary[e].append(v)
            per_case.append(f"\n**{e}: {v}** - " + "; ".join(f"{k}: {val}" for k, val in c.items()))
            note = (grades.get(r["blind_id"]) or {}).get("note")
            if note:
                per_case.append(f"\n> {note}")
    for e in engines:
        mine = [r for r in runs.values() if r["engine"] == e]
        vs = summary[e]
        model = next((r["model"] for r in mine if r["model"]), "default")
        lines.append(
            f"| {e} | {model} | {len(mine)} | {sum(1 for r in mine if r['end']['ok'])} | "
            f"{vs.count('pass')} | {vs.count('FAIL')} | {vs.count('ungraded')} |"
        )
    text = "\n".join(lines + per_case) + "\n"
    (root / "report.md").write_text(text, encoding="utf-8")
    print(f"wrote {root / 'report.md'}")


if __name__ == "__main__":
    main()
