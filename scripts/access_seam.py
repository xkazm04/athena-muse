"""The access seam (ADR 0014): a chore's onboarding signs the person in to its real site in her real
browser (the built Tauri shell on WebView2), the overview stays clean, the site's sign-in lapses, the
overview shows the blocker, and "Sign in again" clears it. Everything runs against the local simulated
test pages (`athena.browser.fixture`, its members' page behind a sign-in); nothing reaches a real
account and no model is called.

    uv run python scripts/access_seam.py                  # fixture + vite 1433 + the shell, walk, report
    uv run python scripts/access_seam.py --out runs/access-seam.json

The draft is brought to its verdict by the daemon's own code with a stand-in engine (the tests'
`drafts_kit.Fake`: simulated, it writes the staged chore), its school-portal node carrying the fixture's
members' page as a confirmed site; then `keep` opens the access step. From there every step goes
through the running daemon's routes, the way the stage and the overview call them. The person's own
act (pressing Sign in on the site's page) is simulated by a signed `page_click` through the MCP
server, as browser_seam.py does for the wheel.

The shell runs as a separate app identity (`ai.athena.meta.seam`), so it never shares a data folder,
a browser profile or a port with the person's own Athena. Ports: fixture 8781, daemon 8782, Vite 1433.
It ends both process trees and prints one JSON report.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from athena.browser import fixture  # noqa: E402

IDENTIFIER = "ai.athena.meta.seam"
FIXTURE_PORT = 8781
DAEMON_PORT = 8782
VITE_PORT = 1433


def onboard(data: Path, origin: str, probe_url: str) -> tuple[str, str]:
    """(draft id, project id): the staged need taken to its verdict and kept by the daemon's own code
    on a stand-in engine (simulated), its school-portal node carrying `probe_url` as a confirmed real
    site. Runs beside the live daemon on the same data folder (SQLite, WAL)."""
    from athena.app import Daemon
    from athena.contracts import Draft, KeyBody
    from athena.drafts import author, key, preview, rehearse, save
    from drafts_kit import Fake, agreed_draft

    daemon = Daemon.open(data)
    try:
        engine = Fake()
        draft = agreed_draft(daemon)
        for node in draft["sketch"]["nodes"]:
            if node["id"] == "n2":
                node["site"] = {"origin": origin, "url": probe_url, "label": node["label"], "confirmed": True}
        draft = daemon.drafts.put(cast("Draft", draft))
        for _ in author.write(daemon, engine, draft["id"]):
            pass
        cards = preview.preview(daemon, engine, draft["id"])
        body: KeyBody = {
            "marks": [{"expected_id": c["id"], "mark": "yes"} for c in cards],
            "missing": [],
            "never": [],
        }
        key.put_key(daemon, engine, draft["id"], body)
        for _ in rehearse.rehearse(daemon, engine, draft["id"]):
            pass
        kept = save.verdict(daemon, draft["id"], "keep", None)
        return kept["id"], kept["space_id"]
    finally:
        daemon.store.close()


class Seam:
    def __init__(self, url: str, token: str, fixture_url: str) -> None:
        self.url = url
        self.token = token
        self.fixture = fixture_url
        self.lease = ""
        self.mcp_url = ""
        self.events: list[dict[str, Any]] = []
        self.log: list[dict[str, Any]] = []
        self._id = 0

    def http(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read()
                code, out = r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            code, out = e.code, (json.loads(raw) if raw else None)
        ms = int((time.monotonic() - started) * 1000)
        self.log.append({"call": f"{method} {path}", "body": body, "status": code, "ms": ms})
        print(f"  {method} {path} {body or ''} -> {code} ({ms} ms)", flush=True)
        return code, out

    def mcp(self, name: str, **args: Any) -> tuple[str, str | None]:
        self._id += 1
        msg = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
        req = urllib.request.Request(self.mcp_url, data=json.dumps(msg).encode(), method="POST")
        req.add_header("Authorization", f"Bearer {self.lease}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=300) as r:
            result = json.loads(r.read())["result"]
        text = result["content"][0]["text"]
        pending = (result.get("structuredContent") or {}).get("pending", {}).get("card_id")
        print(f"  mcp {name} {args} -> {'card ' + pending if pending else text[:120]!r}", flush=True)
        return text, pending

    def listen(self, stop: threading.Event) -> None:
        req = urllib.request.Request(f"{self.url}/events?token={self.token}")
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                for raw in r:
                    if stop.is_set():
                        return
                    line = raw.decode().strip()
                    if line.startswith("data:"):
                        event = json.loads(line[5:])
                        if event.get("type") in ("wheel", "site"):
                            self.events.append(event)
        except Exception:
            return

    def state(self) -> dict[str, Any]:
        """The fixture's journal (sign-ins, lapses)."""
        with urllib.request.urlopen(self.fixture + "/state", timeout=10) as r:
            out: dict[str, Any] = json.loads(r.read())
            return out

    def wheel(self, tab: int, since: int, wait_s: float = 30.0) -> dict[str, Any] | None:
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            for e in self.events[since:]:
                if e["type"] == "wheel" and e["wheel"]["tab"] == tab:
                    return e
            time.sleep(0.2)
        return None

    def press_sign_in(self, tab: int) -> str:
        """The person presses Sign in on the site's own page (simulated: a signed click)."""
        found, card = self.mcp("page_find", tab=tab, query="Sign in", role="button")
        if card:  # a site not yet trusted: the read waits for a signature too
            self.http("POST", f"/decisions/{card}", {"verdict": "approve"})
            _, signed = self.http("GET", "/cards")
            found = next((c.get("outcome", "") for c in signed["cards"] if c["id"] == card), "")
        ref = next(line.split()[0] for line in found.splitlines() if "ref_" in line and "Sign in" in line)
        ref = ref[ref.index("ref_") :]
        _, click = self.mcp("page_click", tab=tab, ref=ref, expect="Sign in")
        assert click, "a click is always a card"
        code, out = self.http("POST", f"/decisions/{click}", {"verdict": "approve"})
        return f"{code} {(out or {}).get('outcome') or (out or {}).get('reason')}"


