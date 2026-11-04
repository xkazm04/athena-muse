"""The README's screenshots: the BUILT desktop against a throwaway daemon on a scratch data folder,
seeded with the repo's own fixtures, driven by Playwright, every shot 1280x800 (her window at its own
400x620) in the app's default dark look. Nothing reaches a network and nothing spends: the daemon runs
the scripted engine, Gmail and Notion are the twin tests' fakes inside its process, and the other
paired computers are peer hosts on the loopback. Everything shown is invented and labelled simulated.

    uv run python scripts/readme_shots.py               # build, seed, serve on 5196, drive, write the shots
    uv run python scripts/readme_shots.py --no-build    # reuse apps/desktop/dist
    uv run python scripts/readme_shots.py --page-port 5197

What is seeded, through the daemon's own code (`--serve`, a flag only this script passes):
- the simulated music channel (scripts/business_fixture.py), its report arranged and a conversation
  played through the real turn loop by the spread fixture's stand-in (scripts/spread_fixture.py), one
  card left waiting for a signature; its routines run once against the simulated browser
  (scripts/routines_fixture.py); its apps, one per kind, with a paired computer's copy attached;
- the staged chore need (athena.drafts.demo) taken to its test-run verdict on the drafts tests' stand-in
  engine (tests/drafts_kit.Fake), and a second one kept so the shelf holds one of yours;
- two twins set up, rehearsed and gone live as scripts/twin_fixture.py does, one working missions;
- devices: this computer, a second computer paired over the loopback (online), a phone, and a request
  waiting for approval.

The first run's probe answer is the only thing the page is told by the script rather than the daemon
(a key check would ask Meta): the two engine-key calls are answered in the browser, labelled here.
It ends every process it started and prints one JSON report; exit 1 when a shot has a problem.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
SHOTS = REPO / "docs/readme/shots"
VITE_PORT = 5196
TOKEN = "shots"
ENGINE = "scripted"
VIEW = {"width": 1280, "height": 800}
HER = {"width": 400, "height": 620}

FAKE_KEY = "muse-readme-shot-not-a-real-key-000000"  # typed into the first run; never sent anywhere


def app_url(port: int) -> str:
    return f"http://localhost:{port}"


# --- the throwaway daemon, seeded (--serve only) ------------------------------------------------------


class MemorySeal:
    """A seal kept in memory: the peer keys of a throwaway run never touch the person's keyring."""

    kind = "memory"

    def __init__(self) -> None:
        self.held: dict[str, str] = {}

    def seal(self, name: str, value: str) -> None:
        self.held[name] = value

    def unseal(self, name: str) -> str | None:
        return self.held.get(name)

    def destroy(self, name: str) -> None:
        self.held.pop(name, None)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def seed_channel(daemon: Any) -> str:
    """The music channel: records, the report arranged, a conversation played through the turn loop."""
    from spread_fixture import Clock, StandIn, arrange, script
    from spread_fixture import seed as channel

    from athena import clock
    from athena.turn import execute, run_turn

    tick = Clock()
    real = clock.monotonic_ms
    clock.monotonic_ms = tick  # type: ignore[assignment]  # the stand-in's authored pace
    try:
        daemon.gate.set_executor(lambda card: execute(daemon, card))
        space = channel(daemon)
        arrange(daemon, tick, space)
        for turn in script(space):
            engine = StandIn(tick, turn["rounds"], turn["think"])
            events = list(run_turn(daemon, engine, turn["say"], space))
            if turn.get("sign"):
                card = next(e["card"] for e in events if e["type"] == "card")
                daemon.gate.resolve(card["id"], "approve")
    finally:
        clock.monotonic_ms = real  # type: ignore[assignment]
    return str(space)


