"""The agent-leases seam (spark agent-leases): a real agent host against the built daemon.

    uv run python scripts/agents_seam.py [--port 8797] [--model haiku]

Starts the daemon on a free loopback port with a throwaway data folder, makes a project with one app
(the repo's stdio test app: a read-only `look`, a destructive `erase`), connects an agent named
"Seam Claude" through `POST /spaces/{id}/agents` with limits of one unattended `erase`, signs the grant card,
then runs `claude -p` with exactly the config the Agents section shows. Checks, from the daemon's side:

1. the connect answers a config, and the limits wait for a signature (state `waiting`);
2. the host's `initialize` name is recorded beside the person's name for it;
3. the agent leaves a note (`note_add`);
4. the first `erase` runs without a card, the second files a card that says who asks;
5. `card_status` on that card answers `waiting` to the agent;
6. revoke ends the agent: its token is refused at `/mcp`.

The daemon is ended with its process tree. Nothing is written outside the temporary folder.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "agents-seam"
LABEL = "Seam Claude"
PROMPT = (
    "You are testing a project's tools. Do exactly this, in order, and nothing else: "
    "1) call note_add with text 'seam: started'. "
    "2) call the tool whose name ends in __erase, with no arguments. "
    "3) call it again. "
    "4) if any answer carried a pending card_id, call card_status with that card_id. "
    "Then reply with one line per call: the tool name and the first sentence of its answer."
)


def free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def api(port: int, method: str, path: str, body: Any = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def mcp_status(port: int, bearer: str) -> int:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/mcp",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode(),
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {bearer}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8797)
    parser.add_argument("--model", default="haiku")
    opts = parser.parse_args()
    port = opts.port
    if not free(port):
        print(f"port {port} is taken; pass --port")
        return 2
    results: list[tuple[str, bool, str]] = []

    def step(name: str, ok: bool, seen: Any = "") -> None:
        results.append((name, ok, json.dumps(seen)[:400] if not ok else ""))
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {results[-1][2]}"), flush=True)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        env = {**os.environ, "ATHENA_TOKEN": TOKEN, "ATHENA_TWIN_POLL": "0"}
        daemon = subprocess.Popen(
            [sys.executable, "-m", "athena.server", "--data", str(Path(tmp) / "data"), "--port", str(port), "--no-peer"],
            cwd=ROOT,
            env={**env, "PYTHONPATH": str(ROOT / "src")},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            assert daemon.stdout is not None
            line = daemon.stdout.readline()
            if "listening" not in line:
                print("the daemon did not start:", line)
                return 1
            space = api(port, "POST", "/spaces", {"name": "Agents seam"})["id"]
            app = api(
                port,
                "POST",
                f"/spaces/{space}/apps",
                {"kind": "mcp_stdio", "label": "Queue", "argv": [sys.executable, str(ROOT / "tests/apps_fake.py")]},
            )
            if not app.get("tools"):
                app = api(port, "POST", f"/spaces/{space}/apps/{app['app_id']}/probe")
            print("app:", app.get("status"), [t["name"] for t in app.get("tools", [])], app.get("reason", ""))
            erase = next(n for n in (t["name"] for t in app.get("tools", [])) if n == "erase")
            slug = app.get("slug", "queue")
            body = {"label": LABEL, "minutes": 30, "ceiling": {"tools": [f"{slug}__{erase}"], "max_calls": 1, "minutes": 30}}
            made = api(port, "POST", f"/spaces/{space}/agents", body)
            lease = made["lease"]
            step("1 connect answers a config; the limits wait for a signature", lease["state"] == "waiting" and made["token"] in made["config"], lease)
            grant = lease["ceiling"]["card_id"]
            api(port, "POST", f"/decisions/{grant}", {"verdict": "approve"})
            cfg = Path(tmp) / "mcp.json"
            cfg.write_text(made["config"], encoding="utf-8")
            started = time.monotonic()
            run = subprocess.run(
                [
                    "claude", "-p", PROMPT, "--model", opts.model, "--mcp-config", str(cfg), "--strict-mcp-config",
                    "--tools", "", "--allowedTools", "mcp__athena__*", "--max-turns", "12", "--output-format", "text",
                ],
                capture_output=True, text=True, timeout=300, encoding="utf-8",
            )
            print(f"--- claude -p ({time.monotonic() - started:.0f} s, exit {run.returncode}) ---\n{run.stdout.strip()}\n---")
            agents = api(port, "GET", f"/spaces/{space}/agents")["agents"]
            now = next(a for a in agents if a["id"] == lease["id"])
            step("2 the host's own name is kept beside the person's", bool(now.get("client")) and now["label"] == LABEL, now)
            notes = api(port, "GET", f"/spaces/{space}/agent-notes")["notes"]
            step("3 the agent left a note", any("seam: started" in n["text"] and n["label"] == LABEL for n in notes), notes)
            cards = api(port, "GET", "/cards")["cards"]
            asks = [c for c in cards if c["action"] == "app_act" and c["label"].startswith(f"{LABEL} asks")]
            ceiling = now.get("ceiling", {})
            step("4 one erase ran without a card, the next filed one that says who asks", ceiling.get("used") == 1 and len(asks) == 1, {"ceiling": ceiling, "cards": cards})
            step("5 card_status answered the agent (its reply names it)", "card_status" in run.stdout and "waiting" in run.stdout.lower(), run.stdout[-600:])
            api(port, "DELETE", f"/spaces/{space}/agents/{lease['id']}")
            step("6 revoke ends it: the token is refused at /mcp", mcp_status(port, made["token"]) == 401)
        finally:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(daemon.pid)], capture_output=True) if os.name == "nt" else daemon.kill()
            daemon.wait(timeout=10)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"{passed}/{len(results)}")
    return 0 if passed == len(results) == 6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
