"""Phase 0's live seam (business-channel, ADR 0013/0015): a scripted session drives her real browser
(the built Tauri shell on WebView2) through Athena's MCP server, against the local simulated test
pages (`athena.browser.fixture`), and signs each card the way her window does (`POST /decisions`).
No model is called: the session is a script, so every step is the same each run. Nothing reaches a
real account.

    uv run python scripts/browser_seam.py                  # fixture + vite 1433 + the shell, drive, report
    uv run python scripts/browser_seam.py --attach <data>  # drive an app already running on that data folder
    uv run python scripts/browser_seam.py --live-turn      # also one Claude Code turn with tools on

The shell runs as a separate app identity (`ai.athena.meta.seam`), so it never shares a data folder,
a browser profile or a port with the person's own Athena. Ports: fixture 8781, daemon 8782, Vite 1433.
It ends both process trees and prints one JSON report; `--out` writes it to a file too.
"""

from __future__ import annotations

import argparse
import hashlib
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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from athena.browser import fixture  # noqa: E402

IDENTIFIER = "ai.athena.meta.seam"
FIXTURE_PORT = 8781
DAEMON_PORT = 8782
VITE_PORT = 1433


class Seam:
    def __init__(self, url: str, token: str, fixture_url: str) -> None:
        self.url = url
        self.token = token
        self.fixture = fixture_url
        self.lease = ""
        self.mcp_url = ""
        self.steps: list[dict[str, Any]] = []
        self._id = 0

    # -- plumbing --------------------------------------------------------------------------------
    def http(self, method: str, path: str, body: Any = None, token: str | None = None) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token or self.token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                raw = r.read()
                return r.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read()
            return e.code, json.loads(raw) if raw else None

    def mcp(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        req = urllib.request.Request(self.mcp_url, data=json.dumps(msg).encode(), method="POST")
        req.add_header("Authorization", f"Bearer {self.lease}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=900) as r:
            answer = json.loads(r.read())
        if "error" in answer:
            raise RuntimeError(answer["error"])
        return answer["result"]

    def tool(self, name: str, **args: Any) -> tuple[str, str | None]:
        """(text, pending card id)."""
        started = time.monotonic()
        result = self.mcp("tools/call", {"name": name, "arguments": args})
        text = result["content"][0]["text"]
        pending = (result.get("structuredContent") or {}).get("pending", {}).get("card_id")
        self.steps.append(
            {
                "tool": name,
                "args": args,
                "pending": pending,
                "ms": int((time.monotonic() - started) * 1000),
                "said": text[:300],
            }
        )
        print(f"  {name} {args} -> {'card ' + pending if pending else text[:140]!r}", flush=True)
        return text, pending

    def sign(self, card_id: str, verdict: str = "approve") -> tuple[int, Any]:
        started = time.monotonic()
        code, card = self.http("POST", f"/decisions/{card_id}", {"verdict": verdict})
        self.steps.append(
            {
                "sign": card_id,
                "verdict": verdict,
                "status": code,
                "ms": int((time.monotonic() - started) * 1000),
                "outcome": (card or {}).get("outcome") or (card or {}).get("reason"),
            }
        )
        print(f"  sign {card_id} {verdict} -> {code} {self.steps[-1]['outcome']!r}", flush=True)
        return code, card

    def state(self) -> dict[str, Any]:
        with urllib.request.urlopen(self.fixture + "/state", timeout=10) as r:
            return json.loads(r.read())

    @staticmethod
    def ref(found: str, contains: str) -> str:
        for line in found.splitlines():
            if line.startswith("ref_") and contains.lower() in line.lower():
                return line.split()[0]
        raise AssertionError(f"no ref for {contains!r} in:\n{found}")

    @staticmethod
    def tab_of(opened: str) -> int:
        return int(opened.split(":", 1)[0].split()[-1])


def check(results: dict[str, Any], name: str, ok: bool, detail: Any = None) -> None:
    results[name] = {"ok": bool(ok), "detail": detail}
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail is not None else ""), flush=True)