def seed_routines(daemon: Any, space: str) -> None:
    """The channel's routines, run once each as scripts/routines_fixture.py does."""
    from business_fixture import SITE

    from athena.routines.host import Host
    from browser_kit import FakeShell
    from routines_kit import PricedEngine

    daemon.sites.add(space, SITE, "YouTube (simulated)", f"{SITE}/account", "The channel's site")
    daemon.sites.looked(space, SITE, "signed_in", "simulated")
    routines = {r["kind"]: r for r in daemon.routines.ensure_defaults(space)}
    daemon.routines.change(routines["stats"]["id"], {"url": f"{SITE}/studio/analytics"})
    readings = {"readings": [{"metric": "views", "value": 612}, {"metric": "subscribers", "value": 48}]}
    pricey = Host(daemon, lambda: PricedEngine(cost=0.3, answer={"tracks": []}))
    cheap = Host(daemon, lambda: PricedEngine(cost=0.002, answer=readings))
    with FakeShell(daemon.relay):
        pricey.run_now(routines["watch"]["id"])
        cheap.run_now(routines["stats"]["id"])
        cheap.run_now(routines["outreach"]["id"])
    daemon.routines.change(routines["inbox"]["id"], {"state": "paused"})


def seed_drafts(daemon: Any) -> dict[str, str]:
    """The staged need taken to its test-run verdict (left there), and once more kept."""
    from athena.drafts import author, key, preview, rehearse, save
    from drafts_kit import Fake, agreed_draft

    out: dict[str, str] = {}
    for name in ("kept", "verdict"):
        engine = Fake()
        draft = agreed_draft(daemon)
        for _ in author.write(daemon, engine, draft["id"]):
            pass
        cards = preview.preview(daemon, engine, draft["id"])
        marks = [{"expected_id": c["id"], "mark": "yes"} for c in cards]
        key.put_key(daemon, engine, draft["id"], {"marks": marks, "missing": [], "never": []})
        for _ in rehearse.rehearse(daemon, engine, draft["id"]):
            pass
        if name == "kept":
            save.verdict(daemon, draft["id"], "keep", None)
        out[name] = draft["id"]
    out["shaping"] = seed_shaping(daemon)["id"]
    # each draft started a project named after the need; one name each, so the projects read apart
    names = {
        "kept": "School and club",
        "verdict": "Club invoice check",
        "shaping": "Club invoice (new draft)",
    }
    for name, draft_id in out.items():
        daemon.spaces.update(daemon.drafts.get(draft_id)["space_id"], {"name": names[name]})
    return out


def seed_shaping(daemon: Any) -> Any:
    """The staged need mid-sketch: the person's own pieces inked, her guesses for the steps still in
    pencil, what she must never do not asked yet, and her open question on it."""
    from athena.drafts import shape
    from athena.drafts.demo import NEED, staged_sketch

    draft = shape.start(daemon, NEED)
    sketch = staged_sketch()
    nodes = []
    for node in sketch["nodes"]:
        if node["slot"] == "never":
            continue
        if node["slot"] in ("steps", "output"):
            node = {**node, "origin": "athena", "confirmed": False}
        nodes.append(node)
    ask = {
        "slot": "never",
        "text": "Is there anything she must never do with the club?",
        "suggestions": ["Never pay the invoice", "Never write to the club without me", "Nothing else"],
        "follow_up": 0,
    }
    return daemon.drafts.put({**draft, "sketch": {**sketch, "nodes": nodes}, "step": "shape", "ask": ask})


def seed_twins(daemon: Any) -> list[str]:
    """Two twins made the way scripts/twin_fixture.py makes its earlier ones, over the fake Gmail and
    Notion (the world stays attached: the twins' pages read the fakes while the daemon serves)."""
    from datetime import UTC, datetime

    from starlette.testclient import TestClient
    from twin_fixture import Clock, Drive, earlier_twin, gmail_thread

    from athena.server import create_app
    from missions_kit import MissionWorld

    d = Drive.__new__(Drive)
    d.clock = Clock()
    d.daemon = daemon
    d.client = TestClient(create_app(daemon, token=TOKEN), headers={"Authorization": f"Bearer {TOKEN}"})
    d.world = MissionWorld(daemon, d.client)
    w = d.world
    desk = earlier_twin(
        d,
        "Client desk",
        "Answers client email for the studio: quotes, scheduling and invoices.",
        "Chase the overdue invoice from Harbor Bakery",
        datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
    )
    family = earlier_twin(
        d,
        "Family admin",
        "Handles school and club email: forms, pickups and the monthly invoice.",
        "Dispute the extra club days in September with Brightside Club",
        datetime(2026, 9, 15, 9, 0, tzinfo=UTC),
    )
    d.post(family, "twin_pause")
    w.threads["thharbor"] = gmail_thread(
        "Harbor Bakery <accounts@harbor-bakery.example>",
        "Invoice 2026-031",
        ("me", "Hi, a friendly reminder that invoice 2026-031 is now two weeks overdue."),
        ("them", "Hi Alex, sorry this slipped. Can you resend the invoice? It goes out by Friday."),
    )
    w.threads["thquote"] = gmail_thread(
        "Oren Vale <oren@greywater.example>",
        "Album artwork quote",
        ("me", "Hi Oren, here is the quote for the album artwork: three covers, delivered in two weeks."),
        ("them", "Looks good to me. Yes, go ahead!"),
    )
    w.threads["thrush"] = gmail_thread(
        "Pia North <pia@northlight.example>",
        "Poster for Saturday",
        ("them", "Could you rush the poster for Saturday? What would that cost, is $300 enough?"),
    )
    for thread, goal in (
        ("thharbor", "Chase the overdue invoice from Harbor Bakery"),
        ("thquote", "Get Oren's sign-off on the artwork quote"),
        ("thrush", "Answer Pia's rush request for the poster"),
    ):
        d.call("POST", "twin_missions", {"thread": thread, "goal": goal}, status=201, id=desk)
    oren = next(m["id"] for m in d.twin(desk)["missions"] if m["goal"].startswith("Get Oren"))
    return [desk, family, oren]


