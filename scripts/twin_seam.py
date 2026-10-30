"""The twins page's live seam (WP5b): the BUILT desktop page against a real daemon on the scripted
engine, with Gmail and Notion faked inside the daemon's own process. Nothing reaches a network: the
vault's transport is the fake, and Google's sign-in "browser" plays the redirect on the loopback.

    uv run python scripts/twin_seam.py              # build, serve on 5192, drive, screenshot, check
    uv run python scripts/twin_seam.py --no-build   # reuse apps/desktop/dist

It starts a throwaway daemon (`--serve-fake`, a flag only this script passes: the fake services are
never on by default) with a scratch data folder, serves the built desktop with Vite on port 5192, and
drives the real page with Playwright through: the overview -> a new twin -> the whole setup (typed
words, her suggestions, a pencil inked, Google's sign-in on the fake, a Notion key on the fake, every
slip) -> the rehearsal with the held draft edited -> go live -> a mission on the fake thread -> the
held card signed with an edit -> the poller resolves it -> the overview's stats moved. At each step
it checks there is no page scroll and no console error; at the end, what the daemon received (the
fake's journal), that the engine asked for answered every call, and it ends both process trees.
Screenshots at 1280x800 go to docs/concepts/twin-module/shots/live/.

The page has no way to pick a Gmail conversation for a mission yet, so the mission is started on the
daemon's own route, as a future picker would; the page must show its held card without a reload.
Playwright for Python is found beside the system python when the project's environment has none.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs/concepts/twin-module/shots/live"
VITE_PORT = 5192  # the only port this seam serves the desktop on
APP = f"http://localhost:{VITE_PORT}"
TOKEN = "seam"
ENGINE = "scripted"
POLL_S = "3"  # the poller's interval in the throwaway daemon

NEED = (
    "I want a twin that writes to Suno creators whose tracks I'd like to feature on my channel, and keeps "
    "each conversation going until we agree."
)
SIGNS = "As Alex from Low Tide Visuals"
NOTION_KEY = "ntn_seam_fake_key_0123456789abcdef"  # the fake's key: no real Notion is asked
CLIENT = ("seam-client.apps.example", "seam-client-secret")  # the fake's Google client
EDIT_REHEARSAL = (
    "You'd get a free visualizer you can use anywhere, plus a credit and a link in the description. "
    "It isn't exclusive: the track and the visualizer stay yours.\n\ncheers, Alex"
)
EDIT_SIGNED = (
    "Thanks Lumen! Nothing more is asked of you: a credit and a link, and it stays yours. Shall I go ahead?"
)
YES = "Yes, go ahead! Credit me as Lumen Vale, please."
GOAL = "Get Lumen Vale's yes to feature 'Glass Harbor'"


# --- the throwaway daemon, with Gmail and Notion faked in its own process (--serve-fake only) ----------


def serve_fake(data: Path, port: int) -> None:
    """The daemon as `athena-daemon` runs it, except that its connected accounts are the twin tests'
    fakes behind the real vault, Google's sign-in plays its redirect on the loopback, and the page on
    port 5192 is an allowed origin. Every request the fakes answer is kept in `<data>/received.jsonl`."""
    sys.path.insert(0, str(REPO / "tests"))
    import uvicorn

    from athena.app import Daemon
    from athena.connectors.part import Connectors
    from athena.connectors.spec import load_builtin
    from athena.connectors.vault import Vault
    from athena.server import APP_ORIGINS, create_app, write_handshake
    from connectors_kit import callback, state_of
    from missions_kit import ASKED, FIRST, THREAD, MissionWorld, mine, theirs

    journal = data / "received.jsonl"
    lock = threading.Lock()

    class SeamWorld(MissionWorld):
        """The tests' Gmail (threads, sends) and Notion (pages, a practice page), plus Google's token
        endpoint; once the person's signed reply reaches the thread, the other side says yes."""

        def __init__(self, daemon: Daemon) -> None:
            super().__init__(daemon, None)
            self.threads[THREAD] = [mine("m1", FIRST), theirs("m2", ASKED)]
            self.answered = False

        def answer(self, method: str, address: str, headers: Mapping[str, str], body: bytes | None) -> Any:
            parts = urlsplit(address)
            entry: dict[str, Any] = {"method": method, "host": parts.hostname, "path": parts.path}
            if parts.hostname == "oauth2.googleapis.com" and parts.path == "/token":
                grant = {"access_token": "ya29.seam", "refresh_token": "1//seam", "expires_in": 3600}
                out: Any = (200, grant)
            elif parts.hostname == "oauth2.googleapis.com" and parts.path == "/revoke":
                out = (200, {})
            else:
                before = len(self.sent)
                out = super().answer(method, address, headers, body)
                if len(self.sent) > before:
                    entry["sent"] = self.sent[-1]
                    if self.sent[-1]["thread"] == THREAD and not self.answered:
                        self.answered = True
                        self.they_write(THREAD, YES)
                if parts.hostname == "api.notion.com" and body:
                    entry["notion"] = _notion_text(body)
            entry["status"] = out[0]
            with lock, journal.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            return out

    def _notion_text(body: bytes) -> str:
        try:
            return json.dumps(json.loads(body))[:400]
        except ValueError:
            return ""

    def play_sign_in(url: str) -> bool:
        """Google's page, faked: the person says yes a moment later, on the flow's own loopback."""

        def later() -> None:
            time.sleep(1.5)
            callback(url, state=state_of(url), code="seam-code")

        threading.Thread(target=later, daemon=True).start()
        return True

    daemon = Daemon.open(data)
    daemon.connectors.close()
    world = SeamWorld(daemon)
    daemon.connectors = Connectors(
        Vault(None, specs=load_builtin(), transport=world.provider, open_browser=play_sign_in)
    )
    token = os.environ.get("ATHENA_TOKEN", TOKEN)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    write_handshake(data, port, token)
    print(f"seam daemon (fake services) on 127.0.0.1:{port}", flush=True)
    app = create_app(daemon, token, origins=(*APP_ORIGINS, APP))
    uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False)).run(sockets=[sock])


