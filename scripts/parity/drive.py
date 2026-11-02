"""One case on one lane: a fresh daemon on the lane's engine, the built main window in Chrome, the
stage walked from describe to saved the way the case says, with the persona answering. Writes
run.json (the schema in report.check_run), transcript.md (blind) and NN-<name>.png into the run's
folder. A time-out or a dead end is the run's `blocker`, with a screenshot; the lane goes on.

Patterns from scripts/stage_seam.py: the init script that skips the first run and picks the view,
the BUSY wait, the ledger read, and ending `uv run`'s whole process tree with taskkill.
"""

from __future__ import annotations

import contextlib
import difflib
import json
import os
import re
import shutil
import socket
import statistics
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from blind import assert_blind, redact
from cases import MAX_TURNS, Case
from persona import PersonaModel, Reply
from playwright.sync_api import Page  # type: ignore[import-not-found]
from playwright.sync_api import TimeoutError as PWTimeout
from report import check_run

REPO = Path(__file__).resolve().parents[2]
TOKEN = "parity"

TURN_S = 180
AUTHOR_S = 600
PREVIEW_S = 300
REHEARSE_S = 900
SAVE_S = 60
OVER_S = 60

BUSY = ", ".join(
    [f'[data-role="notice"][data-phase="{p}"]' for p in ("thinking", "slow", "sending")]
    + ['[data-role="describe"][data-sending="true"]']
)
FAILED = '[data-role="notice"][data-phase="failed"]'
# A failed write, preview or test run: the strip's (or a failed notice's) Try again.
STEP_RETRY = f'[data-role="strip"] [data-role="retry"], {FAILED} [data-role="retry"]'
STEP_WHY = f'[data-role="strip"] .dr-strip__sub, {FAILED} .sp-notice__text'
LINE = '[data-role="note"] .dr-note__line, .ob-line'

# Copied from scripts/twin_fixture.py:79 (SCHEMA.md "Words": never on screen); applied to her lines.
BANNED = re.compile(
    r"\b(token|connector|oauth|api|llm|model|prompt|node|slot|op|fixture|confidence score)s?\b", re.IGNORECASE
)
# The one reply the fault injection serves instead of the daemon's (an engine that did not answer).
FAULT = {"type": "error", "error": "engine_unavailable", "reason": "Injected by the parity runner"}


class Blocked(Exception):
    """The run cannot go on: the message is the run's blocker."""


def port_free(port: int) -> bool:
    """Nothing listens on the port, on IPv4 or IPv6 (vite's "localhost" may be ::1 only)."""
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        with socket.socket(family, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex((host, port)) == 0:
                return False
    return True


def wait_free(port: int, wait_s: float = 30.0) -> bool:
    """The port, once the last case's daemon has let go of it: Windows frees a killed process's socket
    a moment after taskkill returns (measured: six cases of one lane lost to a 1 s gap, run 4)."""
    end = time.monotonic() + wait_s
    while not port_free(port):
        if time.monotonic() > end:
            return False
        time.sleep(0.5)
    return True


def kill_tree(proc: subprocess.Popen[bytes] | None) -> None:
    """`uv run` and `pnpm exec` start children: end the whole tree, or they outlive the run."""
    if proc is not None and proc.poll() is None:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)