def seed_apps(daemon: Any, space: str, studio: tuple[str, str] | None) -> None:
    """One app of each kind in the channel's project; the two program kinds as a check found them (no
    app is started or reached here), Gravitone with the paired computer's copy attached."""
    gt_tools = [
        {"name": "gt_read", "description": "Read projects, renders and the queue", "access": "auto"},
        {"name": "gt_spend", "description": "Estimate what a render would cost", "access": "auto"},
        {"name": "gt_launch", "description": "Start a render", "access": "gated"},
        {"name": "gt_job", "description": "Ask after, pause or cancel a render job", "access": "gated"},
    ]
    cut_tools = [
        {"name": "probe_media", "description": "Read a clip's length, size and audio", "access": "auto"},
        {"name": "cut_clip", "description": "Cut a clip to the song's length", "access": "gated"},
    ]
    apps = daemon.apps
    apps.add(space, {"kind": "local_page", "address": "localhost:5173", "label": "Thumbnail studio"})
    daemon.sites.looked(space, "http://localhost:5173", "signed_in", "simulated")
    gt = apps.add(
        space, {"kind": "mcp_http", "address": "http://localhost:3150/api/mcp", "label": "Gravitone"}
    )
    apps.set_probe(space, gt["app_id"], "ok", gt_tools, None)
    cut = apps.add(space, {"kind": "mcp_stdio", "argv": ["clipcut", "--serve"], "label": "Clip cutter"})
    apps.set_probe(space, cut["app_id"], "ok", cut_tools, None)
    if studio is not None:
        peer_id, device = studio
        remote = {"peer_id": peer_id, "device": device, "remote_app_id": "app_0000studio", "status": "ok"}
        apps.put_remote(space, gt["app_id"], {**remote, "tools": gt_tools})
    offered = apps.add(
        "", {"kind": "mcp_http", "address": "http://localhost:3150/api/mcp", "label": "Gravitone"}
    )
    apps.set_probe("", offered["app_id"], "ok", gt_tools, None)
    apps.patch(offered["app_id"], {"offered": True})


