"""Business Phase 1's live seam: a real daemon over the simulated music channel, one composition on
a real engine, a verdict, and the numbers checked against the records. Nothing reaches a real account.

    uv run python scripts/report_seam.py claude_code runs/report-seam      # about $0.05, est.

It seeds a fresh data folder with scripts/business_fixture.py, starts the daemon on SEAM_PORT (8771),
calls the routes the front page calls, ends the daemon's whole process tree, and prints one JSON report.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("SEAM_PORT", "8771"))
TOKEN = "seam"


def call(method: str, path: str, body: Any = None, timeout: float = 30) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    engine, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    data = out / "data"
    seeded = subprocess.run(
        ["uv", "run", "python", "scripts/business_fixture.py", str(data)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    space = json.loads(seeded.stdout.strip().splitlines()[-1])["space_id"]
    env = {**os.environ, "ATHENA_TOKEN": TOKEN, "ATHENA_ENGINE": engine}
    daemon = subprocess.Popen(
        ["uv", "run", "athena-daemon", "--data", str(data), "--port", str(PORT), "--no-peer"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    report: dict[str, Any] = {"engine": engine, "space_id": space, "checks": {}}
    checks = report["checks"]
    try:
        for _ in range(60):
            try:
                if call("GET", "/health")[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(0.5)
        status, first = call("GET", f"/spaces/{space}/report")
        checks["default view"] = status == 200 and first["default"] is True
        queue = first["values"]["d-queue"]["items"]
        tracks = call("GET", f"/spaces/{space}/records?kind=track")[1]["records"]
        waiting = [t for t in tracks if "verdict" not in t["body"]]
        checks["queue = tracks with no verdict"] = len(queue) == len(waiting)

        t0 = time.time()
        status, composed = call("POST", f"/spaces/{space}/report/compose", timeout=180)
        report["compose_s"] = round(time.time() - t0, 1)
        report["compose_status"] = status
        if status == 200:
            report["composed"] = {
                "title": composed["spec"]["title"],
                "callout": composed["spec"].get("callout"),
                "blocks": [(b["id"], b["kind"], b["span"]) for b in composed["spec"]["blocks"]],
                "dropped": composed["dropped"],
                "reasons": composed["reasons"],
            }
            checks["composed, not default"] = composed["default"] is False
            texts = [composed["spec"]["title"], composed["spec"].get("callout", "")]
            texts += [b["title"] for b in composed["spec"]["blocks"]]
            checks["no digit in her words"] = not any(any(c.isdigit() for c in t) for t in texts)
        else:
            report["compose_error"] = composed

        target = waiting[0]
        status, judged = call(
            "POST", f"/records/{target['id']}/verdict", {"verdict": "keep", "genre": "lo-fi"}
        )
        checks["verdict appends a revision"] = status == 200 and judged["rev"] == target["rev"] + 1
        history = call("GET", f"/records/{judged['id']}/history")[1]["records"]
        checks["history keeps both"] = [r["rev"] for r in history] == [target["rev"], judged["rev"]]
        after = call("GET", f"/spaces/{space}/report")[1]
        key = next((b["id"] for b in after["spec"]["blocks"] if b["kind"] == "queue"), None)
        checks["queue shrinks by one"] = (
            key is not None and len(after["values"][key]["items"]) == len(waiting) - 1
        )
        ledger = call("GET", f"/ledger?space={space}")[1]
        rows = [r for r in ledger["rows"] if r["surface"] == "report"]
        report["ledger_report_rows"] = len(rows)
        report["cost_usd_est"] = round(sum(r.get("cost_usd") or 0 for r in rows), 4)
    finally:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(daemon.pid)], capture_output=True)
        else:
            daemon.terminate()
    report["passed"] = sum(1 for v in checks.values() if v)
    report["of"] = len(checks)
    (out / "seam.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["of"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