def start_vite(port: int, log: Path) -> subprocess.Popen[bytes]:
    if not port_free(port):
        raise RuntimeError(f"port {port} is taken; the lane's app cannot be served there")
    pnpm = shutil.which("pnpm") or "pnpm"
    with log.open("wb") as fh:
        proc = subprocess.Popen(
            [pnpm, "-C", "apps/desktop", "exec", "vite", "preview", "--port", str(port), "--strictPort"],
            cwd=REPO,
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    for _ in range(60):
        if not port_free(port):
            return proc
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    kill_tree(proc)
    raise RuntimeError(f"vite preview did not come up on {port} (see {log.name})")


@dataclass(frozen=True)
class Lane:
    engine: str
    model: str | None  # None: the engine's default, read back from GET /engine
    daemon_port: int
    vite_port: int
    view: str
    persona: bool


class Daemon:
    def __init__(self, lane: Lane, data: Path, log: Path) -> None:
        if not wait_free(lane.daemon_port):
            raise RuntimeError(f"port {lane.daemon_port} is taken; a stale daemon or another program")
        env = {
            **os.environ,
            "ATHENA_ENGINE": lane.engine,
            "ATHENA_TOKEN": TOKEN,
            "ATHENA_EXTRA_ORIGINS": f"http://localhost:{lane.vite_port}",
            "ATHENA_TWIN_POLL": "0",
        }
        env.pop("ATHENA_MODEL", None)
        if lane.model:
            env["ATHENA_MODEL"] = lane.model
        self.port = lane.daemon_port
        self._log = log.open("wb")
        uv = shutil.which("uv") or "uv"
        cmd = [uv, "run", "athena-daemon", "--data", str(data), "--port", str(self.port), "--no-peer"]
        self.proc = subprocess.Popen(cmd, cwd=REPO, env=env, stdout=self._log, stderr=subprocess.STDOUT)

    def get(self, path: str) -> Any:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", headers={"Authorization": f"Bearer {TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)

    def ready(self, engine: str, model: str | None) -> dict[str, Any]:
        for _ in range(120):
            if self.proc.poll() is not None:
                break
            try:
                status: dict[str, Any] = self.get("/engine")
            except Exception:
                time.sleep(0.5)
                continue
            if status.get("engine") != engine or (model and status.get("model") != model):
                raise RuntimeError(
                    f"the daemon runs {status.get('engine')}/{status.get('model')}, not {engine}/{model}"
                )
            return status
        raise RuntimeError("the daemon did not answer GET /engine within 60 s")

    def stop(self) -> None:
        kill_tree(self.proc)
        self._log.close()


def is_pencil(node: dict[str, Any]) -> bool:
    """Her guess not yet agreed (the app's isPencil)."""
    return node.get("origin") == "athena" and not node.get("confirmed")


def site_pencil(node: dict[str, Any]) -> bool:
    """A real website on the piece that is still her guess (ADR 0014)."""
    site = node.get("site")
    return bool(site) and not site.get("confirmed")


def needs_ink(node: dict[str, Any]) -> bool:
    """A piece the person can ink: her pencil, or an agreed piece whose site is still her guess (the
    app's needsInk). "Ink them all" covers only the first kind."""
    return is_pencil(node) or site_pencil(node)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def repeated(asks: list[dict[str, Any]]) -> int:
    """Asks near-identical (ratio >= 0.8) to an earlier one, or the 3rd+ ask on the same slot."""
    n = 0
    per_slot: dict[str, int] = {}
    for i, a in enumerate(asks):
        per_slot[a["slot"]] = per_slot.get(a["slot"], 0) + 1
        same = any(
            difflib.SequenceMatcher(None, _norm(a["text"]), _norm(b["text"])).ratio() >= 0.8 for b in asks[:i]
        )
        if same or per_slot[a["slot"]] >= 3:
            n += 1
    return n


def calls_of(rows: list[dict[str, Any]]) -> dict[str, Any]:
    lat = [int(r.get("latency_ms", 0)) for r in rows]
    costs = [r["cost_usd"] for r in rows if r.get("cost_usd") is not None]
    return {
        "n": len(rows),
        "latency_ms_p50": int(statistics.median(lat)) if lat else None,
        "latency_ms_max": max(lat) if lat else None,
        "over_60s": sum(1 for x in lat if x > OVER_S * 1000),
        "tokens_in": sum(int(r.get("input_tokens") or 0) for r in rows),
        "tokens_out": sum(int(r.get("output_tokens") or 0) for r in rows),
        "cost_usd": round(sum(costs), 4) if costs else None,
        "failed": sum(1 for r in rows if not r.get("ok", True)),
    }


class CaseRun:
    def __init__(self, lane: Lane, case: Case, blind_id: str, out: Path, browser: Any, log: Any) -> None:
        self.lane, self.case, self.blind_id, self.out = lane, case, blind_id, out
        self.browser, self.log = browser, log
        self.t0 = time.time()
        self.shots = 0
        self.transcript: list[str] = []
        self.redacted = 0
        self.turn = 0  # frames seen while shaping
        self.says_ok = 0
        self.say_responses: list[Any] = []
        self.write_responses: list[Any] = []
        self.say_posts = 0
        self.fault_armed = False
        self.fault_fired = False
        self.revised = False
        self.step_retried: set[str] = set()  # author / preview / rehearse: Try again clicked once
        self.persona = PersonaModel(case.persona, enabled=lane.persona and case.answer != "first")
        self.names = tuple(x for x in (lane.engine, lane.model) if x)
        self.rec: dict[str, Any] = {
            "case": case.id,
            "blind_id": blind_id,
            "engine": lane.engine,
            "model": lane.model,
            "end": {"step": None, "expected": case.expected, "ok": False},
            "blocker": None,
            "turns": {"to_agreed": None, "total": 0},
            "asks": [],
            "repeated_asks": 0,
            "repairs": 0,
            "author_failed": False,
            "test": None,
            "calls": calls_of([]),
            "ui": {
                "slow_notices": 0,
                "failures": 0,
                "retries": 0,
                "scroll_problems": [],
                "console_errors": [],
                "banned_words": [],
            },
            "wall_s": 0.0,
            "extra": {
                "name": case.name,
                "draft_id": None,
                "persona_fallback": 0,
                "redacted": 0,
                "revised": False,
                "marks": None,
                "never": None,
                "sites": None,
                "access_step": None,
                "site_on_app": None,
                "site_pencil_left": None,
                "inked": 0,
                "dropped": 0,
                "review_unknown": 0,
                "review_left": 0,
                "drop_noop": [],
                "reviews": [],
                "answered_after_agreed": False,
                "fault_fired": False,
                "http_errors": [],
                "steps": [],
            },
        }

    # --- recording -------------------------------------------------------------------------------

    def elapsed(self) -> float:
        return round(time.time() - self.t0, 1)

    def say(self, text: str) -> None:
        self.transcript.append(text)

    def product(self, text: str) -> str:
        """Text the product or the persona wrote: engine names are redacted and counted."""
        clean, n = redact(text or "", self.names)
        self.redacted += n
        return clean

    def step(self, name: str) -> None:
        self.rec["extra"]["steps"].append({"step": name, "at_s": self.elapsed()})
        self.say(f"\n### [{self.elapsed():.0f} s] step: {name}\n")
        self.log(f"case {self.case.id}: {name}")

    def shot(self, name: str) -> None:
        self.shots += 1
        try:
            self.pg.screenshot(path=str(self.out / f"{self.shots:02d}-{name}.png"))
            scroll = self.pg.evaluate("[document.documentElement.scrollHeight, innerHeight]")
            if scroll[0] > scroll[1] + 1:
                self.rec["ui"]["scroll_problems"].append(f"{name}: page scrolls {scroll[0]} > {scroll[1]}")
        except Exception as e:
            self.log(f"screenshot {name} failed: {e}")

    # --- the daemon and the page -----------------------------------------------------------------

    def draft(self) -> dict[str, Any]:
        return self.d.get(f"/drafts/{self.draft_id}")  # type: ignore[no-any-return]

    def idle(self, timeout_s: float) -> None:
        """Until no reply or work is in flight; a slow notice seen on the way is counted once."""
        end = time.time() + timeout_s
        slow = False
        while time.time() < end:
            if self.pg.locator('[data-role="notice"][data-phase="slow"]').count():
                slow = True
            if not self.pg.locator(BUSY).count():
                if slow:
                    self.rec["ui"]["slow_notices"] += 1
                return
            self.pg.wait_for_timeout(500)
        raise PWTimeout("still busy")

    def drain(self) -> list[dict[str, Any]]:
        """The /say replies that came back since the last look: each one ok or failed."""
        events: list[dict[str, Any]] = []
        while self.say_responses:
            resp = self.say_responses.pop(0)
            try:
                body = resp.text()
            except Exception:
                body = ""
            lines = [json.loads(x) for x in body.splitlines() if x.strip().startswith("{")]
            failed = resp.status >= 400 or any(e.get("type") == "error" for e in lines)
            if not failed:
                self.says_ok += 1
            events.extend(lines)
        return events

    def her_line(self) -> str:
        loc = self.pg.locator(LINE)
        text = loc.first.inner_text().strip() if loc.count() else ""
        for m in BANNED.finditer(text):
            word = m.group(0).lower()
            if word not in self.rec["ui"]["banned_words"]:
                self.rec["ui"]["banned_words"].append(word)
        return text

    def click(self, selector: str, timeout_ms: int = 10000) -> None:
        self.pg.locator(selector).first.click(timeout=timeout_ms)

    def retry_failed(self, where: str) -> bool:
        """A failed notice on screen: count it, click Try again. False when there was none."""
        if not self.pg.locator(FAILED).count():
            return False
        why = " ".join(self.pg.locator(f"{FAILED} .sp-notice__text").first.inner_text().split())[:200]
        self.rec["ui"]["failures"] += 1
        self.say(f"- ({where}) Her reply failed: {self.product(why)!r}; Try again.")
        self.shot(f"failed-{where}")
        self.click('[data-role="retry"]')
        self.rec["ui"]["retries"] += 1
        self.pg.wait_for_timeout(1500)
        return True

    def retry_step(self, where: str) -> bool:
        """A failed write, preview or test run on screen: the person clicks Try again once (counted in
        ui.failures and ui.retries); the same step failing again is the blocker. False when none."""
        button = self.pg.locator(STEP_RETRY)
        if not button.count():
            return False
        why_loc = self.pg.locator(STEP_WHY)
        why = " ".join(why_loc.first.inner_text().split())[:200] if why_loc.count() else ""
        self.rec["ui"]["failures"] += 1
        self.shot(f"failed-{where}")
        if where in self.step_retried:
            raise Blocked(f"{where} failed again after Try again: {why}")
        self.say(f"- ({where}) It failed: {self.product(why)!r}; Try again.")
        button.first.click()
        self.step_retried.add(where)
        self.rec["ui"]["retries"] += 1
        self.pg.wait_for_timeout(2000)
        return True

    # --- the fault ---------------------------------------------------------------------------------

    def _fault(self, route: Any) -> None:
        if route.request.method != "POST" or self.fault_fired:
            route.continue_()
            return
        self.fault_fired = True
        route.fulfill(
            status=200,
            headers={
                "content-type": "application/x-ndjson",
                "access-control-allow-origin": f"http://localhost:{self.lane.vite_port}",
            },
            body=json.dumps(FAULT) + "\n",
        )

    def arm_fault(self) -> None:
        self.pg.route("**/drafts/*/say", self._fault)
        self.fault_armed = True

    def disarm_fault(self) -> None:
        if self.fault_armed and self.fault_fired:
            self.pg.unroute("**/drafts/*/say", self._fault)
            self.fault_armed = False
            self.rec["extra"]["fault_fired"] = True

    # --- the walk ------------------------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        self.out.mkdir(parents=True, exist_ok=True)
        c = self.case
        self.say(f"# Case {c.id} - {c.name} ({self.blind_id})\n")
        self.say(f"**Grading focus:** {c.focus}\n")
        self.say(f"**Persona:** {c.persona.who}\n\n**Persona's truth:** {c.persona.truth}\n")
        self.say(f"**How they talk:** {c.persona.style}\n\n**Need typed:** {c.need}\n")
        self.d = Daemon(self.lane, self.out / "data", self.out / "daemon.log")
        ctx = None
        try:
            status = self.d.ready(self.lane.engine, self.lane.model)
            self.rec["model"] = status.get("model")
            self.names = tuple(x for x in (self.lane.engine, self.rec["model"]) if x)
            ctx = self.browser.new_context(viewport={"width": 1280, "height": 800})
            ctx.add_init_script(
                "try{localStorage.setItem('athena.firstRun.skipped','1');"
                f"localStorage.setItem('athena.stage.view','{self.lane.view}')}}catch(e){{}}"
            )
            self.pg: Page = ctx.new_page()
            errors = self.rec["ui"]["console_errors"]
            self.pg.on("pageerror", lambda e: errors.append(str(e)[:300]))
            self.pg.on("console", lambda m: errors.append(m.text[:300]) if _counts(m) else None)
            self.pg.on("response", self._on_response)
            self.walk()
        except Blocked as e:
            self.block(str(e))
        except PWTimeout as e:
            self.block(f"time-out: {str(e).splitlines()[0][:200]}")
        except Exception as e:
            self.block(f"{type(e).__name__}: {str(e).splitlines()[0][:300] if str(e) else ''}")
        finally:
            self.finish()
            if ctx is not None:
                ctx.close()
            self.d.stop()
        return self.rec

    def _on_response(self, resp: Any) -> None:
        if resp.status >= 400:  # names what the console's bare "Failed to load resource" was
            path = re.sub(r"^https?://[^/]+", "", resp.url)[:160]
            self.rec["extra"]["http_errors"].append(f"{resp.status} {resp.request.method} {path}")
        if resp.request.method != "POST":
            return
        if re.search(r"/drafts/[^/]+/say$", resp.url):
            self.say_responses.append(resp)
        elif re.search(r"/drafts/[^/]+/write$", resp.url):
            self.write_responses.append(resp)

    def block(self, why: str) -> None:
        if self.rec["blocker"] is None:
            self.rec["blocker"] = why
        self.log(f"case {self.case.id}: BLOCKED {why}")
        self.say(f"\n**Stopped:** {self.product(why)}\n")
        if hasattr(self, "pg"):
            self.shot("blocked")

    def walk(self) -> None:
        lane = self.lane
        app = f"http://localhost:{lane.vite_port}"
        self.pg.goto(f"{app}/?daemon=http://127.0.0.1:{lane.daemon_port}&token={TOKEN}#stage/new")
        self.pg.wait_for_selector('[data-role="describe"] textarea', timeout=20000)
        self.step("describe")
        self.shot("describe")
        self.pg.fill('[data-role="describe"] textarea', self.case.need)
        self.click('[data-role="describe"] button[type="submit"]')
        self.pg.wait_for_timeout(1500)
        self.idle(TURN_S)
        self.pg.wait_for_selector(f'[data-stage-view="{lane.view}"]', timeout=30000)
        self.draft_id = self.pg.evaluate("location.hash").split("/")[-1]
        self.rec["extra"]["draft_id"] = self.draft_id
        self.shot("first-frame")
        self.step("shape")
        for _ in range(2):  # a second round only after "Not quite"
            self.shape()
            self.write()
            self.preview()
            self.rehearse()
            if self.case.revise_once and not self.revised:
                self.revise()
                continue
            self.keep()
            return

    def frame(self) -> dict[str, Any]:
        """Records the frame on screen: her line, the ask, the sketch."""
        d = self.draft()
        self.turn += 1
        line = self.her_line()
        self.say(f"\n#### Turn {self.turn} [{self.elapsed():.0f} s]\n")
        self.say(f"- **Athena:** {self.product(line)}")
        ask = d.get("ask")
        if ask and self.pg.locator('[data-role="question"]').count():
            self.rec["asks"].append(
                {"slot": ask["slot"], "text": ask["text"], "suggestions": ask["suggestions"]}
            )
            self.say(f"- **Asks** (about {ask['slot']}): {self.product(ask['text'])}")
            for i, s in enumerate(ask["suggestions"], 1):
                self.say(f"  {i}. {self.product(s)}")
        self.say("- **Sketch:** " + self.sketch_line(d))
        return d

    def sketch_line(self, d: dict[str, Any]) -> str:
        parts = []
        for n in d["sketch"]["nodes"]:
            state = "ink" if n.get("confirmed") else "pencil"
            site = ""
            if n.get("site"):
                site = f" <{n['site']['origin']}{'' if n['site'].get('confirmed') else ', pencil'}>"
            parts.append(f"[{n['slot']}/{state}] {self.product(n['label'])}{site}")
        return "; ".join(parts) or "(empty)"

    def pencil(self, d: dict[str, Any]) -> list[dict[str, Any]]:
        """What "Ink them all" covers: her pencil pieces (not a pencil site on an agreed piece)."""
        return [n for n in d["sketch"]["nodes"] if is_pencil(n)]

    def agreed_now(self) -> bool:
        d = self.draft()
        if d.get("agreed") and self.rec["turns"]["to_agreed"] is None:
            self.rec["turns"]["to_agreed"] = self.says_ok
        return bool(d.get("agreed"))

    def shape(self) -> None:
        c = self.case
        failures_in_row = 0
        start = self.turn
        after_agreed = False  # the one extra answer to a question still open at agreed was given
        for _ in range(MAX_TURNS + 4):
            self.idle(TURN_S)
            self.drain()
            self.disarm_fault()
            if self.retry_failed(f"turn{self.turn + 1}"):
                failures_in_row += 1
                if failures_in_row >= 3:
                    raise Blocked("her reply failed three times in a row")
                continue
            failures_in_row = 0
            d = self.frame()
            if c.exit == "first_frame":
                self.say("- **Person:** (clicks the exit at once)")
                break
            if c.ink_all:
                if self.pencil(self.draft()):
                    ink = self.pg.locator('[data-role="ink-all"]')
                    if ink.count() and ink.first.is_enabled():
                        ink.first.click()
                        self.say("- **Person:** inks all her pencil marks")
                        self.pg.wait_for_timeout(1200)
                        self.idle(TURN_S)
            else:
                self.review()
            if after_agreed:
                self.say("- (leaves after answering the open question)")
                break
            if self.agreed_now():
                self.say("- (agreed)")
                if c.exit == "agreed":
                    d = self.draft()
                    if not (d.get("ask") and self.pg.locator('[data-role="question"]').count()):
                        break
                    # R2: a question still on screen is answered once, as any turn, before leaving
                    self.say("- (a question is still open: the person answers it before leaving)")
                    after_agreed = True
                    self.rec["extra"]["answered_after_agreed"] = True
                    self.answer(d)
                    self.pg.wait_for_timeout(1500)
                    continue
            if self.turn - start >= MAX_TURNS:
                self.say("- (turn cap reached)")
                break
            if not self.pg.locator('[data-role="question"]').count() or not d.get("ask"):
                self.say("- (no question open)")
                break
            self.answer(d)
            self.pg.wait_for_timeout(1500)
        self.shot(f"shaped-{self.turn}")
        d = self.draft()
        self.say(f"\n- **Sketch at exit:** {self.sketch_line(d)}")
        self.click('[data-role="exit"]:not([disabled])')
        self.say("- **Person:** That's enough, write it.")

    def answer(self, d: dict[str, Any]) -> None:
        c = self.case
        ask = d["ask"]
        sugg = list(ask["suggestions"])
        labels = [n["label"] for n in d["sketch"]["nodes"]]
        say_no = self.says_ok + 1  # this answer is the next /say (the describe's was the first)
        if c.fault_on_turn == say_no and not self.fault_fired:
            self.arm_fault()
            self.say("- (an engine failure is injected on this reply)")
        if c.answer == "first":
            reply = Reply(pick=1)
        else:
            reply = self.persona.answer(
                self.her_line(),
                ask["text"],
                sugg,
                labels,
                mode=c.answer,
                contradict=c.contradict_on_turn == self.turn,
            )
        self.rec["extra"]["persona_fallback"] = self.persona.fallbacks
        if reply.pick and 1 <= reply.pick <= self.pg.locator('[data-role="suggestion"]').count():
            text = sugg[reply.pick - 1] if reply.pick <= len(sugg) else f"#{reply.pick}"
            self.say(
                f"- **Person** picks {reply.pick}: {self.product(text)}"
                + (" (fallback)" if reply.fallback else "")
            )
            self.pg.locator('[data-role="suggestion"]').nth(reply.pick - 1).click()
        else:
            words = reply.words or "Yes, that is right."
            self.say(f"- **Person** says: {self.product(words)}" + (" (fallback)" if reply.fallback else ""))
            self.pg.fill('[data-role="composer"] input', words)
            self.pg.press('[data-role="composer"] input', "Enter")

    def review(self) -> None:
        """R1: the persona reviews each pencil mark (a pencil piece, or a pencil site on an agreed
        piece) against its truth; each is inked or rubbed out through its own card."""
        d = self.draft()
        marks = [n for n in d["sketch"]["nodes"] if needs_ink(n)]
        if not marks:
            return
        items = [
            {"label": n["label"], "slot": n["slot"], "site": n["site"]["origin"] if site_pencil(n) else None}
            for n in marks
        ]
        r = self.persona.review(items)
        x = self.rec["extra"]
        x["persona_fallback"] = self.persona.fallbacks
        x["review_unknown"] += r.unknown
        inked: list[str] = []
        dropped: list[str] = []
        noop: list[str] = []
        for label in r.ink:
            for n in (m for m in marks if m["label"] == label):
                if self.act(n, "ink"):
                    inked.append(label + (f" <{n['site']['origin']}>" if site_pencil(n) else ""))
        dropping: list[str] = []
        for label in r.drop:
            for n in (m for m in marks if m["label"] == label):
                if not is_pencil(n):  # an agreed piece with her pencil site: the card's rub-out does nothing
                    noop.append(f"{label} <{n['site']['origin']}>")
                elif self.act(n, "drop"):
                    dropping.append(n["id"])
                    dropped.append(label)
        end = time.time() + 20  # a rub-out waits out its five-second undo, then goes to the daemon
        while dropping and time.time() < end:
            ids = {n["id"] for n in self.draft()["sketch"]["nodes"]}
            if not ids & set(dropping):
                break
            self.pg.wait_for_timeout(1000)
        else:
            if dropping:
                self.say("- (a rub-out did not reach the sketch within 20 s)")
        left = [
            lb for lb in dict.fromkeys(it["label"] for it in items) if lb not in r.ink and lb not in r.drop
        ]
        x["inked"] += len(inked)
        x["dropped"] += len(dropped)
        x["review_left"] += len(left)
        x["drop_noop"] += noop
        x["reviews"].append(
            {
                "turn": self.turn,
                "marks": len(items),
                "inked": len(inked),
                "dropped": len(dropped),
                "left": len(left),
                "unknown": r.unknown,
                "fallback": r.fallback,
            }
        )
        line = "- **Person** reviews her pencil marks: inks: " + (
            ", ".join(self.product(t) for t in inked) or "none"
        )
        line += "; rubs out: " + (", ".join(self.product(t) for t in dropped) or "none")
        if left:
            line += "; leaves in pencil: " + ", ".join(self.product(t) for t in left)
        if noop:
            line += "; could not rub out (a site on an agreed piece): " + ", ".join(
                self.product(t) for t in noop
            )
        if r.unknown:
            line += f"; {r.unknown} label(s) not among her pencil marks ignored"
        self.say(line + (" (fallback)" if r.fallback else ""))
        if dropped or inked:
            self.pg.wait_for_timeout(500)

    def act(self, node: dict[str, Any], role: str) -> bool:
        """Opens the piece's card and clicks its ink or rub-out; an ink waits until the daemon has it."""
        nid = node["id"]
        card = f'[data-role="piece-card"][data-node-id="{nid}"]'
        try:
            if not self.pg.locator(card).count():
                self.click(f'[data-node-id="{nid}"]:is([data-role="piece"], [data-role="chip"]) button', 5000)
            self.click(f'{card} [data-role="{role}"]', 5000)
        except PWTimeout:
            self.say(f"- (could not open the card of {self.product(node['label'])!r} to {role} it)")
            return False
        if role == "ink":
            end = time.time() + 15
            while time.time() < end:
                now = next((n for n in self.draft()["sketch"]["nodes"] if n["id"] == nid), None)
                if now is None or not needs_ink(now):
                    break
                self.pg.wait_for_timeout(500)
        else:
            self.pg.wait_for_timeout(300)
        return True

    def write(self) -> None:
        self.step("author")
        end = time.time() + 15
        while time.time() < end and self.draft()["step"] == "shape" and not self.write_responses:
            self.pg.wait_for_timeout(500)
        end = time.time() + AUTHOR_S
        while time.time() < end:
            if self.draft()["step"] != "author" and not self.pg.locator(BUSY).count():
                break
            if not self.pg.locator(BUSY).count() and self.retry_step("author"):
                # the failed attempt's repairs count; its failure is judged by the retry's outcome
                self.rec["repairs"] += sum(1 for e in self.write_events() if e.get("type") == "repair")
                continue
            self.pg.wait_for_timeout(2000)
        else:
            raise Blocked("authoring did not end within 600 s")
        self.pg.wait_for_timeout(1500)
        events = self.write_events()
        self.rec["repairs"] += sum(1 for e in events if e.get("type") == "repair")
        failed = [e for e in events if e.get("type") in ("author_failed", "error")]
        self.shot("written-or-not")
        d = self.draft()
        if failed or d["step"] != "preview":
            self.rec["author_failed"] = any(e.get("type") == "author_failed" for e in failed)
            probs = [p for e in failed for p in e.get("problems", [])] or [
                str(e.get("reason", "")) for e in failed
            ]
            self.say("- **Writing failed:** " + self.product(" | ".join(probs)[:500]))
            kind = "author_failed" if self.rec["author_failed"] else f"author ended at {d['step']}"
            raise Blocked(f"{kind}: {' | '.join(probs)[:300]}")
        self.say(
            "- **Written.** Practice apps: "
            + ", ".join(self.product(a["name"]) for a in d.get("practice", []))
        )

    def write_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        while self.write_responses:
            resp = self.write_responses.pop(0)
            with contextlib.suppress(Exception):
                events += [json.loads(x) for x in resp.text().splitlines() if x.strip().startswith("{")]
        return events

    def preview(self) -> None:
        self.step("preview")
        show = self.pg.locator('button:has-text("Show me what she will file")')
        if show.count():
            show.first.click()
        end = time.time() + PREVIEW_S
        while time.time() < end and not self.draft().get("expected"):
            if self.retry_step("preview"):
                end = time.time() + PREVIEW_S  # the retry gets its own time
                continue
            self.pg.wait_for_timeout(2000)
        cards = self.draft().get("expected") or []
        if not cards:
            raise Blocked("the preview listed no cards within 300 s")
        self.pg.wait_for_timeout(1500)
        self.shot("check")
        self.say("- **Cards she expects to file:**")
        for card in cards:
            self.say(f"  - {self.product(card['label'])} - {self.product(card.get('why', ''))}")
        if self.case.marks == "yes":
            marks = {str(cd["id"]): "yes" for cd in cards}
            never = None
        else:
            r = self.persona.mark(cards, self.case.never_line)
            self.rec["extra"]["persona_fallback"] = self.persona.fallbacks
            marks, never = r.marks, r.never if self.case.never_line else None
        for cid, mark in marks.items():
            role = "mark-yes" if mark == "yes" else "mark-no"
            self.click(f'[data-role="check-card"][data-expected-id="{cid}"] [data-role="{role}"]')
            self.pg.wait_for_timeout(300)
        self.say("- **Person marks:** " + ", ".join(f"{cid}={m}" for cid, m in marks.items()))
        self.rec["extra"]["marks"] = marks
        if never:
            field = self.pg.locator('[data-role="never-line"] input')
            field.first.fill(never)
            field.first.press("Enter")
            self.say(f"- **Person adds** she must never: {self.product(never)}")
            self.rec["extra"]["never"] = never
            self.pg.wait_for_timeout(500)
        self.shot("marked")

    def rehearse(self) -> None:
        self.step("rehearse")
        self.click('[data-role="run-test"]:not([disabled])')
        end = time.time() + REHEARSE_S
        while time.time() < end:
            d = self.draft()
            if d["step"] == "verdict":
                break
            if self.retry_step("rehearse"):
                end = time.time() + REHEARSE_S
                continue
            self.pg.wait_for_timeout(5000)
        else:
            raise Blocked("the test run did not end within 900 s")
        self.pg.wait_for_timeout(1500)
        self.shot("verdict")
        bench = self.draft().get("bench") or {}
        self.rec["test"] = {
            "found": bench.get("found"),
            "of": bench.get("eligible"),
            "verdict": bench.get("verdict"),
        }
        score = self.pg.locator('[data-role="score"]')
        self.say(f"- **Test run:** {bench.get('found')} of {bench.get('eligible')} ({bench.get('verdict')})")
        if score.count():
            self.say(f"- **Score on screen:** {self.product(' '.join(score.first.inner_text().split()))}")

    def revise(self) -> None:
        self.step("verdict: not quite")
        d = self.draft()
        cards = [x["label"] for x in d.get("expected") or []]
        r = self.persona.gap([n["label"] for n in d["sketch"]["nodes"]], cards)
        self.rec["extra"]["persona_fallback"] = self.persona.fallbacks
        note = r.note or "Something is missing."
        acts = '[data-role="verdict-actions"]'
        self.click(f'{acts} [data-role="revise"]')
        self.pg.fill(f"{acts} input", note)
        self.click(f'{acts} [data-role="revise"]')
        self.say(f"- **Person:** Not quite - {self.product(note)}")
        end = time.time() + 60
        while time.time() < end and self.draft()["step"] != "shape":
            self.pg.wait_for_timeout(1000)
        if self.draft()["step"] != "shape":
            raise Blocked("'Not quite' did not return to the sketch")
        self.pg.wait_for_timeout(1500)
        banner = self.pg.locator('[data-role="revisit"]').count() > 0
        self.say(f"- Back at the sketch (banner shown: {banner}).")
        self.shot("revisit")
        self.revised = True
        self.rec["extra"]["revised"] = True
        self.step("shape (again)")

    def keep(self) -> None:
        self.step("keep")
        self.click('[data-role="keep"]')
        end = time.time() + SAVE_S
        while time.time() < end and self.draft()["step"] not in ("access", "saved"):
            self.pg.wait_for_timeout(1000)
        d = self.draft()
        sites = d.get("sites") or []
        self.rec["extra"]["sites"] = [{"origin": s.get("origin"), "state": s.get("state")} for s in sites]
        self.rec["extra"]["access_step"] = d["step"] == "access"
        if d["step"] == "access":
            self.step("access")
            self.say(
                "- **Sign in to:** " + (", ".join(self.product(s.get("origin", "")) for s in sites) or "none")
            )
            self.shot("access")
            for _ in range(len(sites) + 2):
                skip = self.pg.locator(
                    '[data-role="access-site"][data-state="open"] [data-role="access-skip"]'
                )
                if not skip.count():
                    break
                skip.first.click()
                self.say("- **Person** skips signing in to a site.")
                self.pg.wait_for_timeout(1500)
        self.pg.wait_for_selector('[data-role="saved"]', timeout=SAVE_S * 1000)
        self.pg.wait_for_timeout(1200)
        self.step("saved")
        self.shot("saved")
        d = self.draft()
        self.rec["extra"]["sites"] = [
            {"origin": s.get("origin"), "state": s.get("state")} for s in d.get("sites") or []
        ]
        mine = [ch for ch in self.d.get("/chores")["chores"] if ch.get("origin") == "yours"]
        for ch in mine:
            self.say(
                f"- **Kept chore:** {self.product(ch.get('title', ''))}"
                f" - {self.product(ch.get('promise', ''))}"
            )

    def finish(self) -> None:
        rec = self.rec
        try:
            if getattr(self, "draft_id", None):
                self.drain()
                d = self.draft()
                rec["end"]["step"] = d["step"]
                apps = [n for n in d["sketch"]["nodes"] if n.get("kind") == "app"]
                rec["extra"]["site_on_app"] = any(n.get("site") for n in apps)
                rec["extra"]["site_pencil_left"] = sum(1 for n in apps if site_pencil(n))
                rows = self.d.get("/ledger?limit=500")["rows"]
                rec["calls"] = calls_of(rows)
        except Exception as e:
            self.log(f"case {self.case.id}: finish read failed: {e}")
        rec["turns"]["total"] = self.says_ok
        rec["repeated_asks"] = repeated(rec["asks"])
        rec["end"]["ok"] = rec["end"]["step"] == rec["end"]["expected"] and rec["blocker"] is None
        rec["wall_s"] = self.elapsed()
        rec["extra"]["redacted"] = self.redacted
        rec["extra"]["persona_fallback"] = self.persona.fallbacks
        rec["ui"]["console_errors"] = rec["ui"]["console_errors"][:20]
        end = rec["end"]
        self.say(f"\n### End [{self.elapsed():.0f} s]: step {end['step']}, expected {end['expected']}")
        (self.out / "run.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
        problems = check_run(rec)
        if problems:
            raise AssertionError(f"run.json breaks the schema: {problems}")
        text = "\n".join(self.transcript) + "\n"
        # Fails loudly and writes no transcript.md: a leaked name must never reach the grader.
        assert_blind(text, f"case {self.case.id} ({self.blind_id}) transcript", self.names)
        (self.out / "transcript.md").write_text(text, encoding="utf-8")


def _counts(message: Any) -> bool:
    """A console error that counts. The browser's bare "Failed to load resource" 404 (the favicon) is not
    the app's: any real failed request is named in extra.http_errors by the response hook."""
    text = str(message.text)
    return message.type == "error" and not (text.startswith("Failed to load resource") and "404" in text)