def seed_devices(daemon: Any, data: Path) -> tuple[Any, list[Any], tuple[str, str] | None]:
    """This computer (A), Studio-PC paired both ways over the loopback, a phone, and Laptop asking."""
    from athena.peer import devices as peer_devices
    from athena.peer.listener import PeerHost
    from athena.peer.overlay import Overlay

    up = Overlay("up", "127.0.0.1")

    def host(root: Path, name: str) -> Any:
        h = PeerHost(root, port=free_port(), probe=lambda: up, seal=MemorySeal(), admit_loopback=True)
        h.identity.rename(name)
        return h

    a = host(data / "peer", "Desk-PC")
    b = host(data.parent / "studio-peer", "Studio-PC")
    c = host(data.parent / "laptop-peer", "Laptop")
    studio: tuple[str, str] | None = None
    try:
        opened = peer_devices.open_pairing(a, {"kind": "pc"})[1]
        port = a.bound[1]
        b.join("127.0.0.1", port, opened["code"], ["chat", "approve", "memory", "apps"])
        pending = peer_devices.devices(a)[1]["pending"]
        peer_devices.answer_pending(a, {"choice": "approve"}, pending[0]["pairing_id"])
        b.tick()
        back = peer_devices.devices(b)[1]["pending"]
        if back:
            peer_devices.answer_pending(b, {"choice": "approve"}, back[0]["pairing_id"])
        studio = (b.identity.identity.device_id, "Studio-PC")
        b.start()
        a.registry.admit(
            "dev_0a1b2c3d4e5f",
            name="Pixel phone",
            kind="phone",
            grants=["chat", "approve"],
            token="phone-sim",
            expires_days=None,
        )
        opened = peer_devices.open_pairing(a, {"kind": "pc"})[1]
        c.join("127.0.0.1", a.bound[1], opened["code"], ["chat", "memory"])
    except Exception as e:  # devices are one shot among many: the rest still runs
        print(f"devices seed: {type(e).__name__}: {e}", flush=True)
    return a, [b, c], studio


def serve(data: Path, port: int, page_port: int) -> None:
    sys.path.insert(0, str(REPO / "tests"))
    sys.path.insert(0, str(REPO / "scripts"))
    import uvicorn

    from athena.app import Daemon
    from athena.server import APP_ORIGINS, create_app, write_handshake

    started = time.time()
    daemon = Daemon.open(data)
    twins = seed_twins(daemon)  # attaches the fake Gmail and Notion to the daemon's connectors
    print(f"seed: twins {time.time() - started:.0f}s", flush=True)
    drafts = seed_drafts(daemon)
    print(f"seed: drafts {time.time() - started:.0f}s", flush=True)
    space = seed_channel(daemon)
    seed_routines(daemon, space)
    print(f"seed: channel {time.time() - started:.0f}s", flush=True)
    peers, others, studio = seed_devices(daemon, data)
    daemon.peers = peers
    seed_apps(daemon, space, studio)
    daemon.settings.set("active_space_id", space)
    seeded = {"space": space, "drafts": drafts, "twins": twins[:2], "mission": twins[2]}
    (data / "seeded.json").write_text(json.dumps(seeded), encoding="utf-8")
    print(f"seed: done {time.time() - started:.0f}s", flush=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    write_handshake(data, port, TOKEN)
    app = create_app(daemon, TOKEN, origins=(*APP_ORIGINS, app_url(page_port)))
    try:
        uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False)).run(sockets=[sock])
    finally:
        for other in others:
            with contextlib.suppress(Exception):
                other.close()


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


def wait_for(url: str, seconds: float, proc: subprocess.Popen[Any] | None = None) -> None:
    end = time.time() + seconds
    while time.time() < end:
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(f"the process for {url} ended with {proc.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=2):
                return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.4)
    raise RuntimeError(f"nothing answered at {url}")


def end_tree(proc: subprocess.Popen[Any] | None) -> None:
    """Ends a process and everything it started (`pnpm` and Vite start children)."""
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

#: Scrolls only the nearest scrolling ancestor so the element's top ("start") or bottom ("end") shows,
#: leaving the window itself where it is (scrollIntoView would move the window's coat too).
SCROLL_INTO_VIEW = """(el, edge) => {
  let box = el.parentElement;
  const scrolls = (b) =>
    b.scrollHeight > b.clientHeight + 1 && /(auto|scroll)/.test(getComputedStyle(b).overflowY);
  while (box && !scrolls(box)) {
    box = box.parentElement;
  }
  if (!box) return;
  const a = el.getBoundingClientRect(), b = box.getBoundingClientRect();
  box.scrollTop += edge === "end" ? a.bottom - b.bottom + 16 : a.top - b.top - 16;
}"""

BAD_WORDS = ("undefined", "NaN", "[object Object]")


