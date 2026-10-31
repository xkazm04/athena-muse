"""The access step (ADR 0014): after the keep, the person signs in to each real site the chore needs,
in her browser, so next time Athena reaches it on her own.

The sites are the confirmed sites of the sketch's app nodes (her practice apps are invented and never
come here). `begin` makes each one a site of the Project (the only place a site is ever written, so
the only way her browser comes to trust one) and opens the step; with no real site the draft goes
straight to `saved`. `act` takes one site at a time:

- `sign_in`: open it in her browser, in front, and hand the person the wheel. Signing in happens on
  the site's own page; Athena never asks for, sees or keeps a password.
- `check`: look now. Signed in: the site is done. Anything else: it stays open with the reason.
- `skip`: the site is kept as signed out, a blocker on the overview from day one.
- `use_moved`: a look ended on another site's page that is not a sign-in (another address of the
  same company, `www.` to `studio.`); that site replaces this one, here and in the Project. Only
  onboarding grants trust, so the move is caught now, not as a blocker later (owner, 2026-10-31).

When no site is open, the step checks every signed-in site once more (a sign-in on one site can sign
her out of another); any that is no longer signed in opens again with the reason. Then the draft is
`saved`.
"""

from __future__ import annotations

from typing import Any, cast

from athena.app import Daemon
from athena.browser import sites
from athena.contracts import AccessAct, Draft, DraftSite, Sketch
from athena.errors import ApiError

SKIPPED = "You skipped signing in when the chore was set up."


def confirmed_sites(sketch: Sketch) -> list[DraftSite]:
    """The real sites the person confirmed on the sketch's app nodes, once each, in sketch order."""
    out: list[DraftSite] = []
    for node in sketch["nodes"]:
        site = node.get("site")
        if node["kind"] != "app" or not node["confirmed"] or site is None or not site["confirmed"]:
            continue
        if any(s["origin"] == site["origin"] for s in out):
            continue
        out.append(
            {"origin": site["origin"], "label": site["label"], "probe_url": site["url"], "state": "open"}
        )
    return out


def begin(daemon: Daemon, stored: dict[str, Any], chore: str) -> None:
    """At the keep: the confirmed sites become the Project's sites and the step is `access`; with
    none, the step is `saved`. Changes `stored` in place; the caller writes it."""
    found = confirmed_sites(cast("Sketch", stored["sketch"]))
    if not found:
        stored["step"] = "saved"
        stored.pop("sites", None)
        return
    for site in found:
        kept = daemon.sites.add(stored["space_id"], site["origin"], site["label"], site["probe_url"], chore)
        sites.publish(daemon, stored["space_id"], kept)
    stored["sites"] = found
    stored["step"] = "access"


def act(daemon: Daemon, draft_id: str, origin: str, what: AccessAct) -> Draft:
    if what not in ("sign_in", "check", "skip", "use_moved"):
        raise ApiError("bad_request", "the act is sign_in, check, skip or use_moved")
    draft = daemon.drafts.get(draft_id)
    if draft["step"] != "access":
        raise ApiError("bad_request", "signing in to the chore's sites comes after you keep it")
    listed = [dict(s) for s in draft.get("sites", [])]
    mine = next((s for s in listed if s["origin"] == origin), None)
    if mine is None:
        raise ApiError("unknown_ref", "that site is not one this chore needs")
    space_id = draft["space_id"]
    if what == "sign_in":
        mine["tab"] = sites.sign_in(daemon, space_id, origin)
        mine.pop("reason", None)
    elif what == "check":
        if not daemon.relay.connected():
            raise ApiError("bad_request", "Her browser is not open; the desktop app runs it.")
        site, seen = sites.check_seen(daemon, space_id, origin, force=True)
        mine.pop("moved_to", None)
        if site["access"] == "signed_in":
            mine["state"] = "signed_in"
            mine.pop("reason", None)
            mine.pop("tab", None)
        else:
            mine["state"] = "open" if mine["state"] != "skipped" else "skipped"
            mine["reason"] = site.get("reason", "")
            moved = sites.moved_to(origin, seen) if seen is not None else ""
            if moved:
                mine["moved_to"] = moved
    elif what == "use_moved":
        listed = _use_moved(daemon, space_id, listed, mine)
    else:
        mine["state"] = "skipped"
        mine.pop("tab", None)
        site, changed = daemon.sites.looked(space_id, origin, "signed_out", SKIPPED)
        if changed:
            sites.publish(daemon, space_id, site)
    if all(s["state"] != "open" for s in listed):
        _check_again(daemon, space_id, listed)
    stored = cast("dict[str, Any]", dict(draft))
    stored["sites"] = listed
    if all(s["state"] != "open" for s in listed):
        stored["step"] = "saved"
    return daemon.drafts.put(cast("Draft", stored))


def _use_moved(
    daemon: Daemon, space_id: str, listed: list[dict[str, Any]], mine: dict[str, Any]
) -> list[dict[str, Any]]:
    """The site a look moved to replaces this one: in the Project (carrying the chores it blocks) and
    on the step. Already on the step: this one just goes."""
    moved = mine.get("moved_to")
    if not moved:
        raise ApiError("bad_request", "her last look at that site did not end on another site")
    origin, url = sites.probe_address(moved)
    old = daemon.sites.get(space_id, mine["origin"])
    kept = None
    for chore in old["blocks"] or [""]:
        kept = daemon.sites.add(space_id, origin, old["label"], url, chore)
    daemon.sites.remove(space_id, mine["origin"])
    if kept is not None:
        sites.publish(daemon, space_id, kept)
    rest = [s for s in listed if s is not mine]
    if any(s["origin"] == origin for s in rest):
        return rest
    replaced: dict[str, Any] = {"origin": origin, "label": mine["label"], "probe_url": url, "state": "open"}
    return [replaced if s is mine else s for s in listed]


def _check_again(daemon: Daemon, space_id: str, listed: list[dict[str, Any]]) -> None:
    """Before the step ends: each signed-in site once more. One that no longer is opens again."""
    if not daemon.relay.connected():
        return
    for entry in listed:
        if entry["state"] != "signed_in":
            continue
        site = sites.check(daemon, space_id, entry["origin"], force=True)
        if site["access"] != "signed_in":
            entry["state"] = "open"
            entry["reason"] = f"After the last sign-in, {site.get('reason', 'she is no longer signed in.')}"
