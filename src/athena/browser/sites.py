"""A project's sites (ADR 0014): the real web apps its chores need, the browser's trust list, and the
look that says whether the person is still signed in to each.

A site is written only by a chore's onboarding (the access step, `drafts/access.py`): no other path
grants her browser trust. A look changes only what it found (`access`, `checked_at`, `reason`), and a
change is published as the `site` app event, so the overview follows it live. Erasing a project
erases its sites (the `sites` table is in `spaces.erase`).

The look (`check`) is one function used by onboarding, the overview and her hands: it opens the
site's probe address in a hidden tab and decides with `decide`, a pure table:

- her browser is not open: no verdict (nothing stored changes);
- the page could not be reached: `unknown`, with the reason;
- the page ended on another site (a sign-in host): `signed_out`;
- the page's address is a sign-in route (`/login`, `/signin`, `/auth`...): `signed_out`;
- the page shows a password field: `signed_out`;
- otherwise: `signed_in`.

A look stands SITE_FRESH_S seconds: the overview and a hand look again only after that, and at
most one look per site runs at a time.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlsplit

from athena.clock import now_iso
from athena.contracts import LABEL_MAX, SITE_FRESH_S, SITES_MAX, Site, SiteAccess
from athena.errors import ApiError
from athena.spaces import normalise_origin
from athena.store import Store

if TYPE_CHECKING:
    from athena.app import Daemon

#: Seconds a look waits after the page loads, so a script's redirect lands before the address is read.
SETTLE_S = 1.0
OPEN_WAIT_S = 45.0
#: Path segments that name a sign-in page.
SIGN_IN_SEGMENTS = frozenset(
    {
        "login",
        "log-in",
        "log_in",
        "logon",
        "signin",
        "sign-in",
        "sign_in",
        "auth",
        "authenticate",
        "authorize",
        "sso",
        "oauth",
        "oauth2",
        "servicelogin",
        "identifier",
        "challenge",
    }
)
_SEGMENT = re.compile(r"[^/]+")


def host_of(origin: str) -> str:
    return urlsplit(origin).netloc or origin


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    try:
        return normalise_origin(f"{parts.scheme}://{parts.netloc}")
    except ApiError:
        return ""


def probe_address(raw: str) -> tuple[str, str]:
    """(origin, the address a look opens) from what Athena or the person wrote: a bare host or a full
    http(s) address. ApiError("bad_request") in plain words for anything else."""
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        raise ApiError("bad_request", "a site needs its web address")
    if "://" not in text:
        text = "https://" + text
    parts = urlsplit(text)
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        raise ApiError("bad_request", "a site's address starts with http:// or https://")
    origin = normalise_origin(f"{parts.scheme}://{parts.netloc}")
    path = parts.path or "/"
    url = origin + path + (f"?{parts.query}" if parts.query else "")
    return origin, url[:500]


@dataclass(frozen=True)
class Seen:
    """What her browser saw on a look: whether the page was reached, the address it ended on, and
    whether a password field was showing. `why` says why it was not reached."""

    reached: bool
    url: str = ""
    password: bool = False
    why: str = ""


def sign_in_path(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return any(seg in SIGN_IN_SEGMENTS for seg in _SEGMENT.findall(path))


def moved_to(origin: str, seen: Seen) -> str:
    """The address on another site a look ended on when that page is not a sign-in (another
    address of the same company, such as `www.` to `studio.`); empty otherwise. Onboarding offers it
    as the site to use instead, so the move is caught while the chore is set up (ADR 0014)."""
    if not seen.reached or seen.password or sign_in_path(seen.url):
        return ""
    landed = origin_of(seen.url)
    if not landed or landed == origin:
        return ""
    return probe_address(seen.url)[1]


def decide(origin: str, seen: Seen) -> tuple[SiteAccess, str]:
    """The look's decision table, in plain words (the reason is shown to the person)."""
    site = host_of(origin)
    if not seen.reached:
        return "unknown", f"Athena could not reach {site}: {seen.why or 'no answer'}"
    landed = origin_of(seen.url)
    if moved_to(origin, seen):
        return "signed_out", f"{site} sent her on to {host_of(landed)}, a different site."
    if landed != origin:
        where = host_of(landed) if landed else "another page"
        return "signed_out", f"{site} sent her to {where} to sign in."
    if sign_in_path(seen.url):
        return "signed_out", f"{site} showed its sign-in page."
    if seen.password:
        return "signed_out", f"{site} asked for a password."
    return "signed_in", f"{site} opened without asking her to sign in."