def drive(base: str, page_port: int, seeded: dict[str, Any], only: list[str]) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    result: dict[str, Any] = {"shots": [], "problems": [], "skipped": []}
    SHOTS.mkdir(parents=True, exist_ok=True)
    q = f"?daemon={base}&token={TOKEN}"
    space = seeded["space"]

    def want(name: str) -> bool:
        return not only or any(name.startswith(o) for o in only)

    with sync_playwright() as p:
        browser = p.chromium.launch()

        def context(skip: bool = True, viewport: dict[str, int] = VIEW, view: str = "drawing") -> Any:
            ctx = browser.new_context(viewport=viewport, color_scheme="dark", reduced_motion="reduce")
            init = f"try{{localStorage.setItem('athena.stage.view','{view}');"
            if skip:
                init += "localStorage.setItem('athena.firstRun.skipped','1');"
            ctx.add_init_script(init + "}catch(e){}")
            return ctx

        def page(ctx: Any) -> Any:
            pg = ctx.new_page()
            errors: list[str] = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.errors = errors  # type: ignore[attr-defined]
            return pg

        def shot(pg: Any, name: str, settle_ms: int = 900) -> None:
            pg.wait_for_timeout(settle_ms)
            path = SHOTS / f"{name}.png"
            pg.screenshot(path=str(path))
            result["shots"].append(path.relative_to(REPO).as_posix())
            text = pg.inner_text("body")
            for bad in BAD_WORDS:
                if bad in text:
                    result["problems"].append(f"{name}: the page says {bad!r}")
            scroll = pg.evaluate("[document.documentElement.scrollHeight, innerHeight]")
            if scroll[0] > scroll[1] + 1:
                result["problems"].append(f"{name}: the page scrolls {scroll}")
            if pg.locator('[role="alert"]').count():
                said = " | ".join(pg.locator('[role="alert"]').all_inner_texts())[:200]
                result["problems"].append(f"{name}: an alert shows: {said}")
            if pg.errors:
                result["problems"].append(f"{name}: console errors {pg.errors[:3]}")
                pg.errors.clear()
            print(f"{time.strftime('%H:%M:%S')} shot {name}", flush=True)

        def attempt(name: str, fn: Any) -> None:
            if not want(name):
                return
            try:
                fn(name)
            except Exception as e:
                result["problems"].append(f"{name}: {type(e).__name__}: {e}"[:400])
                print(f"{name} failed: {e}", flush=True)

        def first_run(name: str) -> None:
            ctx = context(skip=False)
            pg = page(ctx)
            engine = {"engine": "muse", "model": "muse-spark-1.3", "key": "file", "simulated": False}
            probe = {"ok": True, "model": "muse-spark-1.3", "latency_ms": 840}
            cors = {
                "access-control-allow-origin": app_url(page_port),
                "access-control-allow-headers": "*",
                "access-control-allow-methods": "*",
                "content-type": "application/json",
            }

            def answer(body: Any) -> Any:
                def handle(route: Any) -> None:
                    if route.request.method == "OPTIONS":
                        route.fulfill(status=204, headers=cors)
                    else:
                        route.fulfill(status=200, headers=cors, body=json.dumps(body))

                return handle

            # Staged: the key check would ask Meta. The page is answered here, in the browser only.
            pg.route(f"{base}/engine/key", answer(engine))
            pg.route(f"{base}/engine/probe", answer(probe))
            pg.goto(f"{app_url(page_port)}/{q}")
            pg.wait_for_selector(".m-firstrun", timeout=30000)
            pg.click('button:has-text("Connect Muse")')
            pg.fill("#fr-key", FAKE_KEY)
            pg.locator("form.m-row button[type=submit]").first.click()
            pg.wait_for_selector('.m-probe .badge[data-tone="success"]', timeout=15000)
            shot(pg, name)
            ctx.close()

        def main_page(hash_: str, ready: str, name: str, before: Any = None, settle_ms: int = 1200) -> None:
            ctx = context()
            pg = page(ctx)
            pg.goto(f"{app_url(page_port)}/{q}#{hash_}")
            pg.wait_for_selector(ready, timeout=30000)
            if before:
                before(pg)
            shot(pg, name, settle_ms)
            ctx.close()

        def to_top(selector: str) -> Any:
            def scroll(pg: Any) -> None:
                pg.locator(selector).first.evaluate("el => el.scrollIntoView({block: 'start'})")
                pg.wait_for_timeout(500)

            return scroll

        def apps_list(pg: Any) -> None:
            to_top("[data-role=apps]")(pg)
            gt = pg.locator('[data-role="app"][data-kind="mcp_http"]').first
            gt.locator("summary").first.click()
            gt.evaluate(
                "el => { const list = el.closest('.m-apps');"
                " list.scrollTop = el.offsetTop - list.offsetTop; }"
            )
            pg.wait_for_timeout(400)

        def twin_draft(name: str) -> None:
            ctx = context()
            pg = page(ctx)
            pg.goto(f"{app_url(page_port)}/{q}#twins")
            pg.wait_for_selector('[data-role="waiting-card"]', timeout=30000)
            pg.locator('[data-role="waiting-card"]').first.click()
            pg.wait_for_selector('[data-role="draft-page"]', timeout=20000)
            shot(pg, name)
            ctx.close()

        def her_window(name: str) -> None:
            ctx = context(viewport=HER)
            pg = page(ctx)
            pg.goto(f"{app_url(page_port)}/athena.html{q}")
            pg.wait_for_selector("[data-spread]", timeout=30000)
            # the page holding the card that waits (the bookmark would scroll the window to its Sign)
            pg.wait_for_function(
                "() => [...document.querySelectorAll('select option')]"
                ".some(o => /Offer Velvet/.test(o.textContent))",
                timeout=20000,
            )
            pick = pg.locator("select").last
            options = pick.evaluate("s => [...s.options].map(o => [o.value, o.textContent])")
            pick.select_option(value=next(v for v, t in options if "Offer Velvet" in t))
            pg.wait_for_timeout(1000)
            pg.locator('button:has-text("Decline")').last.evaluate(SCROLL_INTO_VIEW, "end")
            shot(pg, name, 1500)
            ctx.close()

        def drawer(pg: Any) -> None:
            pg.locator('.m-sky__nodes button:has-text("Studio-PC")').first.click()
            pg.wait_for_selector(".m-cdrawer", timeout=10000)
            pg.wait_for_timeout(1500)
            pg.locator(".m-cdrawer").first.evaluate(SCROLL_INTO_VIEW, "end")
            pg.wait_for_timeout(500)

        desk = seeded["twins"][0]
        mission = seeded.get("mission", "")
        attempt("01-first-run", first_run)
        attempt("02-surface", lambda n: main_page("home", ".m-bar", n))
        attempt("03-projects", lambda n: main_page("projects", ".m-bar", n))
        attempt(
            "04-project",
            lambda n: main_page(f"projects/{space}", "#level-brief", n, to_top("section:has(#level-brief)")),
        )
        attempt("05-apps", lambda n: main_page(f"projects/{space}", ".m-bar", n, apps_list))
        attempt("06-chores", lambda n: main_page("chores", ".m-bar", n))
        attempt("07-chore-scene", lambda n: main_page("chores/prior-auth-denial-appeal", ".m-bar", n))
        attempt("10-twins", lambda n: main_page("twins", ".ov", n))
        attempt(
            "11-twin-mission",
            lambda n: main_page(f"twin/{desk}/mission/{mission}", '[data-role="mission-page"]', n),
        )
        attempt("12-twin-draft", twin_draft)
        attempt("13-devices", lambda n: main_page("settings/devices", ".m-sky__nodes", n))
        attempt("14-devices-drawer", lambda n: main_page("settings/devices", ".m-sky__nodes", n, drawer))
        attempt("15-spread", lambda n: main_page("athena/p2", "[data-spread]", n))
        attempt("16-spread-costs", lambda n: main_page("athena/costs", "[data-spread]", n))
        attempt("17-her-window", her_window)
        attempt("18-settings", lambda n: main_page("settings", ".m-bar", n))
        attempt("19-business-report", lambda n: main_page(f"projects/{space}", ".m-bar", n))
        attempt(
            "20-business-routines",
            lambda n: main_page(f"projects/{space}", ".m-bar", n, to_top("[data-role=routines]")),
        )
        # the stage last: a draft's stage makes its project the active one
        attempt(
            "08-chore-drawing",
            lambda n: main_page(f"stage/{seeded['drafts']['shaping']}", "[data-stage-view]", n),
        )
        attempt(
            "09-chore-test-run",
            lambda n: main_page(f"stage/{seeded['drafts']['verdict']}", "[data-stage-view]", n),
        )
        browser.close()
    return result


