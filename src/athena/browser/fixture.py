"""Local test pages for her browser (simulated; not YouTube, not a mailbox, not a studio).

They reproduce the hard parts of the business channel's acceptance without the owner's accounts:

- `/channel`: a creator's channel page with three tracks (read).
- `/watch?v=<id>`: a track with a comment form; a posted comment lands in the journal (sign once).
- `/downloads`: a link to a short WAV and to a draft MP4 of N MB (deterministic bytes).
- `/studio`: an "Upload videos" button opening a same-origin iframe whose upload dialog is a custom
  element with an open shadow root holding a hidden file input, a title field and the visibility
  choice (Private / Unlisted / Public). The page hashes the file it was given (SHA-256) and posts the
  digest to the journal, so a test knows the bytes arrived whole.
- `/captcha`: a "verify you are human" step that only a person passes (the wheel's test).
- `/account`: a members' page (ADR 0014's look). Without a valid mark in the browser it redirects to
  `/signin?next=/account`, a page with a password field; `POST /signin` sets the mark (a random value
  the server remembers) and returns to `next`. `/account?away=1` sends a visitor who is not signed in
  to the sign-in page on another host (`localhost` instead of `127.0.0.1`).
- `/channel/<handle>/videos` (also `/@<handle>/videos`): a creator's uploads with their dates, for
  the two creators in `CREATORS`. `POST /fixture/new-upload` adds one more upload to the first
  creator's page, so a seam can make "a new track" happen.
- `/mail`: a Proton-like inbox (thread rows: subject, sender address, snippet, time). `/mail/<id>`:
  a thread with its messages, a reply box labelled "Reply" and a "Send" button posting to
  `/mail/<id>/reply` (journal `sent`). `/mail/new`: compose (To, Subject, body, Send; journal
  `sent`). `/mail?locked=1` is the inbox behind the sign-in below. `POST /fixture/new-reply?thread=<id>`
  adds a new message from the thread's creator, now.
- `/studio/analytics`: the channel's numbers (Views, Subscribers, Watch time (hours)) under a
  "last updated" date the page claims (a reader must keep its own read time instead).
- `/expire`: forgets every mark, so the next visit to `/account` asks to sign in again (a lapse).
- `/state`: the journal as JSON (comments, uploads, saves, downloads, sign-ins, lapses, sent mail,
  new uploads, the mailbox's threads).

Every page says on screen that it is a simulated test page.

    uv run python -m athena.browser.fixture --port 8781
"""

from __future__ import annotations

import argparse
import html
import io
import json
import random
import secrets
import struct
import threading
import wave
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

BANNER = (
    '<p style="background:#fde68a;padding:6px 10px;font:14px sans-serif;margin:0 0 12px">'
    "Simulated test page - not a real site (Athena fixture, no real account)</p>"
)
TRACKS = (
    ("t1", "Night Drive in Glass", "3:12"),
    ("t2", "Paper Lanterns (Suno v5)", "2:58"),
    ("t3", "Low Tide Choir", "4:05"),
)
MB_MAX = 200
MARK = "athena_fixture_member"

# --- the business routines' pages (business Phase 2) ---------------------------------------------
# A seed that wants the inbox to match these senders keeps each creator with its address in `emails`.