def _row(r: Any) -> Site:
    out: Site = {
        "origin": r["origin"],
        "label": r["label"],
        "probe_url": r["probe_url"],
        "access": cast("SiteAccess", r["access"]),
        "blocks": json.loads(r["blocks"]),
    }
    if r["checked_at"]:
        out["checked_at"] = r["checked_at"]
    if r["reason"]:
        out["reason"] = r["reason"]
    return out


def _age_s(checked_at: str | None) -> float | None:
    if not checked_at:
        return None
    try:
        then = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(UTC) - then).total_seconds()


def stale(site: Site) -> bool:
    age = _age_s(site.get("checked_at"))
    return age is None or age >= SITE_FRESH_S


class Sites:
    """The `sites` table. `add` is the onboarding's alone; `looked` is the look's alone."""

    def __init__(self, store: Store) -> None:
        self._store = store

    def list(self, space_id: str) -> list[Site]:
        rows = self._store.query(
            "SELECT * FROM sites WHERE space_id = ? ORDER BY created, origin", (space_id,)
        )
        return [_row(r) for r in rows]

    def get(self, space_id: str, origin: str) -> Site:
        rows = self._store.query("SELECT * FROM sites WHERE space_id = ? AND origin = ?", (space_id, origin))
        if not rows:
            raise ApiError("unknown_ref", "that site is not one of this project's sites")
        return _row(rows[0])

    def trusted(self, space_id: str, origin: str) -> bool:
        """The browser's trust check (ADR 0013 as amended by 0014): one of the project's sites."""
        if not space_id or not origin:
            return False
        return bool(
            self._store.query("SELECT 1 FROM sites WHERE space_id = ? AND origin = ?", (space_id, origin))
        )

    def add(self, space_id: str, origin: str, label: str, probe_url: str, chore: str) -> Site:
        """Onboarding only (the access step): keeps the site, and the chore that needs it. A site the
        project already has keeps what the last look found."""
        label = " ".join(label.split())[:LABEL_MAX] or host_of(origin)
        chore = " ".join(chore.split())[:LABEL_MAX]
        with self._store.tx() as db:
            found = db.execute(
                "SELECT blocks FROM sites WHERE space_id = ? AND origin = ?", (space_id, origin)
            ).fetchone()
            if found is None:
                if (
                    db.execute("SELECT COUNT(*) FROM sites WHERE space_id = ?", (space_id,)).fetchone()[0]
                    >= SITES_MAX
                ):
                    raise ApiError("bad_request", f"a project holds at most {SITES_MAX} sites")
                db.execute(
                    "INSERT INTO sites(space_id, origin, label, probe_url, access, blocks, created) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        space_id,
                        origin,
                        label,
                        probe_url,
                        "unknown",
                        json.dumps([chore] if chore else []),
                        now_iso(),
                    ),
                )
            else:
                blocks = json.loads(found["blocks"])
                if chore and chore not in blocks:
                    blocks.append(chore)
                db.execute(
                    "UPDATE sites SET label = ?, probe_url = ?, blocks = ? WHERE space_id = ? AND origin = ?",
                    (label, probe_url, json.dumps(blocks), space_id, origin),
                )
        return self.get(space_id, origin)

    def remove(self, space_id: str, origin: str) -> None:
        """Onboarding only: a site replaced by the one its look moved to (`use_moved`)."""
        self._store.run("DELETE FROM sites WHERE space_id = ? AND origin = ?", (space_id, origin))

    def looked(self, space_id: str, origin: str, access: SiteAccess, reason: str) -> tuple[Site, bool]:
        """Stores what a look found: (the site, whether what it found changed)."""
        before = self.get(space_id, origin)
        self._store.run(
            "UPDATE sites SET access = ?, reason = ?, checked_at = ? WHERE space_id = ? AND origin = ?",
            (access, reason, now_iso(), space_id, origin),
        )
        after = self.get(space_id, origin)
        return after, (before["access"], before.get("reason")) != (access, reason)


