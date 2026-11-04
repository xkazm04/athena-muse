"""The phone page on the peer listener: open, fixed files, no traversal (ADR 0017).

athena/peer/phone.py (peer_routes, serve) over a real peer socket, plus the page's own node tests
(tests/peer_phone/*.test.mjs, run here under pytest; also `node --test tests/peer_phone/*.test.mjs`).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Iterator
from http.client import HTTPConnection
from pathlib import Path

import pytest

from athena.peer.listener import PeerHost
from athena.peer.overlay import Overlay
from athena.peer.phone import FILES, MOBILE_DIR, SECURITY_HEADERS, serve

HERE = Path(__file__).resolve().parent
SUITES = sorted((HERE / "peer_phone").glob("*.test.mjs"))
NODE = shutil.which("node")


class NoSeal:
    kind = "none"

    def seal(self, name: str, value: str) -> None: ...

    def unseal(self, name: str) -> str | None:
        return None

    def destroy(self, name: str) -> None: ...


@pytest.fixture
def beacon(tmp_path: Path) -> Iterator[PeerHost]:
    up = Overlay("up", "127.0.0.1")
    peer_host = PeerHost(tmp_path, port=0, probe=lambda: up, seal=NoSeal(), admit_loopback=True)  # type: ignore[arg-type]
    from athena.peer import phone

    peer_host.add_routes(phone.peer_routes(peer_host))
    peer_host.beacon = True
    peer_host.reconcile()
    assert peer_host.bound is not None
    yield peer_host
    peer_host.close()


def get(peer_host: PeerHost, path: str) -> tuple[int, dict[str, str], bytes]:
    assert peer_host.bound is not None
    connection = HTTPConnection("127.0.0.1", peer_host.bound[1], timeout=10)
    try:
        connection.request("GET", path)
        answer = connection.getresponse()
        return answer.status, {k.lower(): v for k, v in answer.getheaders()}, answer.read()
    finally:
        connection.close()


def test_the_shell_is_served_without_a_token(beacon: PeerHost) -> None:
    status, headers, body = get(beacon, "/m/")
    assert status == 200
    assert headers["content-type"] == "text/html; charset=utf-8"
    assert b'<script type="module" src="app.js"></script>' in body


@pytest.mark.parametrize("name", sorted(FILES))
def test_every_file_has_its_own_content_type_and_the_security_headers(beacon: PeerHost, name: str) -> None:
    status, headers, body = get(beacon, f"/m/{name}")
    assert status == 200
    assert headers["content-type"] == FILES[name]
    assert body == (MOBILE_DIR / name).read_bytes()
    for header, value in SECURITY_HEADERS.items():
        assert headers[header.lower()] == value
    assert "'unsafe-inline'" not in headers["content-security-policy"]


def test_m_without_its_slash_redirects_to_the_page(beacon: PeerHost) -> None:
    status, headers, _ = get(beacon, "/m")
    assert status == 308
    assert headers["location"] == "/m/"


@pytest.mark.parametrize(
    "path",
    [
        "/m/../routes.py",
        "/m/%2e%2e/routes.py",
        "/m/..%2f..%2fwiring.py",
        "/m/%2e%2e%5cremote.py",
        "/m/mobile/app.js",
        "/m/app.js/",
        "/m/APP.JS",
        "/m/index.html%00",
        "/m/nothing.html",
    ],
)
def test_anything_but_a_listed_name_is_a_404_not_a_file(beacon: PeerHost, path: str) -> None:
    status, headers, body = get(beacon, path)
    assert status == 404
    assert b"import" not in body and b"<html" not in body
    assert headers["x-content-type-options"] == "nosniff"


def test_the_rest_of_the_listener_still_wants_a_token(beacon: PeerHost) -> None:
    assert get(beacon, "/peer/hello")[0] == 401


def test_every_file_in_the_mobile_directory_is_served_and_nothing_else() -> None:
    on_disk = {p.name for p in MOBILE_DIR.iterdir() if p.is_file()}
    assert on_disk == set(FILES)


def test_the_page_never_writes_html_from_a_string() -> None:
    script = (MOBILE_DIR / "app.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "insertAdjacentHTML" not in script
    assert "eval(" not in script
    # The claim is read from the fragment and wiped from the address bar.
    assert "history.replaceState" in script


def test_serve_reads_only_from_its_own_directory(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<p>elsewhere</p>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("no", encoding="utf-8")
    assert serve("index.html", tmp_path).body == b"<p>elsewhere</p>"
    assert serve("secret.txt", tmp_path).status == 404
    assert serve("app.js", tmp_path).status == 404  # listed, but not there: still a 404


def test_the_offline_shell_precaches_every_served_file() -> None:
    # sw.js caches the shell for a page opened offline; a module the page imports but the cache
    # lacks would leave that page broken. "./" is the shell's own URL; sw.js is the worker itself.
    script = (MOBILE_DIR / "sw.js").read_text(encoding="utf-8")
    match = re.search(r"const FILES = \[([^\]]*)\];", script)
    assert match is not None
    cached = set(re.findall(r'"([^"]+)"', match.group(1)))
    assert cached - {"./"} == set(FILES) - {"sw.js"}
    assert "./" in cached


def test_a_hidden_element_stays_hidden_whatever_its_display() -> None:
    css = (MOBILE_DIR / "app.css").read_text(encoding="utf-8")
    script = (MOBILE_DIR / "app.js").read_text(encoding="utf-8")
    assert ".hidden = " in script and "hidden: true" in script
    assert re.search(r"\[hidden\]\s*\{[^}]*display:\s*none\s*!important", css)


TOKENS = HERE.parent / "apps" / "desktop" / "src" / "theme" / "tokens.css"


def _blocks(css: str) -> dict[str, dict[str, str]]:
    """Custom properties per block: the dark block, the light block, the light block under the
    system's media query, and the scale tokens (the last plain `:root`)."""
    heads = {
        "dark": '[data-theme="dark"] {',
        "light": '[data-theme="light"] {',
        "system-light": ':root:not([data-theme="dark"]) {',
        "scale": "/* Scale tokens",
    }
    at = {name: css.index(head) for name, head in heads.items()}
    out: dict[str, dict[str, str]] = {}
    for name, start in at.items():
        end = min([later for later in at.values() if later > start] + [len(css)])
        body = css[start:end]
        if name == "scale":
            body = body[body.index(":root {") :]
            body = body[: body.index("\n}")]  # the first block only, not the large-text overrides
        out[name] = {
            m.group(1): " ".join(m.group(2).split())
            for m in re.finditer(r"^\s*--([\w-]+):\s*(.+?);", body, re.M)
        }
    return out