def check(results: dict[str, Any], name: str, ok: bool, detail: Any = None) -> None:
    results[name] = {"ok": bool(ok), "detail": detail}
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail is not None else ""), flush=True)


def walk(seam: Seam, draft_id: str, sid: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    origin = seam.fixture
    stop = threading.Event()
    threading.Thread(target=seam.listen, args=(stop,), daemon=True).start()
    time.sleep(1.0)
    _, lease = seam.http("POST", "/mcp/lease", {"space_id": sid})
    seam.lease, seam.mcp_url = lease["token"], lease["url"]

    # 1. The keep opened the access step, and the site became the project's (trust from onboarding).
    _, draft = seam.http("GET", f"/drafts/{draft_id}")
    _, listed = seam.http("GET", f"/spaces/{sid}/sites")
    check(
        results,
        "keep_opens_the_access_step_with_the_confirmed_site",
        draft["step"] == "access"
        and [(s["origin"], s["state"]) for s in draft["sites"]] == [(origin, "open")]
        and [s["origin"] for s in listed["sites"]] == [origin],
        {"step": draft["step"], "sites": draft.get("sites"), "project_sites": listed["sites"]},
    )

    # 2. Sign in: her browser opens the site in front, the person has the wheel.
    since = len(seam.events)
    code, draft = seam.http("POST", f"/drafts/{draft_id}/access", {"origin": origin, "act": "sign_in"})
    tab = (draft or {}).get("sites", [{}])[0].get("tab")
    check(
        results, "sign_in_opens_her_browser_and_hands_the_wheel", code == 200 and isinstance(tab, int), draft
    )
    early = seam.http("POST", f"/drafts/{draft_id}/access", {"origin": origin, "act": "check"})[1]
    check(
        results,
        "before_signing_in_the_look_says_not_yet",
        early["sites"][0]["state"] == "open" and "sign-in" in early["sites"][0].get("reason", ""),
        early["sites"][0],
    )
    pressed = seam.press_sign_in(tab)
    back = seam.wheel(tab, since)
    _, draft = seam.http("POST", f"/drafts/{draft_id}/access", {"origin": origin, "act": "check"})
    check(
        results,
        "signed_in_after_the_person_signs_in_and_the_draft_is_saved",
        back is not None and draft["sites"][0]["state"] == "signed_in" and draft["step"] == "saved",
        {"pressed": pressed, "wheel": back, "draft_site": draft["sites"][0], "step": draft["step"]},
    )
    state = seam.state()
    check(results, "the_site_saw_one_sign_in", state["signins"] == 1, {"signins": state["signins"]})

    # 3. The overview: clean.
    _, listed = seam.http("GET", f"/spaces/{sid}/sites")
    check(
        results,
        "overview_clean",
        [s["access"] for s in listed["sites"]] == ["signed_in"],
        listed["sites"],
    )
    opened, card = seam.mcp("page_open", url=f"{origin}/account")
    check(
        results,
        "her_hand_opens_the_site_on_her_own",
        card is None and "Your account" in opened,
        opened[:160],
    )

    # 4. The sign-in lapses (the fixture forgets it): the look finds the sign-in page; a blocker.
    with urllib.request.urlopen(f"{origin}/expire", timeout=10) as r:
        r.read()
    since = len(seam.events)
    _, lapsed = seam.http("POST", f"/spaces/{sid}/sites/check", {"origin": origin})
    time.sleep(0.5)
    heard = [e for e in seam.events[since:] if e["type"] == "site"]
    check(
        results,
        "lapse_shows_the_blocker_live",
        lapsed["access"] == "signed_out"
        and any(e["site"]["access"] == "signed_out" and e["space_id"] == sid for e in heard),
        {"site": lapsed, "events": heard},
    )
    refused, card = seam.mcp("page_open", url=f"{origin}/account")
    check(
        results,
        "a_hand_on_a_signed_out_site_is_refused_with_the_way_back",
        card is None and "Sign in again" in refused,
        refused,
    )

    # 5. Sign in again from the overview: the tab, the wheel, the person signs in, the look: clean.
    since = len(seam.events)
    code, started = seam.http("POST", f"/spaces/{sid}/sites/sign_in", {"origin": origin})
    again_tab = (started or {}).get("tab")
    pressed = seam.press_sign_in(again_tab) if isinstance(again_tab, int) else "no tab"
    back = seam.wheel(again_tab, since) if isinstance(again_tab, int) else None
    _, site = seam.http("POST", f"/spaces/{sid}/sites/check", {"origin": origin})
    _, listed = seam.http("GET", f"/spaces/{sid}/sites")
    check(
        results,
        "sign_in_again_clears_the_blocker",
        code == 200
        and back is not None
        and site["access"] == "signed_in"
        and [s["access"] for s in listed["sites"]] == ["signed_in"],
        {"started": started, "pressed": pressed, "wheel": back, "site": site},
    )

    # 6. The looks close their hidden tabs: only the tabs the person signed in on stay open.
    tabs, _ = seam.mcp("tabs_read")
    looks = [line for line in tabs.splitlines() if line.startswith("tab ")]
    check(results, "looks_close_their_hidden_tabs", len(looks) == 3, tabs)  # two sign-ins, one open
    stop.set()
    results["calls"] = seam.log
    results["events"] = seam.events
    return results


def app_data(identifier: str) -> Path:
    return Path(os.environ["APPDATA"]) / identifier


def kill(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is not None and proc.poll() is None:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)


def launch(shell_log: Path | None) -> tuple[subprocess.Popen[bytes], subprocess.Popen[bytes]]:
    """Vite on 1433 and the shell under the seam's own identity, its daemon on 8782 (scripted)."""
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
    env = dict(
        os.environ, ATHENA_DAEMON_PORT=str(DAEMON_PORT), ATHENA_ENGINE="scripted", ATHENA_TWIN_POLL="0"
    )
    log = open(shell_log, "wb") if shell_log else subprocess.DEVNULL  # noqa: SIM115
    shell = subprocess.Popen(
        [pnpm, "tauri", "dev", "--config", str(config)],
        cwd=desktop,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return vite, shell


def connect(data: Path, fixture_url: str) -> Seam:
    deadline = time.monotonic() + 600
    while not (data / "daemon.json").exists():
        if time.monotonic() > deadline:
            raise RuntimeError("the shell did not start its daemon within 10 minutes")
        time.sleep(1)
    hand = json.loads((data / "daemon.json").read_text())
    seam = Seam(f"http://127.0.0.1:{hand['port']}", hand["token"], fixture_url)
    for _ in range(240):
        try:
            seam.http("GET", "/engine")
            break
        except OSError:
            time.sleep(0.5)
    time.sleep(3)  # her browser's relay polls once the daemon answers
    return seam


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="access_seam")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--shell-log", type=Path)
    args = parser.parse_args(argv)
    server, _ = fixture.serve(FIXTURE_PORT)
    fixture_url = f"http://127.0.0.1:{FIXTURE_PORT}"
    data = app_data(IDENTIFIER)
    vite = shell = None
    try:
        (data / "daemon.json").unlink(missing_ok=True)
        vite, shell = launch(args.shell_log)
        seam = connect(data, fixture_url)
        started = time.monotonic()
        draft_id, sid = onboard(data, fixture_url, f"{fixture_url}/account")
        print(f"onboarded draft {draft_id} in {sid} ({time.monotonic() - started:.1f} s, stand-in engine)")
        results = walk(seam, draft_id, sid)
        failed = [k for k, v in results.items() if isinstance(v, dict) and v.get("ok") is False]
        report = json.dumps(results, indent=2)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(report, encoding="utf-8")
        print(f"{len(failed)} failed: {failed}", flush=True)
        return 1 if failed else 0
    finally:
        server.shutdown()
        kill(shell)
        kill(vite)


if __name__ == "__main__":
    sys.exit(main())
