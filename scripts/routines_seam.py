"""The routines seam (business Phase 2): the BUILT desktop shell (her browser on WebView2) and a real
engine, against the local simulated pages (`athena.browser.fixture`): creator videos, a Proton-like
inbox and Studio analytics. Nothing reaches a real account; the pages are labelled simulated.

    uv run python scripts/routines_seam.py --engine claude_code --out runs/routines-seam.json

What it walks, through the running daemon's routes (Run now, the way the front page calls it):
1. watch reads both creators' pages and keeps their uploads as tracks;
2. a new upload appears; watch is asked to run while a chat turn is open in the project -> skipped
   `live_turn`; once the turn ends it runs and keeps exactly the new track;
3. inbox reads the mailbox: one reply card per creator whose last message is theirs, the stranger is
   not kept; a second run files nothing new; a new reply files exactly one more card;
4. stats keeps the analytics page's figures as stat readings, measured now;
5. one reply card is signed: the recipe answers in the real page, and the mailbox's journal shows one
   message sent.

The shell runs under its own identity (`ai.athena.meta.routines-seam`) with the host's ticking off
(ATHENA_TWIN_POLL=0), so only Run now starts a routine. Ports: fixture 8783, Vite 1434.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from athena.browser import fixture  # noqa: E402

IDENTIFIER = "ai.athena.meta.routines-seam"
FIXTURE_PORT = 8783
VITE_PORT = 1434


def app_data(identifier: str) -> Path:
    return Path(os.environ["APPDATA"]) / identifier


def kill(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is not None and proc.poll() is None:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)


def seed(data: Path, site: str) -> str:
    """The project, through the daemon's own code beside the live daemon (SQLite, WAL): the business
    kinds, the fixture's two creators (followed, with their addresses), the fixture as the project's
    site (the mailbox), and a live twin on business mail. Answers the space id."""
    from athena.app import Daemon
    from twins_web_kit import web_twin

    daemon = Daemon.open(data)
    try:
        space = daemon.spaces.create({"name": "Music channel (simulated seam)"})["id"]
        daemon.records.set_kinds(space, {"kinds": ["creator", "track", "thread", "agreement", "stat"]})
        for handle, name, email in fixture.CREATORS:
            daemon.records.put(
                space,
                "creator",
                {
                    "name": name,
                    "channel_url": f"{site}/channel/{handle}",
                    "followed": True,
                    "emails": [email],
                },
                "person",
            )
        daemon.sites.add(space, site, "Proton Mail (simulated)", f"{site}/mail", "Business mail and pages")
        daemon.sites.looked(space, site, "signed_in", "set up by the seam")
        web_twin(daemon, ("mail_web",), state="live", space_id=space)
        return space
    finally:
        daemon.store.close()


class Seam:
    def __init__(self, url: str, token: str, site: str) -> None:
        self.url, self.token, self.site = url, token, site

    def http(self, method: str, path: str, body: Any = None, timeout: float = 300) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                code, out = (
                    r.status,
                    (json.loads(raw) if raw and r.headers.get_content_type() == "application/json" else raw),
                )
        except urllib.error.HTTPError as e:
            raw = e.read()
            code, out = e.code, (json.loads(raw) if raw else None)
        print(f"  {method} {path} -> {code} ({int((time.monotonic() - started) * 1000)} ms)", flush=True)
        return code, out

    def fixture(self, method: str, path: str) -> Any:
        req = urllib.request.Request(self.site + path, method=method, data=b"" if method == "POST" else None)
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return json.loads(raw) if path == "/state" else raw

    def routines(self, space: str) -> dict[str, dict[str, Any]]:
        return {r["kind"]: r for r in self.http("GET", f"/spaces/{space}/routines")[1]["routines"]}

    def run(self, routine_id: str) -> dict[str, Any]:
        out: dict[str, Any] = self.http("POST", f"/routines/{routine_id}/run")[1]
        print(
            f"    -> {out.get('outcome')} {out.get('reason', '')} found {out.get('found')} kept {out.get('kept')} "
            f"cards {out.get('cards')} {out.get('note', '')}",
            flush=True,
        )
        return out

    def records(self, space: str, kind: str) -> list[dict[str, Any]]:
        return list(self.http("GET", f"/spaces/{space}/records?kind={kind}")[1]["records"])

    def waiting_web_cards(self) -> list[dict[str, Any]]:
        cards = self.http("GET", "/cards?state=waiting")[1]["cards"]
        return [c for c in cards if c["action"] == "twin_send_web"]


def check(results: dict[str, Any], name: str, ok: bool, detail: Any = None) -> None:
    results[name] = {"ok": bool(ok), "detail": detail}
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail is not None else ""), flush=True)


def walk(seam: Seam, space: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    routines = seam.routines(space)
    check(results, "default_routines", {"watch", "inbox", "stats"} <= set(routines), sorted(routines))
    seam.http("PATCH", f"/routines/{routines['inbox']['id']}", {"url": f"{seam.site}/mail"})
    seam.http("PATCH", f"/routines/{routines['stats']['id']}", {"url": f"{seam.site}/studio/analytics"})

    # 1. watch keeps both creators' uploads.
    started = time.monotonic()
    first = seam.run(routines["watch"]["id"])
    tracks = seam.records(space, "track")
    expected = sum(len(v) for v in fixture.UPLOADS.values())
    check(
        results,
        "watch_keeps_every_upload",
        first["outcome"] == "ran" and len(tracks) == expected and first.get("of") == len(fixture.CREATORS),
        {
            "run": first,
            "tracks": len(tracks),
            "expected": expected,
            "s": round(time.monotonic() - started, 1),
        },
    )

    # 2. a new upload during a live chat turn: skipped, then kept once the turn ends.
    seam.fixture("POST", "/fixture/new-upload")
    turn_done = threading.Event()

    def chat() -> None:
        seam.http(
            "POST", "/run", {"text": "In two short sentences, what does this project do?", "space_id": space}
        )
        turn_done.set()

    threading.Thread(target=chat, daemon=True).start()
    time.sleep(1.5)
    during = seam.run(routines["watch"]["id"])
    turn_done.wait(300)
    after = seam.run(routines["watch"]["id"])
    titles = [t["body"]["title"] for t in seam.records(space, "track")]
    check(
        results,
        "watch_waits_for_a_live_turn_then_keeps_the_new_upload",
        during["outcome"] == "skipped"
        and during.get("reason") == "live_turn"
        and after["outcome"] == "ran"
        and after["kept"] == 1
        and titles.count(fixture.NEW_UPLOAD[1]) == 1,
        {"during": during, "after": after},
    )

    # 3. inbox: one reply card per creator whose last message is theirs; the stranger is not kept.
    inbox = seam.run(routines["inbox"]["id"])
    threads = seam.records(space, "thread")
    cards = seam.waiting_web_cards()
    check(
        results,
        "inbox_keeps_creator_threads_and_drafts_one_reply_each",
        inbox["outcome"] == "ran" and len(threads) == 2 and len(cards) == 2,
        {"run": inbox, "threads": len(threads), "cards": [c["label"] for c in cards]},
    )
    again = seam.run(routines["inbox"]["id"])
    check(
        results,
        "a_second_inbox_run_files_nothing_new",
        len(seam.waiting_web_cards()) == 2,
        {"run": again},
    )
    seam.fixture("POST", "/fixture/new-reply?thread=m1")
    later = seam.run(routines["inbox"]["id"])
    check(
        results,
        "a_new_reply_files_exactly_one_more_card",
        len(seam.waiting_web_cards()) == 3,
        {"run": later},
    )

    # 4. stats.
    stats = seam.run(routines["stats"]["id"])
    readings = seam.records(space, "stat")
    check(
        results,
        "stats_keeps_the_figures_measured_now",
        stats["outcome"] == "ran"
        and len(readings) >= 3
        and all(not r["body"]["measured_at"].startswith(fixture.ANALYTICS_CLAIMED) for r in readings),
        {"run": stats, "metrics": sorted({r["body"]["metric"] for r in readings})},
    )

    # 5. sign one reply: the recipe answers in the real page.
    before = len(seam.fixture("GET", "/state").get("sent", []))
    card = seam.waiting_web_cards()[0]
    code, signed = seam.http("POST", f"/decisions/{card['id']}", {"verdict": "approve"})
    after_sent = seam.fixture("GET", "/state").get("sent", [])
    check(
        results,
        "a_signed_reply_is_sent_once_through_her_browser",
        code == 200 and len(after_sent) == before + 1,
        {
            "status": code,
            "outcome": (signed or {}).get("outcome") or (signed or {}).get("reason"),
            "sent": after_sent[-1:],
        },
    )
    _, ledger = seam.http("GET", f"/ledger?space={space}&limit=200")
    results["cost"] = {
        "routine_usd_est": round(
            sum(r.get("cost_usd") or 0 for r in ledger["rows"] if r["surface"] == "routine"), 4
        ),
        "twin_usd_est": round(
            sum(r.get("cost_usd") or 0 for r in ledger["rows"] if r["surface"] == "twin"), 4
        ),
        "calls": len(ledger["rows"]),
    }
    print("cost", results["cost"], flush=True)
    return results


def launch(engine: str, shell_log: Path | None) -> tuple[subprocess.Popen[bytes], subprocess.Popen[bytes]]:
    desktop = ROOT / "apps" / "desktop"
    pnpm = "pnpm.cmd" if os.name == "nt" else "pnpm"
    vite = subprocess.Popen(
        [pnpm, "exec", "vite", "--port", str(VITE_PORT), "--strictPort"],
        cwd=desktop,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    config = Path(tempfile.mkdtemp()) / "seam.json"
    config.write_text(
        json.dumps(
            {
                "identifier": IDENTIFIER,
                "build": {"devUrl": f"http://localhost:{VITE_PORT}", "beforeDevCommand": ""},
            }
        )
    )
    env = dict(os.environ, ATHENA_ENGINE=engine, ATHENA_TWIN_POLL="0")
    env.pop("ATHENA_DAEMON_PORT", None)
    log = open(shell_log, "wb") if shell_log else subprocess.DEVNULL  # noqa: SIM115
    shell = subprocess.Popen(
        [pnpm, "tauri", "dev", "--config", str(config)],
        cwd=desktop,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return vite, shell


def connect(data: Path, site: str) -> Seam:
    deadline = time.monotonic() + 600
    while not (data / "daemon.json").exists():
        if time.monotonic() > deadline:
            raise RuntimeError("the shell did not start its daemon within 10 minutes")
        time.sleep(1)
    hand = json.loads((data / "daemon.json").read_text())
    seam = Seam(f"http://127.0.0.1:{hand['port']}", hand["token"], site)
    for _ in range(240):
        try:
            seam.http("GET", "/engine")
            break
        except OSError:
            time.sleep(0.5)
    time.sleep(3)  # her browser's relay polls once the daemon answers
    return seam


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="routines_seam")
    parser.add_argument("--engine", default="claude_code")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--shell-log", type=Path)
    args = parser.parse_args(argv)
    server, _ = fixture.serve(FIXTURE_PORT)
    site = f"http://127.0.0.1:{FIXTURE_PORT}"
    data = app_data(IDENTIFIER)
    vite = shell = None
    try:
        shutil.rmtree(data, ignore_errors=True)  # a clean data folder: this identity is the seam's own
        vite, shell = launch(args.engine, args.shell_log)
        seam = connect(data, site)
        space = seed(data, site)
        results = walk(seam, space)
        failed = [k for k, v in results.items() if isinstance(v, dict) and v.get("ok") is False]
        results["engine"] = args.engine
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"{len(failed)} failed: {failed}", flush=True)
        return 1 if failed else 0
    finally:
        server.shutdown()
        kill(shell)
        kill(vite)


if __name__ == "__main__":
    sys.exit(main())