# --- the look --------------------------------------------------------------------------------------

_locks_guard = threading.Lock()
_locks: dict[tuple[str, str], threading.Lock] = {}


def _lock(space_id: str, origin: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault((space_id, origin), threading.Lock())


def look(daemon: Daemon, probe_url: str) -> Seen | None:
    """Opens the address in a hidden tab, reads where it ended and whether a password field shows,
    and closes the tab. None when her browser is not open."""
    opened = daemon.relay.call("open", {"url": probe_url, "hidden": True}, timeout=OPEN_WAIT_S)
    if opened.get("reason") == "no_browser":
        return None
    tab = (opened.get("tab") or {}).get("id")
    try:
        if not opened.get("ok") or not isinstance(tab, int):
            return Seen(False, why=str(opened.get("output") or opened.get("reason") or "no answer"))
        if SETTLE_S:
            time.sleep(SETTLE_S)
        seen = daemon.relay.call("tab", tab=tab)
        url = str((seen.get("tab") or {}).get("url") or (opened.get("tab") or {}).get("url") or "")
        found = daemon.relay.call("page_find", {"role": "password"}, tab=tab)
        output = str(found.get("output", ""))
        password = bool(found.get("ok")) and output.strip() != "nothing matched" and "password" in output
        return Seen(True, url=url, password=password)
    finally:
        if isinstance(tab, int):
            daemon.relay.call("close", tab=tab)


def publish(daemon: Daemon, space_id: str, site: Site) -> None:
    daemon.events.publish({"type": "site", "space_id": space_id, "site": site})


def check(daemon: Daemon, space_id: str, origin: str, *, force: bool = False) -> Site:
    """The site after a look: the stored one while it is fresh (unless `force`), else a new look.
    With her browser not open, the stored site is answered unchanged. Publishes a change."""
    return check_seen(daemon, space_id, origin, force=force)[0]


def check_seen(
    daemon: Daemon, space_id: str, origin: str, *, force: bool = False
) -> tuple[Site, Seen | None]:
    """`check`, and what the look saw (None when no look ran): onboarding reads a move from it."""
    site = daemon.sites.get(space_id, origin)
    with _lock(space_id, origin):
        site = daemon.sites.get(space_id, origin)
        if not force and not stale(site):
            return site, None
        seen = look(daemon, site["probe_url"])
        if seen is None:
            return site, None
        access, reason = decide(origin, seen)
        site, changed = daemon.sites.looked(space_id, origin, access, reason)
    if changed:
        publish(daemon, space_id, site)
    return site, seen


def refresh(daemon: Daemon, space_id: str) -> int:
    """Looks again, on a worker thread, at each site whose last look is stale (the overview opening).
    Answers how many it started; none while her browser is not open."""
    if not daemon.relay.connected():
        return 0
    started = 0
    for site in daemon.sites.list(space_id):
        if not stale(site) or _lock(space_id, site["origin"]).locked():
            continue
        threading.Thread(
            target=_quietly, args=(daemon, space_id, site["origin"]), name="site-look", daemon=True
        ).start()
        started += 1
    return started


def _quietly(daemon: Daemon, space_id: str, origin: str) -> None:
    try:
        check(daemon, space_id, origin)
    except ApiError:
        return  # the project or the site went away while the look waited


def sign_in(daemon: Daemon, space_id: str, origin: str) -> int:
    """Opens the site in her browser, in front, and hands the person the wheel; answers the tab.
    The person signs in on the site's own page: Athena never asks for, sees or keeps a password."""
    site = daemon.sites.get(space_id, origin)
    opened = daemon.relay.call("open", {"url": site["probe_url"]}, timeout=OPEN_WAIT_S)
    tab = (opened.get("tab") or {}).get("id")
    if not isinstance(tab, int):
        raise ApiError("bad_request", str(opened.get("output") or "Her browser could not open the site."))
    say = f"Sign in to {site['label']} here; Athena never sees your password"
    handed = daemon.relay.call("wheel", {"say": say}, tab=tab)
    if not handed.get("ok"):
        raise ApiError(
            "bad_request", str(handed.get("output") or "Her browser could not bring the site forward.")
        )
    return tab
