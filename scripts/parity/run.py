"""The onboarding parity runner: the real chore-onboarding stage, driven in Chrome through the use cases
in cases.py, one lane per engine in parallel, the persona answering. See README.md.

    python scripts/parity/run.py --engines claude_code,muse_code --cases 1-10 --out runs/parity/<stamp> \
        [--model muse_code=muse-spark-1.3] [--model claude_code=sonnet] [--view drawing]

Run with the system python (Playwright for Python lives there, not in uv's environment).
"""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import string
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cases import CASES, parse_cases
from drive import REPO, CaseRun, Lane, kill_tree, port_free, start_vite
from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
from report import GRADE_KEYS

# Lane ports: lane 0 daemon 8790 / app 1440, lane 1 8795 / 1445; the scripted dry runs 8792 / 1442.
LANE_PORTS = ((8790, 1440), (8795, 1445))
SCRIPTED_PORTS = (8792, 1442)
ALPHABET = string.ascii_lowercase + string.digits

print_lock = threading.Lock()


def say(lane: str, line: str) -> None:
    with print_lock:
        print(f"{time.strftime('%H:%M:%S')} [{lane}] {line}", flush=True)


def blind_ids(n: int) -> list[str]:
    ids: set[str] = set()
    while len(ids) < n:
        ids.add("".join(secrets.choice(ALPHABET) for _ in range(4)))
    out = list(ids)
    secrets.SystemRandom().shuffle(out)
    return out


def plan(engines: list[str], cases: list[int], root: Path) -> dict[tuple[str, int], str]:
    """A blind id per (engine, case); blind.json and the grades template are written up front, so a
    crashed lane still leaves a complete key. Ids are random, so neither the id nor the folder order
    tells the engines of one case apart."""
    pairs = [(e, c) for c in cases for e in engines]
    ids = blind_ids(len(pairs))
    assigned = dict(zip(pairs, ids, strict=True))
    root.mkdir(parents=True, exist_ok=True)
    blind_path = root / "blind.json"
    blind: dict[str, Any] = json.loads(blind_path.read_text(encoding="utf-8")) if blind_path.exists() else {}
    grades_path = root / "grades.json"
    grades: dict[str, Any] = (
        json.loads(grades_path.read_text(encoding="utf-8")) if grades_path.exists() else {}
    )
    for (engine, case), bid in assigned.items():
        blind[bid] = {"engine": engine, "model": None, "case": case}
        grades.setdefault(bid, {**dict.fromkeys(GRADE_KEYS), "note": ""})
    blind_path.write_text(json.dumps(blind, indent=2), encoding="utf-8")
    grades_path.write_text(json.dumps(grades, indent=2), encoding="utf-8")
    return assigned


def run_lane(
    lane: Lane, cases: list[int], ids: dict[tuple[str, int], str], root: Path, results: list[Any]
) -> None:
    name = lane.engine

    def log(line: str) -> None:
        say(name, line)

    vite = None
    try:
        vite = start_vite(lane.vite_port, root / f"_vite-{name}.log")
        log(f"app on {lane.vite_port}, daemons on {lane.daemon_port}")
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome")
            try:
                for cid in cases:
                    bid = ids[(lane.engine, cid)]
                    out = root / f"{cid:02d}-{bid}"
                    try:
                        rec = CaseRun(lane, CASES[cid], bid, out, browser, log).run()
                        results.append(rec)
                        log(
                            f"case {cid} ({bid}): end {rec['end']['step']} ok={rec['end']['ok']} "
                            f"blocker={rec['blocker']} wall {rec['wall_s']:.0f} s"
                        )
                    except Exception as e:  # a broken run (a leak, a schema break) is loud, the lane goes on
                        log(f"case {cid} ({bid}) BROKE: {type(e).__name__}: {e}")
                        results.append({"case": cid, "blind_id": bid, "broken": f"{type(e).__name__}: {e}"})
            finally:
                browser.close()
    except Exception as e:
        log(f"lane FAILED: {type(e).__name__}: {e}")
        results.append({"lane": name, "broken": str(e)})
    finally:
        kill_tree(vite)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engines", required=True, help="comma-separated: claude_code,muse_code or scripted")
    ap.add_argument("--cases", default="1-10", help="'1-10', '1,3,7'")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--model", action="append", default=[], help="engine=model, e.g. muse_code=muse-spark-1.3"
    )
    ap.add_argument("--view", default="drawing", choices=("drawing", "orbit"))
    ap.add_argument(
        "--persona", default="on", choices=("on", "off"), help="off: first suggestion, yes to all"
    )
    ap.add_argument(
        "--no-build", action="store_true", help="serve the app already built in apps/desktop/dist"
    )
    lanes_parallel = ap.add_mutually_exclusive_group()
    lanes_parallel.add_argument("--lanes-parallel", dest="parallel", action="store_true", default=True)
    lanes_parallel.add_argument("--lanes-serial", dest="parallel", action="store_false")
    args = ap.parse_args()

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    if len(engines) > len(LANE_PORTS):
        raise SystemExit(f"at most {len(LANE_PORTS)} engines (one lane each)")
    models: dict[str, str] = {}
    for m in args.model:
        engine, _, model = m.partition("=")
        if not model or engine not in engines:
            raise SystemExit(f"--model {m!r}: expected <engine>=<model> for one of {engines}")
        models[engine] = model
    cases = parse_cases(args.cases)
    root = args.out if args.out.is_absolute() else REPO / args.out

    lanes = []
    for i, engine in enumerate(engines):
        daemon_port, vite_port = SCRIPTED_PORTS if engine == "scripted" else LANE_PORTS[i]
        for port in (daemon_port, vite_port):
            if not port_free(port):
                raise SystemExit(f"port {port} (lane {engine}) is taken; free it first")
        lanes.append(
            Lane(engine, models.get(engine), daemon_port, vite_port, args.view, args.persona == "on")
        )

    if not args.no_build:
        print("building the app once (pnpm -C apps/desktop build) ...", flush=True)
        pnpm = shutil.which("pnpm") or "pnpm"
        done = subprocess.run([pnpm, "-C", "apps/desktop", "build"], cwd=REPO, capture_output=True, text=True)
        if done.returncode:
            raise SystemExit(f"the app did not build:\n{done.stdout[-2000:]}{done.stderr[-2000:]}")

    ids = plan(engines, cases, root)
    started = time.time()
    results: list[Any] = []
    threads = [threading.Thread(target=run_lane, args=(lane, cases, ids, root, results)) for lane in lanes]
    for t in threads:
        t.start()
        if not args.parallel:
            t.join()
    for t in threads:
        t.join()

    # the model each lane actually ran, read back from its runs, joins the key
    blind = json.loads((root / "blind.json").read_text(encoding="utf-8"))
    for rec in results:
        if "engine" in rec and rec.get("blind_id") in blind:
            blind[rec["blind_id"]]["model"] = rec.get("model")
    (root / "blind.json").write_text(json.dumps(blind, indent=2), encoding="utf-8")
    broken = [r for r in results if "broken" in r]
    print(
        f"\n{len(results) - len(broken)} run(s) recorded, {len(broken)} broken, {time.time() - started:.0f} s"
    )
    for r in broken:
        print(f"  BROKEN {r}")
    print(f"grade {root / 'grades.json'} blind, then: python scripts/parity/report.py {args.out}")
    if broken:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