#: (handle, name, business email): the creators whose videos pages and mail the fixture serves.
CREATORS = (
    ("lumen-tide-sim", "Lumen Tide (simulated)", "lumen.tide@creators.example"),
    ("paper-orbit-sim", "Paper Orbit (simulated)", "paper.orbit@creators.example"),
)
#: The channel's own mailbox address (the sender of what it sends) and a sender who is no creator.
CHANNEL_EMAIL = "channel@business.example"
STRANGER_EMAIL = "promo@growfast.example"
#: handle -> uploads (video id, title, published date), newest first.
UPLOADS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "lumen-tide-sim": (
        ("lt2", "Glass Harbour (simulated)", "2026-10-28"),
        ("lt1", "Night Ferry (simulated)", "2026-10-20"),
    ),
    "paper-orbit-sim": (
        ("po2", "Quiet Arcade (simulated)", "2026-10-30"),
        ("po1", "Neon Pantry (simulated)", "2026-10-15"),
    ),
}
#: The upload `POST /fixture/new-upload` adds to the first creator's page (newest).
NEW_UPLOAD = ("lt3", "Harbour Lights (simulated)", "2026-11-01")
#: The mailbox: thread id -> sender, subject and messages [sender, ISO time, text], oldest first.
THREADS: dict[str, dict[str, Any]] = {
    "m1": {
        "from": CREATORS[0][2],
        "subject": "Re: Licensing Night Ferry (simulated)",
        "messages": [
            [CHANNEL_EMAIL, "2026-10-30T10:00:00Z", "Hi, we love Night Ferry. May we make a video of it?"],
            [CREATORS[0][2], "2026-11-01T09:12:00Z", "Hi! Happy to talk. Which plan do you need it on?"],
        ],
    },
    "m2": {
        "from": CREATORS[1][2],
        "subject": "Re: Neon Pantry video (simulated)",
        "messages": [
            [CHANNEL_EMAIL, "2026-10-29T15:30:00Z", "Hello, could we feature Neon Pantry on our channel?"],
            [CREATORS[1][2], "2026-10-31T18:05:00Z", "Sure, I am on the pro plan. Send me the terms."],
        ],
    },
    "m3": {
        "from": STRANGER_EMAIL,
        "subject": "Grow your channel 10x overnight",
        "messages": [[STRANGER_EMAIL, "2026-11-01T07:40:00Z", "Buy views now, limited offer."]],
    },
}
#: The numbers the analytics page shows, and the date it claims (never a reading's time).
ANALYTICS = (("Views", "12,480"), ("Subscribers", "1,204"), ("Watch time (hours)", "389.5"))
ANALYTICS_CLAIMED = "2026-10-15"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _shown(at: str) -> str:
    """A message time as a mailbox shows it: 1 Nov 2026, 09:12 UTC."""
    moment = datetime.fromisoformat(at)
    return f"{moment.day} {moment.strftime('%b %Y, %H:%M')} UTC"


def _page(title: str, body: str) -> bytes:
    doc = (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>'
        "<style>body{font:15px sans-serif;margin:16px;max-width:900px}</style></head>"
        f"<body>{BANNER}{body}</body></html>"
    )
    return doc.encode("utf-8")