def drive_elsewhere(base: str, out: Path, page_port: int, data: Path, only: list[str]) -> dict[str, Any]:
    """Playwright lives beside the system python here: drive from there, and read what it saw."""
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
            cmd = [exe, str(Path(__file__)), "--drive", base, "--out", str(out), "--data", str(data)]
            cmd += ["--page-port", str(page_port), *(["--only", *only] if only else [])]
            subprocess.run(cmd, env=env, check=False)
            if not out.is_file():
                raise RuntimeError("the drive wrote no result")
            return json.loads(out.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    raise RuntimeError("Playwright for Python is not installed here: pip install playwright")


# --- the run --------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="readme_shots")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--data", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--drive", metavar="DAEMON", help=argparse.SUPPRESS)
    parser.add_argument("--out", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--no-build", action="store_true", help="reuse apps/desktop/dist")
    parser.add_argument("--page-port", type=int, default=VITE_PORT, help="the port the page is served on")
    parser.add_argument(
        "--only", nargs="*", default=[], help="take only the shots whose names start so (e.g. 05 17)"
    )
    args = parser.parse_args(argv)
    if args.serve:
        serve(args.data, args.port, args.page_port)
        return 0
    if args.drive:
        seeded = json.loads((args.data / "seeded.json").read_text(encoding="utf-8"))
        args.out.write_text(
            json.dumps(drive(args.drive, args.page_port, seeded, args.only)), encoding="utf-8"
        )
        return 0

    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("pnpm is needed to build and serve the desktop")
    scratch = Path(tempfile.mkdtemp(prefix="readme-shots-"))
    data = scratch / "data"
    data.mkdir()
    port = free_port()
    page_port = args.page_port
    base = f"http://127.0.0.1:{port}"
    result: dict[str, Any] = {"engine": ENGINE, "problems": []}
    vite: subprocess.Popen[Any] | None = None
    daemon: subprocess.Popen[Any] | None = None
    try:
        if not args.no_build:
            print("building the desktop", flush=True)
            subprocess.run([pnpm, "-C", "apps/desktop", "build"], cwd=REPO, check=True, capture_output=True)
        vite = subprocess.Popen(
            [pnpm, "-C", "apps/desktop", "exec", "vite", "preview", "--port", str(page_port), "--strictPort"],
            cwd=REPO,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("META_API_KEY", "ANTHROPIC_API_KEY", "META_BASE_URL", "META_MODEL")
        }
        env.update({"ATHENA_ENGINE": ENGINE, "ATHENA_TOKEN": TOKEN, "ATHENA_TWIN_POLL": "0"})
        daemon = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__)),
                "--serve",
                "--data",
                str(data),
                "--port",
                str(port),
                "--page-port",
                str(page_port),
            ],
            cwd=REPO,
            env=env,
        )
        wait_for(f"{base}/health", 600, daemon)
        wait_for(app_url(page_port), 60)
        status = call(base, "GET", "/engine")
        print(f"daemon on {port}, engine {status['engine']}; the page on {page_port}", flush=True)
        if status["engine"] != ENGINE or not status["simulated"] or status["key"] != "absent":
            raise RuntimeError(f"the daemon runs {status}, not {ENGINE} without a key")
        try:
            import playwright.sync_api  # noqa: F401

            seeded = json.loads((data / "seeded.json").read_text(encoding="utf-8"))
            seen = drive(base, page_port, seeded, args.only)
        except ImportError:
            seen = drive_elsewhere(base, scratch / "drive.json", page_port, data, args.only)
        result.update({k: v for k, v in seen.items() if k != "problems"})
        result["problems"] += seen.get("problems", [])
        rows = call(base, "GET", "/ledger?limit=500")["rows"]
        result["ledger"] = {"calls": len(rows), "engines": sorted({r["engine"] for r in rows})}
    except Exception as e:  # the record says where it stopped and why
        result["problems"].append(f"{type(e).__name__}: {e}"[:600])
    finally:
        end_tree(daemon)
        end_tree(vite)
        for p in (port, page_port):
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", p)) == 0:
                    result["problems"].append(f"something still listens on {p} after the run")
        shutil.rmtree(scratch, ignore_errors=True)
    print(json.dumps(result, indent=1))
    ok = not result["problems"]
    print("SHOTS TAKEN" if ok else "SHOTS TAKEN WITH PROBLEMS", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