# --- talking to the daemon ------------------------------------------------------------------------


def call(base: str, method: str, path: str, body: Any = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def wait_for(url: str, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.4)
    raise RuntimeError(f"nothing answered at {url}")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def end_tree(proc: subprocess.Popen[Any] | None) -> None:
    """Ends a process and everything it started (`uv`, `pnpm` and Vite start children)."""
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


# --- driving the page -------------------------------------------------------------------------------


def drive(base: str) -> dict[str, Any]:
    """Drives the built page through the whole path; answers what it saw."""
    from playwright.sync_api import Page, sync_playwright

    result: dict[str, Any] = {"steps": [], "problems": [], "errors": [], "shots": []}
    SHOTS.mkdir(parents=True, exist_ok=True)

    def note(line: str) -> None:
        result["steps"].append(line)
        print(f"{time.strftime('%H:%M:%S')} {line}", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_init_script("try{localStorage.setItem('athena.firstRun.skipped','1')}catch(e){}")
        pg: Page = ctx.new_page()
        pg.on("pageerror", lambda e: result["errors"].append(str(e)))
        pg.on("console", lambda m: result["errors"].append(m.text) if m.type == "error" else None)

        def no_scroll(where: str) -> None:
            h = pg.evaluate("[document.documentElement.scrollHeight, innerHeight]")
            if h[0] > h[1] + 1:
                result["problems"].append(f"the page scrolls at {where}: {h}")

        def shot(name: str) -> None:
            pg.wait_for_timeout(700)  # the stamps and the ink settle
            path = SHOTS / f"1280x800-{name}.png"
            pg.screenshot(path=str(path))
            result["shots"].append(path.relative_to(REPO).as_posix())
            no_scroll(name)

        def idle(timeout_s: float = 60) -> None:
            pg.wait_for_function(
                "() => { const f = document.querySelector('.tw-frame--setup');"
                " return !f || (f.dataset.work === '' && f.dataset.phase !== 'thinking'"
                " && f.dataset.phase !== 'sending'); }",
                timeout=timeout_s * 1000,
            )
            failed = pg.locator('.tw-frame--setup[data-phase="failed"]')
            if failed.count():
                raise RuntimeError("her reply failed: " + pg.inner_text('[data-role="note"]')[:300])
            no_scroll("a setup step")

        def say(text: str) -> None:
            pg.fill('[data-role="composer"] input', text)
            pg.click('[data-role="composer"] button[type="submit"]')
            pg.wait_for_timeout(300)
            idle()

        def pick(i: int) -> None:
            pg.locator('[data-role="note"] [data-role="suggestion"]').nth(i).click()
            pg.wait_for_timeout(300)
            idle()

        def slip(kind: str) -> None:
            pg.wait_for_selector(f'[data-role="slip"][data-kind="{kind}"]', timeout=20000)

        def go_slip(kind: str) -> None:
            slip(kind)
            pg.click(f'[data-role="slip"][data-kind="{kind}"] [data-role="slip-go"]')
            pg.wait_for_timeout(300)
            idle()

        def ink_all() -> None:
            pg.click(".ath__inkall")
            pg.wait_for_timeout(200)
            idle()

        def stats() -> list[str]:
            return [" ".join(t.split()) for t in pg.locator('[data-role="stat-tile"]').all_inner_texts()]

        try:
            q = f"?daemon={base}&token={TOKEN}"
            pg.goto(f"{APP}/{q}#twins")
            pg.wait_for_selector('.ov[data-mode="first"]', timeout=30000)
            before = stats()
            shot("overview-before")
            note(f"overview before: {before}")

            # --- a new twin, set up in conversation ---
            pg.click('button:has-text("Set up a first twin with Athena")')
            pg.wait_for_selector('.tw-frame--setup [data-role="composer"]', timeout=20000)
            if not pg.locator('.tw-frame--setup [data-role="simulated"]').count():
                result["problems"].append("the setup does not say it is simulated")
            say(NEED)  # typed words: what it is for
            note(f"described; at {pg.evaluate('location.hash')}")
            pg.locator('.doc [data-role="piece-pencil"] button').first.click()  # her name for it, inked
            pg.wait_for_timeout(300)
            idle()
            say(SIGNS)  # typed words: how it signs
            slip("gmail")
            pg.click('[data-role="slip"][data-kind="gmail"] summary')
            inputs = pg.locator('[data-role="slip"][data-kind="gmail"] .client__f input')
            inputs.nth(0).fill(CLIENT[0])
            inputs.nth(1).fill(CLIENT[1])
            pg.click('[data-role="slip"][data-kind="gmail"] .slip__f .btn-primary')
            pg.wait_for_selector('[data-kind="gmail"] .cstate[data-state="waiting"]', timeout=10000)
            note("Google's sign-in waits in the (fake) browser")
            idle(60)
            go_slip("samples")
            slip("style")
            shot("setup-f3")
            ink_all()  # the voice she heard, inked
            pick(1)  # "A little more formal at first contact"
            slip("notion")
            pg.fill("#notion-key", NOTION_KEY)
            pg.click('[data-role="slip"][data-kind="notion"] button[type="submit"]')
            pg.wait_for_timeout(300)
            idle()
            go_slip("pages")
            go_slip("chores")
            ink_all()  # the lines it must never cross
            pick(2)  # "Also: never write after 9 pm their time"
            slip("autonomy")
            pg.click('[data-role="slip"][data-kind="autonomy"] input[type="checkbox"]')
            pg.click('[data-kind="autonomy"] [aria-label="Replies"] button:has-text("Auto")')
            go_slip("autonomy")
            go_slip("memory")
            pick(0)  # the first mission she suggests
            twin_id = pg.evaluate("location.hash").split("/")[1]
            result["twin"] = twin_id
            detail = call(base, "GET", f"/twins/{twin_id}")
            note(f"set up: readiness {detail['readiness']}, {len(detail['pieces'])} pieces")
            if not detail["ready"]:
                raise RuntimeError("the setup did not end ready")

            # --- the dress rehearsal: one stream, then the drafts that waited ---
            pg.click('[data-role="exit"]:not([disabled])')  # That's enough, rehearse it
            pg.wait_for_selector(".turn.is-current .turn__act", timeout=60000)
            idle()
            pg.click('.turn.is-current .turn__act button:has-text("That\'s me")')
            pg.wait_for_selector('.turn.is-current[data-turn="t3"] .turn__act', timeout=20000)
            idle()
            shot("rehearsal-held")
            pg.click('.turn.is-current .turn__act button:has-text("Edit it")')
            pg.fill("#edit-box", EDIT_REHEARSAL)
            pg.click('.turn.is-current .turn__act button:has-text("Save my version")')
            pg.wait_for_timeout(300)
            idle()
            pg.click('.turn.is-current .turn__act button:has-text("Send it")')
            pg.wait_for_selector('.outcome[data-state="resolved"]', timeout=20000)
            note("rehearsed: resolved, the held reply in the person's words")
            pg.click('.outcome button:has-text("Go live")')
            pg.wait_for_timeout(300)
            idle()
            if call(base, "GET", f"/twins/{twin_id}")["state"] != "live":
                raise RuntimeError("it did not go live")
            note("live")
            pg.click('[data-role="exit"]')  # back to the twins
            pg.wait_for_selector('.ov[data-mode="today"]', timeout=20000)

            # --- a mission on the fake thread; its held card shows without a reload ---
            mission = call(base, "POST", f"/twins/{twin_id}/missions", {"thread": "th0123abcd", "goal": GOAL})
            held = mission["turns"][-1]
            note(f"mission {mission['id']}: {mission['state']}, its draft waits: {held.get('reason')}")
            card = pg.locator('[data-role="waiting-card"]', has_text="Feature on Friday")
            card.first.wait_for(timeout=20000)
            card.first.click()
            pg.wait_for_selector('[data-role="draft-page"]', timeout=20000)
            shot("draft")
            pg.click('[data-role="draft-page"] button:has-text("Edit")')
            pg.fill("#draft-edit", EDIT_SIGNED)
            pg.click('[data-role="draft-page"] button:has-text("Sign and send yours")')
            pg.wait_for_selector('.ov[data-mode="today"]', timeout=20000)
            note("signed with an edit")

            # the other side says yes; the poller works the mission, and the page follows the daemon's events
            end = time.time() + 40
            while time.time() < end:
                m = call(base, "GET", f"/twins/{twin_id}/missions/{mission['id']}")
                if m["state"] == "resolved":
                    break
                time.sleep(1)
            result["mission"] = {"state": m["state"], "note": m.get("note", ""), "beats": m["beats"]}
            pg.wait_for_timeout(2500)
            after = stats()
            shot("overview-after")
            note(f"overview after: {after}")
            result["stats"] = {"before": before, "after": after}
            if after == before:
                result["problems"].append("the overview's stats did not move")

            # --- the mission's script, and how it sounds now ---
            pg.evaluate(f"location.hash = '#twin/{twin_id}/mission/{mission['id']}'")
            pg.wait_for_selector('[data-role="mission-page"]', timeout=20000)
            shot("mission")
            pg.evaluate(f"location.hash = '#twin/{twin_id}/voice'")
            pg.wait_for_selector('[data-role="preview-text"]', timeout=30000)
            shot("voice")
            result["preview"] = pg.inner_text('[data-role="preview-text"]')
        except Exception as e:  # where it stopped, with what the page said there
            result["problems"].append(f"{type(e).__name__}: {e}"[:400])
            result["page"] = " ".join(pg.inner_text("body").split())[:1500]
            pg.screenshot(path=str(Path(tempfile.gettempdir()) / "twin-seam-stopped.png"))
            result["stopped_shot"] = "twin-seam-stopped.png in the temp folder"
        browser.close()
    return result


def drive_elsewhere(base: str, out: Path) -> dict[str, Any]:
    """Playwright lives beside the system python here: drive from there (outside this project's
    environment, which its launchers would otherwise pick), and read what it saw."""
    venv = os.environ.get("VIRTUAL_ENV", "")
    path = os.pathsep.join(
        d for d in os.environ.get("PATH", "").split(os.pathsep) if not (venv and d.startswith(venv))
    )
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH")}
    env["PATH"] = path
    for name in ("python", "python3", "py"):
        exe = shutil.which(name, path=path)
        if not exe:
            continue
        probe = subprocess.run([exe, "-c", "import playwright.sync_api"], capture_output=True, env=env)
        if probe.returncode == 0:
            drive_it = [exe, str(Path(__file__)), "--drive", base, "--out", str(out)]
            subprocess.run(drive_it, env=env, check=False)
            if not out.is_file():
                raise RuntimeError("the drive wrote no result")
            return json.loads(out.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    raise RuntimeError("Playwright for Python is not installed here: pip install playwright")


# --- the run --------------------------------------------------------------------------------------------


def check_received(data: Path, result: dict[str, Any]) -> None:
    """What the fakes received: one Google sign-in, the Notion key checked, the practice page written,
    the person's own words sent in-thread, then the thanks sent alone and the outcome filed."""
    lines = [json.loads(x) for x in (data / "received.jsonl").read_text(encoding="utf-8").splitlines()]
    sent = [x["sent"] for x in lines if "sent" in x]
    token = [x for x in lines if x["path"] == "/token"]
    notion = [x for x in lines if x["host"] == "api.notion.com"]
    got = {
        "google_sign_ins": len(token),
        "notion_key_checks": sum(x["path"] == "/v1/users/me" for x in notion),
        "practice_pages": sum(x["method"] == "POST" and x["path"] == "/v1/pages" for x in notion),
        "notion_writes": sum(x["method"] == "PATCH" for x in notion),
        "gmail_sends": [{"to": s["to"], "thread": s["thread"], "text": s["text"][:80]} for s in sent],
        # the mission's outcome note names who it was with; the rehearsal's last line does not
        "outcome_filed": any("Outcome: " in x.get("notion", "") and "With " in x["notion"] for x in notion),
        "hosts": sorted({str(x["host"]) for x in lines}),
    }
    result["received"] = got
    want = [
        (got["google_sign_ins"] == 1, "one Google sign-in"),
        (got["notion_key_checks"] >= 1, "the Notion key checked"),
        (got["practice_pages"] >= 1, "a practice page made"),
        (len(sent) == 2, "two Gmail sends"),
        (bool(sent) and sent[0]["text"] == EDIT_SIGNED, "the person's own words sent"),
        (bool(sent) and sent[0]["thread"] == "th0123abcd" and bool(sent[0]["in_reply_to"]), "sent in-thread"),
        (len(sent) == 2 and sent[1]["text"].startswith("(Simulated) Brilliant"), "the thanks sent alone"),
        (got["outcome_filed"], "the outcome filed to Notion"),
    ]
    for ok, what in want:
        if not ok:
            result["problems"].append(f"the daemon did not receive: {what}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="twin_seam")
    parser.add_argument("--serve-fake", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--data", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--drive", metavar="DAEMON", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--no-build", action="store_true", help="reuse apps/desktop/dist")
    args = parser.parse_args(argv)
    if args.serve_fake:
        serve_fake(args.data, args.port)
        return 0
    if args.drive:
        args.out.write_text(json.dumps(drive(args.drive)), encoding="utf-8")
        return 0

    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("pnpm is needed to build and serve the desktop")
    scratch = Path(tempfile.mkdtemp(prefix="twin-seam-"))
    data = scratch / "data"
    data.mkdir()
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    result: dict[str, Any] = {"engine": ENGINE, "problems": []}
    vite: subprocess.Popen[Any] | None = None
    daemon: subprocess.Popen[Any] | None = None
    try:
        if not args.no_build:
            print("building the desktop", flush=True)
            subprocess.run([pnpm, "-C", "apps/desktop", "build"], cwd=REPO, check=True, capture_output=True)
        vite = subprocess.Popen(
            [pnpm, "-C", "apps/desktop", "exec", "vite", "preview", "--port", str(VITE_PORT), "--strictPort"],
            cwd=REPO,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        env = {**os.environ, "ATHENA_ENGINE": ENGINE, "ATHENA_TOKEN": TOKEN, "ATHENA_TWIN_POLL": POLL_S}
        daemon = subprocess.Popen(
            [sys.executable, str(Path(__file__)), "--serve-fake", "--data", str(data), "--port", str(port)],
            cwd=REPO,
            env=env,
        )
        wait_for(f"{base}/health", 60)
        wait_for(APP, 60)
        status = call(base, "GET", "/engine")
        print(f"daemon on {port}, engine {status['engine']}; the page on {VITE_PORT}", flush=True)
        if status["engine"] != ENGINE or not status["simulated"]:
            raise RuntimeError(f"the daemon runs {status['engine']}, not {ENGINE}")
        try:
            import playwright.sync_api  # noqa: F401

            seen = drive(base)
        except ImportError:
            seen = drive_elsewhere(base, scratch / "drive.json")
        result.update({k: v for k, v in seen.items() if k != "problems"})
        result["problems"] += seen.get("problems", [])
        if seen.get("errors"):
            result["problems"].append(f"console errors: {seen['errors'][:5]}")
        check_received(data, result)
        rows = call(base, "GET", "/ledger?limit=500")["rows"]
        engines = sorted({r["engine"] for r in rows})
        surfaces = sorted({r["surface"] for r in rows})
        result["ledger"] = {"calls": len(rows), "engines": engines, "surfaces": surfaces}
        if engines != [ENGINE]:
            result["problems"].append(f"an engine other than {ENGINE} answered: {engines}")
    except Exception as e:  # the record says where it stopped and why
        result["problems"].append(f"{type(e).__name__}: {e}"[:600])
    finally:
        end_tree(daemon)
        end_tree(vite)
        for p in (port, VITE_PORT):
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", p)) == 0:
                    result["problems"].append(f"something still listens on {p} after the run")
        shutil.rmtree(scratch, ignore_errors=True)
    print(json.dumps(result, indent=1))
    ok = not result["problems"]
    print("SEAM PASSED" if ok else "SEAM FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