def test_the_phone_wears_the_desktops_tokens_value_for_value() -> None:
    # app.css copies a subset of the desktop's Loop Tide tokens (no build step to import them), so a
    # re-themed colour or radius on the computer must be copied here or this fails.
    desktop = _blocks(TOKENS.read_text(encoding="utf-8"))
    phone = _blocks((MOBILE_DIR / "app.css").read_text(encoding="utf-8"))
    for name, mine in phone.items():
        assert mine, name
        for token, value in mine.items():
            assert desktop[name].get(token) == value, f"{name}: --{token} drifted from tokens.css"
    assert {"background", "role-human", "on-human", "glass", "lt-arc"} <= set(phone["dark"])
    assert set(phone["light"]) == set(phone["system-light"]) == set(phone["dark"])


def test_hello_hands_the_phone_the_look_and_the_page_paints_it() -> None:
    from athena.peer import routes as peer_routes
    from athena.peer.listener import PeerRequest

    class Host:
        beacon = True
        look = staticmethod(lambda: {"theme": "light", "type_scale": "large", "motion": "calm"})
        setup_phase = staticmethod(lambda: None)

        class identity:
            class identity:
                device_id, name = "dev_x", "Desk"

        class pairings:
            window_open = staticmethod(lambda: False)

        class presence:
            own = staticmethod(lambda: None)

    request = PeerRequest("GET", "/peer/hello", {}, {}, "127.0.0.1", None)  # type: ignore[arg-type]
    body = peer_routes.hello(Host(), request)[1]  # type: ignore[arg-type]
    assert body["look"] == {"theme": "light", "type_scale": "large", "motion": "calm"}
    script = (MOBILE_DIR / "app.js").read_text(encoding="utf-8")
    assert "answer.body.look" in script and "data-type-scale" in script and "data-motion" in script


def test_read_it_first_is_a_tap_target_a_thumb_can_hit() -> None:
    css = (MOBILE_DIR / "app.css").read_text(encoding="utf-8")
    rule = re.search(r"\.card summary\s*\{([^}]*)\}", css)
    assert rule is not None
    assert re.search(r"min-height:\s*44px", rule.group(1))


def test_the_page_calls_the_routes_the_daemon_serves() -> None:
    script = (MOBILE_DIR / "app.js").read_text(encoding="utf-8")
    turn = (MOBILE_DIR / "turn.js").read_text(encoding="utf-8")
    for path in ("/peer/hello", "/peer/pair/request", "/peer/pair/claim", "/peer/decisions", "/peer/message"):
        assert path in script
    assert "/peer/turns/" in turn
    assert "window_closed" not in script  # there is no window to be asleep here


def test_turn_js_is_served_and_app_js_delegates_to_it() -> None:
    assert FILES["turn.js"] == "text/javascript; charset=utf-8"
    script = (MOBILE_DIR / "app.js").read_text(encoding="utf-8")
    assert 'from "./turn.js"' in script
    assert "pendingTurn(" in script  # a reload re-attaches to the open turn
    assert "if (sameCards(chat.cards, polled)) return;" in script


def test_turn_js_never_writes_html_from_a_string() -> None:
    script = (MOBILE_DIR / "turn.js").read_text(encoding="utf-8")
    assert "innerHTML" not in script and "insertAdjacentHTML" not in script
    assert "eval(" not in script and "document." not in script


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_phone_page_cases_pass_under_node() -> None:
    assert NODE is not None and SUITES
    done = subprocess.run(
        [NODE, "--test", "--test-reporter=tap", *map(str, SUITES)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "# fail 0" in done.stdout