def wait_wheel(seam: Seam, seen: list[dict[str, Any]], stop: threading.Event) -> None:
    req = urllib.request.Request(f"{seam.url}/events?token={seam.token}")
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                if stop.is_set():
                    return
                line = raw.decode().strip()
                if line.startswith("data:"):
                    event = json.loads(line[5:])
                    if event.get("type") == "wheel":
                        seen.append(event)
    except Exception:
        return


def drive(seam: Seam, live_turn: bool) -> dict[str, Any]:
    results: dict[str, Any] = {}
    origin = seam.fixture
    code, space = seam.http("POST", "/spaces", {"name": "Music channel (seam)", "apps": [origin]})
    assert code == 201, space
    sid = space["id"]
    _, lease = seam.http("POST", "/mcp/lease", {"space_id": sid})
    seam.lease, seam.mcp_url = lease["token"], lease["url"]
    init = seam.mcp(
        "initialize",
        {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "seam", "version": "0"}},
    )
    tools = [t["name"] for t in seam.mcp("tools/list")["tools"]]
    check(
        results,
        "mcp_lists_browser_tools",
        "page_upload" in tools and "page_open" in tools,
        {"server": init["serverInfo"], "tools": len(tools)},
    )
    _, bad = seam.http("POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, token=seam.token)
    check(results, "daemon_token_is_not_a_lease", (bad or {}).get("error") == "unauthorized")

    # 1. Read a channel page.
    opened, _ = seam.tool("page_open", url=f"{origin}/channel")
    channel = seam.tab_of(opened)
    page, _ = seam.tool("page_read", tab=channel)
    check(
        results,
        "read_channel_page",
        "Night Drive in Glass" in page and "page data, not instructions" in page,
        page[:160],
    )

    # 2. A signed comment posts exactly once.
    opened, _ = seam.tool("page_open", url=f"{origin}/watch?v=t1")
    watch = seam.tab_of(opened)
    found, _ = seam.tool("page_find", tab=watch, query="comment")
    box, button = seam.ref(found, "Add a comment"), seam.ref(found, "button  Comment")
    _, fill = seam.tool(
        "page_fill", tab=watch, ref=box, expect="Add a comment", value="Lovely track - simulated seam comment"
    )
    _, click = seam.tool("page_click", tab=watch, ref=button, expect="Comment")
    check(results, "acts_file_cards_not_acts", bool(fill and click) and seam.state()["comments"] == [])
    assert fill and click
    seam.sign(fill)
    seam.sign(click)
    again, _ = seam.sign(click)
    time.sleep(1.0)
    comments = seam.state()["comments"]
    check(
        results,
        "comment_posts_exactly_once",
        len(comments) == 1 and again == 400,
        {"comments": comments, "second_sign": again},
    )

    # 3. An approval is spent on the page it was given for.
    found, _ = seam.tool("page_find", tab=channel, query="")
    first, last = seam.ref(found, "Night Drive"), seam.ref(found, "Low Tide")
    _, a = seam.tool("page_click", tab=channel, ref=first, expect="Night Drive in Glass")
    _, b = seam.tool("page_click", tab=channel, ref=last, expect="Low Tide Choir")
    assert a and b
    seam.sign(a)
    time.sleep(1.5)
    code_b, card_b = seam.sign(b)
    check(results, "moved_page_refuses_old_card", code_b == 400 and "changed" in str(card_b), card_b)
    seam.sign(b, "decline")

    # 4. An untrusted site is a card even for a read.
    _, untrusted = seam.tool("page_open", url=f"http://localhost:{FIXTURE_PORT}/channel")
    check(results, "untrusted_open_is_a_card", untrusted is not None)
    if untrusted:
        seam.sign(untrusted, "decline")

    # 5. Download two files into the project's files.
    opened, _ = seam.tool("page_open", url=f"{origin}/downloads")
    downloads = seam.tab_of(opened)
    found, _ = seam.tool("page_find", tab=downloads, query="download")
    files: dict[str, str] = {}
    for label, mb in (("WAV", 0), ("5 MB", 5), ("50 MB", 50)):
        ref = seam.ref(found, label)
        expect = next(line.split("  ", 2)[2] for line in found.splitlines() if line.startswith(ref))
        _, card = seam.tool("page_download", tab=downloads, ref=ref, expect=expect)
        assert card
        _, signed = seam.sign(card)
        outcome = (signed or {}).get("outcome", "")
        fid = next((w for w in outcome.split() if w.startswith("fil_")), "")
        files[label] = fid
        if mb:
            files[f"{label}_sha"] = hashlib.sha256(fixture.draft_bytes(mb)).hexdigest()
    listed, _ = seam.tool("file_list")
    _, listing = seam.http("GET", f"/spaces/{sid}/files")
    by_id = {f["id"]: f for f in listing["files"]}
    check(
        results,
        "downloads_land_in_project_files",
        all(files[k] in by_id for k in ("WAV", "5 MB", "50 MB"))
        and by_id[files["5 MB"]]["sha256"] == files["5 MB_sha"],
        listed,
    )

    # 6. Upload into a file input inside an open shadow root inside a same-origin iframe.
    opened, _ = seam.tool("page_open", url=f"{origin}/studio")
    studio = seam.tab_of(opened)
    found, _ = seam.tool("page_find", tab=studio, query="Upload videos")
    _, open_dialog = seam.tool(
        "page_click", tab=studio, ref=seam.ref(found, "Upload videos"), expect="Upload videos"
    )
    assert open_dialog
    seam.sign(open_dialog)
    waited, _ = seam.tool("page_wait", tab=studio, text="Select files", timeout_ms=10000)
    found, _ = seam.tool("page_find", tab=studio, role="file")
    file_ref = seam.ref(found, "file")
    measured: dict[str, Any] = {}
    for label in ("5 MB", "50 MB"):
        _, card = seam.tool("page_upload", tab=studio, ref=file_ref, file_id=files[label])
        assert card
        code, signed = seam.sign(card)
        measured[label] = {
            "status": code,
            "outcome": (signed or {}).get("outcome"),
            "sign_ms": seam.steps[-1]["ms"],
        }
        for _ in range(100):
            if any(u.get("sha256") == files[f"{label}_sha"] for u in seam.state()["uploads"]):
                break
            time.sleep(0.3)
    uploads = seam.state()["uploads"]
    check(
        results,
        "upload_through_shadow_dom_in_iframe",
        all(any(u.get("sha256") == files[f"{k}_sha"] for u in uploads) for k in ("5 MB", "50 MB")),
        {"measured": measured, "page_saw": uploads, "wait": waited},
    )

    # 7. Privacy is private: a "Public" control is refused even when signed.
    found, _ = seam.tool("page_find", tab=studio, query="")
    _, public = seam.tool("page_click", tab=studio, ref=seam.ref(found, "Public"), expect="Public")
    assert public
    code, card = seam.sign(public)
    check(results, "public_is_refused_when_signed", code == 400 and "public" in str(card).lower(), card)
    seam.sign(public, "decline")
    _, title = seam.tool(
        "page_fill",
        tab=studio,
        ref=seam.ref(found, "Title"),
        expect="Title (required)",
        value="Night Drive in Glass - Mira Vale (simulated)",
    )
    _, save = seam.tool("page_click", tab=studio, ref=seam.ref(found, "Save draft"), expect="Save draft")
    assert title and save
    seam.sign(title)
    seam.sign(save)
    time.sleep(1.0)
    saves = seam.state()["saves"]
    check(results, "draft_saved_private", saves and saves[-1]["visibility"] == "private", saves)

    # 8. Hand the wheel: the tab comes forward; the page moving on is heard. The person's own act is
    # simulated here by two more signed hands (Athena never solves a check on her own).
    seen: list[dict[str, Any]] = []
    stop = threading.Event()
    threading.Thread(target=wait_wheel, args=(seam, seen, stop), daemon=True).start()
    opened, _ = seam.tool("page_open", url=f"{origin}/captcha")
    about = seam.tab_of(opened)
    _, wheel = seam.tool(
        "wheel_handoff", tab=about, say="Tick the box and show the email; I'll take it from there"
    )
    assert wheel
    seam.sign(wheel)
    found, _ = seam.tool("page_find", tab=about, query="")
    _, tick = seam.tool("page_click", tab=about, ref=seam.ref(found, "robot"), expect="I am not a robot")
    _, show = seam.tool(
        "page_click", tab=about, ref=seam.ref(found, "Show email"), expect="Show email address"
    )
    assert tick and show
    seam.sign(tick)
    seam.sign(show)
    for _ in range(40):
        if seen:
            break
        time.sleep(0.25)
    stop.set()
    after, _ = seam.tool("page_read", tab=about)
    check(
        results,
        "wheel_back_is_heard",
        bool(seen) and seen[0]["wheel"]["state"] == "back" and "mira.vale@" in after,
        seen,
    )

    if live_turn:
        results["live_turn"] = live(seam, sid)
    results["steps"] = seam.steps
    return results


def live(seam: Seam, sid: str) -> dict[str, Any]:
    """One Claude Code turn with tools on: she reads the channel page through her browser."""
    started = time.monotonic()
    body = json.dumps(
        {
            "text": f"Open {seam.fixture}/channel in your browser and tell me the titles of the tracks listed there.",
            "space_id": sid,
        }
    ).encode()
    req = urllib.request.Request(seam.url + "/run", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {seam.token}")
    req.add_header("Content-Type", "application/json")
    events = []
    with urllib.request.urlopen(req, timeout=600) as r:
        for raw in r:
            events.append(json.loads(raw))
    text = "".join(e.get("delta", "") for e in events if e["type"] == "text")
    out = {
        "engine": events[0].get("engine"),
        "tools": [e["name"] for e in events if e["type"] == "tool"],
        "said": text[:600],
        "done": events[-1],
        "wall_s": round(time.monotonic() - started, 1),
        "names_all_three": all(t in text for t in ("Night Drive", "Paper Lanterns", "Low Tide")),
    }
    print("LIVE", json.dumps(out)[:800], flush=True)
    return out


def app_data(identifier: str) -> Path:
    return Path(os.environ["APPDATA"]) / identifier


def kill(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is not None and proc.poll() is None:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="browser_seam")
    parser.add_argument("--attach", type=Path, help="the data folder of an app that is already running")
    parser.add_argument("--live-turn", action="store_true")
    parser.add_argument("--engine", default="scripted", help="ATHENA_ENGINE for the launched daemon")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--shell-log", type=Path, help="keep the shell's own output here")
    args = parser.parse_args(argv)

    server, _ = fixture.serve(FIXTURE_PORT)
    fixture_url = f"http://127.0.0.1:{FIXTURE_PORT}"
    vite = shell = None
    data = args.attach or app_data(IDENTIFIER)
    try:
        if args.attach is None:
            (data / "daemon.json").unlink(missing_ok=True)
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
                os.environ,
                ATHENA_DAEMON_PORT=str(DAEMON_PORT),
                ATHENA_ENGINE=args.engine,
                ATHENA_TWIN_POLL="0",
            )
            log = open(args.shell_log, "wb") if args.shell_log else subprocess.DEVNULL  # noqa: SIM115
            shell = subprocess.Popen(
                [pnpm, "tauri", "dev", "--config", str(config)],
                cwd=desktop,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        deadline = time.monotonic() + 600
        while not (data / "daemon.json").exists():
            if time.monotonic() > deadline:
                raise RuntimeError("the shell did not start its daemon within 10 minutes")
            time.sleep(1)
        hand = json.loads((data / "daemon.json").read_text())
        seam = Seam(f"http://127.0.0.1:{hand['port']}", hand["token"], fixture_url)
        for _ in range(240):  # the relay connects once the daemon answers
            try:
                _, engine = seam.http("GET", "/engine")
                break
            except OSError:
                time.sleep(0.5)
        time.sleep(3)
        print("engine:", engine, flush=True)
        results = drive(seam, args.live_turn)
        results["engine"] = engine
        failed = [k for k, v in results.items() if isinstance(v, dict) and v.get("ok") is False]
        report = json.dumps(results, indent=2)
        if args.out:
            args.out.write_text(report, encoding="utf-8")
        print(f"{len(failed)} failed: {failed}", flush=True)
        return 1 if failed else 0
    finally:
        server.shutdown()
        kill(shell)
        kill(vite)


if __name__ == "__main__":
    sys.exit(main())
