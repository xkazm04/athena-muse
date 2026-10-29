"""The stage's live seam (onboarding v2, WP3-4): the BUILT desktop app against a real daemon, the
staged need walked through the stage in one view - describe, shape (picking her first suggestion and
inking her guesses until agreed), write, check (yes to every card), test run, keep - as far as the
engine allows (the scripted engine cannot write a chore, and says so). Every step is screenshotted;
seam.json records where it got, the score, the ledger, page scroll and console errors, and whether
her window shows the draft's history.

    pnpm -C apps/desktop build
    pnpm -C apps/desktop exec vite preview --port 1420 --strictPort    # the daemon's allowed origin
    SEAM_PORT=8767 python scripts/stage_seam.py drawing claude_code runs/seam-drawing   # or orbit / scripted

It starts its own daemon on SEAM_PORT with a fresh data folder inside <out_dir>, and ends the whole
process tree when it is done. A Claude Code run costs about $0.5-0.8 (measured 2026-10-29, n=3).
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

# Playwright for Python is installed beside the system python, not in the daemon's environment.
from playwright.sync_api import TimeoutError as PWTimeout  # type: ignore[import-not-found]
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
NEED = (
    "Each month I check the after-school club's invoice against the days my kids actually went "
    "(the school portal has attendance) and dispute the extra days."
)
PORT = int(os.environ.get("SEAM_PORT", "8766"))
TOKEN = "seam"
APP = "http://localhost:1420"
MAX_TURNS = 9
BUSY = ", ".join(
    [f'[data-role="notice"][data-phase="{p}"]' for p in ("thinking", "slow", "sending")]
    + ['[data-role="describe"][data-sending="true"]']
)

view, engine, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
data = out / "data"
log: list[str] = []


def note(line: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    log.append(f"{stamp} {line}")
    print(f"{stamp} {line}", flush=True)


def get(path: str) -> Any:
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


env = {**os.environ, "ATHENA_TOKEN": TOKEN, "ATHENA_ENGINE": engine}
daemon = subprocess.Popen(
    ["uv", "run", "athena-daemon", "--data", str(data), "--port", str(PORT)],
    cwd=REPO,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
result: dict[str, Any] = {"view": view, "engine": engine, "reached": "start", "problems": []}
try:
    for _ in range(60):
        try:
            get("/engine")
            break
        except Exception:
            time.sleep(0.5)
    status = get("/engine")
    note(f"daemon up, engine {status}")
    if status["engine"] != engine:
        raise RuntimeError(f"the daemon on {PORT} runs {status['engine']}, not {engine}: a stale one?")
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_init_script(
            "try{localStorage.setItem('athena.firstRun.skipped','1');"
            f"localStorage.setItem('athena.stage.view','{view}')}}catch(e){{}}"
        )
        pg = ctx.new_page()
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        n = 0

        def shot(name: str) -> None:
            global n
            n += 1
            pg.screenshot(path=str(out / f"{n:02d}-{name}.png"))
            scroll = pg.evaluate("[document.documentElement.scrollHeight, innerHeight]")
            if scroll[0] > scroll[1] + 1:
                result["problems"].append(f"page scrolls at {name}: {scroll}")

        def idle(timeout_s: float) -> None:
            """Waits until no reply/work is in flight: the notice is gone or failed."""
            end = time.time() + timeout_s
            while time.time() < end:
                busy = pg.locator(BUSY).count()
                if not busy:
                    return
                pg.wait_for_timeout(500)
            raise PWTimeout("still busy")

        pg.goto(f"{APP}/?daemon=http://127.0.0.1:{PORT}&token={TOKEN}#stage/new")
        pg.wait_for_selector('[data-role="describe"] textarea', timeout=20000)
        shot("describe")
        pg.fill('[data-role="describe"] textarea', NEED)
        pg.click('[data-role="describe"] button[type="submit"]')
        result["reached"] = "describe"
        pg.wait_for_timeout(1500)
        idle(180)
        pg.wait_for_selector(f'[data-stage-view="{view}"]', timeout=30000)
        shot("first-frame")
        draft_id = pg.evaluate("location.hash").split("/")[-1]
        result["draft_id"] = draft_id
        note(f"draft {draft_id}")

        for turn in range(1, MAX_TURNS + 1):
            idle(180)
            failed = pg.locator('[data-role="notice"][data-phase="failed"]').count()
            if failed:
                result["problems"].append(
                    f"turn {turn}: failed notice: {pg.inner_text('[data-role=notice]')[:200]}"
                )
                pg.click('[data-role="retry"]')
                continue
            ink = pg.locator('button:text-matches("Ink (them |all her pencil marks)", "i")')
            if ink.count() and ink.first.is_enabled():
                ink.first.click()
                pg.wait_for_timeout(1200)
            d = get(f"/drafts/{draft_id}")
            pieces = len(d["sketch"]["nodes"])
            note(f"turn {turn}: {pieces} pieces, agreed={d['agreed']}, coverage={d['coverage']}")
            if d["agreed"]:
                break
            sugg = pg.locator('[data-role="suggestion"]')
            if not sugg.count():
                note("no suggestion offered; stopping the shaping")
                break
            sugg.first.click()
            pg.wait_for_timeout(1500)
        result["reached"] = "shape"
        shot("shaped")
        d = get(f"/drafts/{draft_id}")
        result["shape"] = {
            "pieces": len(d["sketch"]["nodes"]),
            "agreed": d["agreed"],
            "views": d.get("views"),
        }

        pg.click('[data-role="exit"]:not([disabled])')
        note("That's enough, write it")
        end = time.time() + 600
        while time.time() < end:
            d = get(f"/drafts/{draft_id}")
            if d["step"] != "author":
                break
            pg.wait_for_timeout(2000)
        pg.wait_for_timeout(1500)
        shot("written-or-not")
        d = get(f"/drafts/{draft_id}")
        note(f"after writing: step={d['step']} chore={d.get('chore_id')}")
        if d["step"] != "preview":
            result["reached"] = "author-failed"
            result["author"] = pg.locator('[data-role="problems"]').all_inner_texts()[:1]
            raise SystemExit(0)
        result["reached"] = "written"
        result["practice"] = [a["name"] for a in d.get("practice", [])]

        show = pg.locator('button:has-text("Show me what she will file")')
        if show.count():
            show.first.click()
        end = time.time() + 300
        while time.time() < end and not get(f"/drafts/{draft_id}").get("expected"):
            pg.wait_for_timeout(2000)
        pg.wait_for_timeout(1500)
        shot("check")
        expected = get(f"/drafts/{draft_id}").get("expected", [])
        note(f"preview: {len(expected)} cards")
        for _ in range(len(expected) + 2):
            yes = pg.locator('[data-role="mark-yes"]:visible')
            target = [i for i in range(yes.count()) if yes.nth(i).get_attribute("aria-pressed") != "true"]
            if not target:
                break
            yes.nth(target[0]).click()
            pg.wait_for_timeout(500)
        shot("marked")
        pg.click('[data-role="run-test"]')
        result["reached"] = "rehearse"
        note("test run started")
        end = time.time() + 900
        while time.time() < end:
            d = get(f"/drafts/{draft_id}")
            if d["step"] == "verdict" or (
                d["step"] == "rehearse" and pg.locator('[data-role="notice"][data-phase="failed"]').count()
            ):
                break
            pg.wait_for_timeout(5000)
        pg.wait_for_timeout(1500)
        shot("verdict")
        d = get(f"/drafts/{draft_id}")
        result["bench"] = d.get("bench")
        note(f"after the run: step={d['step']} bench={json.dumps(d.get('bench'))[:300]}")
        if d["step"] != "verdict":
            raise SystemExit(0)
        result["reached"] = "verdict"
        pg.click('[data-role="keep"]')
        pg.wait_for_selector('[data-role="saved"]', timeout=60000)
        pg.wait_for_timeout(1200)
        shot("saved")
        d = get(f"/drafts/{draft_id}")
        chores = get("/chores")["chores"]
        result["reached"] = d["step"]
        result["kept"] = [c["id"] for c in chores if c.get("origin") == "yours"]

        # Her window: the draft's conversation, live, because the draft is the active space.
        her = ctx.new_page()
        her.set_viewport_size({"width": 400, "height": 620})
        her.goto(f"{APP}/athena.html?daemon=http://127.0.0.1:{PORT}&token={TOKEN}")
        her.wait_for_timeout(3000)
        her.screenshot(path=str(out / "her-window.png"))
        text = her.inner_text("body")
        result["her_window_has_need"] = "after-school club" in text
        result["errors"] = errors[:10]
        b.close()
except SystemExit:
    pass
except Exception as e:  # the record says where it stopped and why
    result["problems"].append(f"{type(e).__name__}: {e}"[:500])
finally:
    try:
        ledger = get("/ledger")
        result["ledger"] = {
            "calls": ledger["totals"]["calls"],
            "cost_usd": ledger["totals"]["cost_usd"],
            "by_surface": {},
        }
        for r in ledger["rows"]:
            k = r["surface"]
            result["ledger"]["by_surface"][k] = result["ledger"]["by_surface"].get(k, 0) + 1
    except Exception as e:
        result["problems"].append(f"ledger: {e}")
    # `uv run` starts the daemon as a child: end the whole tree, or it outlives the run on its port
    subprocess.run(["taskkill", "/PID", str(daemon.pid), "/T", "/F"], capture_output=True)
    result["log"] = log
    (out / "seam.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "log"}, indent=1)[:3000])