def wav_bytes() -> bytes:
    """One second of a quiet 440 Hz tone, 8 kHz mono: a small real audio file."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        frames = b"".join(
            struct.pack("<h", 2000 * (1 if (i * 440 * 2 // 8000) % 2 else -1)) for i in range(8000)
        )
        w.writeframes(frames)
    return buf.getvalue()


def draft_bytes(mb: int) -> bytes:
    """`mb` MiB of seeded bytes: the same every time, so a test can know its digest."""
    return random.Random(f"athena-draft-{mb}").randbytes(mb * 1024 * 1024)


STUDIO_DIALOG = """
<h2>Upload videos (dialog frame)</h2>
<upload-dialog></upload-dialog>
<script>
class UploadDialog extends HTMLElement {
  constructor() {
    super();
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <div>
        <input id="file" type="file" accept="video/*" style="display:none">
        <button id="pick" type="button">Select files</button>
        <p id="status">No file selected</p>
        <label>Title <input id="title" type="text" aria-label="Title (required)"></label>
        <fieldset><legend>Visibility</legend>
          <label><input type="radio" name="vis" value="private" checked> Private</label>
          <label><input type="radio" name="vis" value="unlisted"> Unlisted</label>
          <label><input type="radio" name="vis" value="public"> Public</label>
        </fieldset>
        <button id="save" type="button">Save draft</button>
        <p id="saved"></p>
      </div>`;
    const file = root.getElementById("file");
    root.getElementById("pick").addEventListener("click", () => file.click());
    file.addEventListener("change", async () => {
      const f = file.files[0];
      if (!f) return;
      root.getElementById("status").textContent = "Reading " + f.name + "...";
      const digest = await crypto.subtle.digest("SHA-256", await f.arrayBuffer());
      const hex = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
      await fetch("/uploaded", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: f.name, size: f.size, type: f.type, sha256: hex }) });
      root.getElementById("status").textContent =
        "Uploaded " + f.name + " (" + f.size + " bytes, sha256 " + hex.slice(0, 12) + ")";
    });
    root.getElementById("save").addEventListener("click", async () => {
      const vis = root.querySelector("input[name=vis]:checked").value;
      const title = root.getElementById("title").value;
      await fetch("/studio/save", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, visibility: vis }) });
      root.getElementById("saved").textContent = "Draft saved as " + vis;
    });
  }
}
customElements.define("upload-dialog", UploadDialog);
</script>
"""

STUDIO = """
<h1>Channel content (simulated studio)</h1>
<button id="open" type="button">Upload videos</button>
<div id="dialog"></div>
<script>
document.getElementById("open").addEventListener("click", () => {
  const frame = document.createElement("iframe");
  frame.src = "/studio/dialog";
  frame.title = "Upload dialog";
  frame.style = "width:100%;height:420px;border:1px solid #999";
  document.getElementById("dialog").replaceChildren(frame);
});
</script>
"""


class Journal:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.state: dict[str, Any] = {
            "comments": [],
            "uploads": [],
            "saves": [],
            "downloads": 0,
            "verified": 0,
            "marks": [],
            "signins": 0,
            "expired": 0,
            "sent": [],
            "new_uploads": 0,
            "threads": json.loads(json.dumps(THREADS)),
        }

    def add(self, key: str, item: Any) -> None:
        with self.lock:
            self.state[key].append(item)

    def bump(self, key: str) -> None:
        with self.lock:
            self.state[key] += 1

    def uploads(self, handle: str) -> list[tuple[str, str, str]]:
        """A creator's uploads now, newest first (with the new one once it was made to appear)."""
        with self.lock:
            fresh = self.state["new_uploads"] > 0 and handle == CREATORS[0][0]
        return ([NEW_UPLOAD] if fresh else []) + list(UPLOADS.get(handle, ()))

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            copied: dict[str, Any] = json.loads(json.dumps(self.state))
            return copied


def make_handler(journal: Journal) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            return

        def _send(
            self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8", **headers: str
        ) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in headers.items():
                self.send_header(k.replace("_", "-"), v)
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, location: str) -> None:
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _mark(self) -> str:
            jar = SimpleCookie(self.headers.get("Cookie") or "")
            return jar[MARK].value if MARK in jar else ""

        def _body(self) -> bytes:
            return self.rfile.read(int(self.headers.get("Content-Length") or 0))

        def do_GET(self) -> None:
            parts = urlsplit(self.path)
            query = parse_qs(parts.query)
            path = parts.path
            if path == "/":
                links = "".join(
                    f'<li><a href="{p}">{t}</a></li>'
                    for p, t in (
                        ("/channel", "A creator's channel"),
                        ("/watch?v=t1", "A track with comments"),
                        ("/downloads", "Downloads"),
                        ("/studio", "Studio upload"),
                        ("/captcha", "About page behind a check"),
                        ("/account", "A members' page behind a sign-in"),
                        (f"/channel/{CREATORS[0][0]}/videos", "A creator's uploads"),
                        ("/mail", "A mailbox"),
                        ("/mail/new", "Write a message"),
                        ("/studio/analytics", "Channel analytics"),
                    )
                )
                self._send(200, _page("Athena fixture", f"<h1>Athena fixture</h1><ul>{links}</ul>"))
            elif path == "/channel":
                rows = "".join(
                    f'<li><a href="/watch?v={i}">{html.escape(t)}</a> <span>{d}</span></li>'
                    for i, t, d in TRACKS
                )
                body = (
                    "<h1>Mira Vale - Topic (simulated)</h1><p>1.2K subscribers - 3 videos</p>"
                    f"<h2>Videos</h2><ul>{rows}</ul>"
                )
                self._send(200, _page("Mira Vale - simulated channel", body))
            elif self._business_get(path, query):
                return
            elif path == "/watch":
                vid = (query.get("v") or ["t1"])[0]
                title = next((t for i, t, _ in TRACKS if i == vid), "") or _upload_title(vid)
                said = [c for c in journal.snapshot()["comments"] if c["video"] == vid]
                comments = "".join(f"<li>{html.escape(c['text'])}</li>" for c in said)
                body = (
                    f"<h1>{html.escape(title)}</h1><p>by Mira Vale</p>"
                    f'<form method="post" action="/comment"><input type="hidden" name="video" value="{vid}">'
                    '<textarea name="text" aria-label="Add a comment" rows="3" cols="60"></textarea>'
                    '<button type="submit">Comment</button></form>'
                    f"<h2>{len(said)} comments</h2><ul>{comments}</ul>"
                )
                self._send(200, _page(f"{title} - simulated", body))
            elif path == "/downloads":
                body = (
                    "<h1>Files from the creator (simulated)</h1>"
                    '<p><a href="/files/track.wav">Download the track (WAV)</a></p>'
                    '<p><a href="/files/draft.mp4?mb=5">Download the draft video (5 MB)</a></p>'
                    '<p><a href="/files/draft.mp4?mb=50">Download the draft video (50 MB)</a></p>'
                )
                self._send(200, _page("Downloads - simulated", body))
            elif path == "/files/track.wav":
                journal.bump("downloads")
                self._send(
                    200, wav_bytes(), "audio/wav", Content_Disposition='attachment; filename="track.wav"'
                )
            elif path == "/files/draft.mp4":
                mb = max(1, min(int((query.get("mb") or ["5"])[0] or 5), MB_MAX))
                journal.bump("downloads")
                name = f"draft-{mb}mb.mp4"
                self._send(
                    200, draft_bytes(mb), "video/mp4", Content_Disposition=f'attachment; filename="{name}"'
                )
            elif path == "/studio":
                self._send(200, _page("Channel content - simulated studio", STUDIO))
            elif path == "/studio/dialog":
                self._send(200, _page("Upload dialog", STUDIO_DIALOG))
            elif path == "/captcha":
                body = (
                    "<h1>Mira Vale - About (simulated)</h1>"
                    '<form method="get" action="/about"><label><input type="checkbox" name="human" required> '
                    'I am not a robot</label> <button type="submit">Show email address</button></form>'
                )
                self._send(200, _page("About - simulated", body))
            elif path == "/about":
                body = "<h1>Mira Vale - About (simulated)</h1><p>Business email: mira.vale@example.com</p>"
                self._send(200, _page("About - simulated", body))
            elif path == "/account":
                if self._mark() in journal.snapshot()["marks"]:
                    body = (
                        "<h1>Your account (simulated)</h1><p>Signed in as Mira Vale.</p>"
                        '<p><a href="/channel">Your channel</a></p>'
                    )
                    self._send(200, _page("Your account - simulated", body))
                else:
                    port = str(self.headers.get("Host") or "").rsplit(":", 1)[-1]
                    host = f"http://localhost:{port}" if query.get("away") else ""
                    self._redirect(f"{host}/signin?next=/account")
            elif path == "/signin":
                nxt = html.escape((query.get("next") or ["/account"])[0], quote=True)
                body = (
                    "<h1>Sign in (simulated)</h1>"
                    f'<form method="post" action="/signin"><input type="hidden" name="next" value="{nxt}">'
                    '<label>Email <input type="email" name="email" value="mira.vale@example.com"></label> '
                    '<label>Password <input type="password" name="password" value="simulated"></label> '
                    '<button type="submit">Sign in</button></form>'
                    "<p>Test page: the fields are filled in already; press Sign in.</p>"
                )
                self._send(200, _page("Sign in - simulated", body))
            elif path == "/expire":
                with journal.lock:
                    journal.state["marks"] = []
                    journal.state["expired"] += 1
                self._send(200, json.dumps({"expired": True}).encode(), "application/json")
            elif path == "/state":
                self._send(200, json.dumps(journal.snapshot()).encode(), "application/json")
            else:
                self._send(404, _page("Not found", "<h1>Not found</h1>"))

        def _business_get(self, path: str, query: dict[str, list[str]]) -> bool:
            """The business routines' pages; False when `path` is none of them."""
            handle = _videos_handle(path)
            if handle is not None:
                self._videos(handle)
            elif path == "/mail":
                if query.get("locked") and self._mark() not in journal.snapshot()["marks"]:
                    self._redirect("/signin?next=/mail?locked=1")
                else:
                    self._send(200, _page("Inbox - simulated mail", _inbox(journal.snapshot()["threads"])))
            elif path == "/mail/new":
                self._send(200, _page("New message - simulated mail", COMPOSE))
            elif path.startswith("/mail/"):
                thread_id = path.removeprefix("/mail/")
                thread = journal.snapshot()["threads"].get(thread_id)
                if thread is None:
                    self._send(404, _page("Not found", "<h1>No such conversation</h1>"))
                else:
                    self._send(
                        200, _page(f"{thread['subject']} - simulated mail", _thread(thread_id, thread))
                    )
            elif path == "/studio/analytics":
                self._send(200, _page("Channel analytics - simulated studio", _analytics()))
            else:
                return False
            return True

        def _videos(self, handle: str) -> None:
            name = next((n for h, n, _ in CREATORS if h == handle), None)
            if name is None:
                self._send(404, _page("Not found", "<h1>No such channel</h1>"))
                return
            uploads = journal.uploads(handle)
            rows = "".join(
                f'<li><a href="/watch?v={i}">{html.escape(t)}</a> <span>Published {d}</span></li>'
                for i, t, d in uploads
            )
            body = f"<h1>{html.escape(name)}</h1><p>{len(uploads)} videos</p><h2>Videos</h2><ul>{rows}</ul>"
            self._send(200, _page(f"{name} - videos - simulated channel", body))

        def _form(self) -> dict[str, str]:
            form = parse_qs(self._body().decode("utf-8"))
            return {k: (v[0] if v else "").strip() for k, v in form.items()}

        def _business_post(self, path: str, query: dict[str, list[str]]) -> bool:
            """The business routines' posts; False when `path` is none of them."""
            if path == "/fixture/new-upload":
                journal.bump("new_uploads")
                self._send(200, json.dumps({"upload": NEW_UPLOAD[0]}).encode(), "application/json")
            elif path == "/fixture/new-reply":
                thread_id = (query.get("thread") or ["m1"])[0]
                with journal.lock:
                    thread = journal.state["threads"].get(thread_id)
                    if thread is not None:
                        thread["messages"].append(
                            [thread["from"], _now(), "One more thing: when can we start?"]
                        )
                code = 200 if thread is not None else 404
                self._send(code, json.dumps({"thread": thread_id}).encode(), "application/json")
            elif path == "/mail/new":
                form = self._form()
                if form.get("to") and form.get("body"):
                    journal.add(
                        "sent", {"to": form["to"], "subject": form.get("subject", ""), "text": form["body"]}
                    )
                self._redirect("/mail")
            elif path.startswith("/mail/") and path.endswith("/reply"):
                thread_id = path.removeprefix("/mail/").removesuffix("/reply")
                text = self._form().get("body", "")
                with journal.lock:
                    thread = journal.state["threads"].get(thread_id)
                    if thread is not None and text:
                        thread["messages"].append([CHANNEL_EMAIL, _now(), text])
                        journal.state["sent"].append(
                            {
                                "thread": thread_id,
                                "to": thread["from"],
                                "subject": thread["subject"],
                                "text": text,
                            }
                        )
                if thread is None:
                    self._send(404, _page("Not found", "<h1>No such conversation</h1>"))
                else:
                    self.send_response(303)
                    self.send_header("Location", f"/mail/{thread_id}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
            else:
                return False
            return True

        def do_POST(self) -> None:
            parts = urlsplit(self.path)
            path = parts.path
            if self._business_post(path, parse_qs(parts.query)):
                return
            if path == "/comment":
                form = parse_qs(self._body().decode("utf-8"))
                video = (form.get("video") or ["t1"])[0]
                text = (form.get("text") or [""])[0].strip()
                if text:
                    journal.add("comments", {"video": video, "text": text})
                self.send_response(303)
                self.send_header("Location", f"/watch?v={video}")
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif path == "/signin":
                form = parse_qs(self._body().decode("utf-8"))
                nxt = (form.get("next") or ["/account"])[0]
                mark = secrets.token_hex(12)
                with journal.lock:
                    journal.state["marks"].append(mark)
                    journal.state["signins"] += 1
                self.send_response(303)
                self.send_header("Set-Cookie", f"{MARK}={mark}; Path=/; HttpOnly; SameSite=Lax")
                self.send_header("Location", nxt if nxt.startswith("/") else "/account")
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif path in ("/uploaded", "/studio/save"):
                data = json.loads(self._body() or b"{}")
                journal.add("uploads" if path == "/uploaded" else "saves", data)
                self._send(200, b"{}", "application/json")
            else:
                self._send(404, b"{}", "application/json")

    return Handler


COMPOSE = """
<h1>New message (simulated mail)</h1>
<form method="post" action="/mail/new">
<p><label>To <input type="email" name="to" aria-label="To" size="40"></label></p>
<p><label>Subject <input type="text" name="subject" aria-label="Subject" size="60"></label></p>
<p><textarea name="body" aria-label="Message" rows="8" cols="70"></textarea></p>
<button type="submit">Send</button>
</form>
"""


def _videos_handle(path: str) -> str | None:
    """The handle of `/channel/<handle>/videos` or `/@<handle>/videos`, else None."""
    for prefix in ("/channel/", "/@"):
        if path.startswith(prefix) and path.endswith("/videos"):
            handle = path.removeprefix(prefix).removesuffix("/videos")
            if handle and "/" not in handle:
                return handle
    return None


def _upload_title(vid: str) -> str:
    for uploads in (*UPLOADS.values(), (NEW_UPLOAD,)):
        for i, title, _ in uploads:
            if i == vid:
                return title
    return "Unknown track"


def _inbox(threads: dict[str, Any]) -> str:
    def last(item: tuple[str, Any]) -> str:
        return str(item[1]["messages"][-1][1])

    rows = []
    for thread_id, thread in sorted(threads.items(), key=last, reverse=True):
        _, at, text = thread["messages"][-1]
        rows.append(
            f'<tr><td><a href="/mail/{thread_id}">{html.escape(thread["subject"])}</a></td>'
            f"<td>{html.escape(thread['from'])}</td><td>{html.escape(text[:80])}</td>"
            f"<td>{_shown(at)}</td></tr>"
        )
    return (
        '<h1>Inbox (simulated mail)</h1><p><a href="/mail/new">New message</a></p>'
        "<table><thead><tr><th>Subject</th><th>From</th><th>Snippet</th><th>Time</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _thread(thread_id: str, thread: dict[str, Any]) -> str:
    said = "".join(
        f"<article><p><b>From:</b> {html.escape(sender)} - {_shown(at)}</p>"
        f"<p>{html.escape(text)}</p></article>"
        for sender, at, text in thread["messages"]
    )
    return (
        f"<h1>{html.escape(thread['subject'])}</h1>{said}"
        f'<form method="post" action="/mail/{thread_id}/reply">'
        '<label for="reply">Reply</label><br>'
        '<textarea id="reply" name="body" aria-label="Reply" rows="6" cols="70"></textarea><br>'
        '<button type="submit">Send</button></form>'
    )


def _analytics() -> str:
    rows = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in ANALYTICS)
    return (
        "<h1>Channel analytics (simulated studio)</h1>"
        f"<p>Last updated {ANALYTICS_CLAIMED}</p>"
        f"<table><tbody>{rows}</tbody></table>"
    )


class _Server(ThreadingHTTPServer):
    def handle_error(self, request: Any, client_address: Any) -> None:
        """A tab closed mid-request (the shell was ended) is not an error worth a traceback."""
        return


def serve(port: int) -> tuple[ThreadingHTTPServer, Journal]:
    journal = Journal()
    server = _Server(("127.0.0.1", port), make_handler(journal))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, journal


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="athena.browser.fixture")
    parser.add_argument("--port", type=int, default=8781)
    args = parser.parse_args(argv)
    server = _Server(("127.0.0.1", args.port), make_handler(Journal()))
    print(f"simulated test pages on http://127.0.0.1:{args.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
