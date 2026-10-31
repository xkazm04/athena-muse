"""A project's sites (ADR 0014): the store and its erase, trust from sites alone, the look's decision
table, the access step's state machine, the sketch's real sites, and the routes the overview uses."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from starlette.testclient import TestClient

from athena.app import Daemon
from athena.browser import sites
from athena.browser.sites import Seen, decide
from athena.contracts import AppEvent, Draft, Sketch
from athena.drafts import access
from athena.drafts.sketch import SketchError, apply, confirm, drop
from athena.engine import ToolCall
from athena.errors import ApiError
from athena.server import create_app
from athena.turn import dispatch, execute
from browser_kit import ORIGIN, FakeShell, trust
from drafts_kit import Fake
from test_drafts_rehearse import H, lines, to_rehearse

OTHER = "https://billing.sunbeam-club.example"


@pytest.fixture(autouse=True)
def no_settle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sites, "SETTLE_S", 0.0)


@pytest.fixture
def daemon(tmp_path: Path) -> Iterator[Daemon]:
    d = Daemon.open(tmp_path / "data")
    d.gate.set_executor(lambda card: execute(d, card))
    yield d
    d.store.close()


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Fake:
    from athena import engine as engine_mod

    f = Fake()
    monkeypatch.setattr(engine_mod, "build_engine", lambda *a, **k: f)
    return f


@pytest.fixture
def client(daemon: Daemon) -> TestClient:
    return TestClient(create_app(daemon, "t"))


def heard(daemon: Daemon) -> list[AppEvent]:
    """Every app event published from here on."""
    got: list[AppEvent] = []
    original = daemon.events.publish

    def keep(event: AppEvent) -> None:
        got.append(event)
        original(event)

    daemon.events.publish = keep  # type: ignore[method-assign]
    return got


# --- the store -------------------------------------------------------------------------------------


def test_a_site_is_kept_once_per_project_with_the_chores_that_need_it_and_erased_with_it(
    daemon: Daemon,
) -> None:
    space = daemon.spaces.create({"name": "Club"})["id"]
    other = daemon.spaces.create({"name": "Elsewhere"})["id"]
    daemon.sites.add(space, ORIGIN, "The club", f"{ORIGIN}/account", "Club invoice check")
    daemon.sites.add(space, ORIGIN, "The club", f"{ORIGIN}/account", "Monthly report")
    daemon.sites.add(other, ORIGIN, "The club", f"{ORIGIN}/account", "Another")
    [site] = daemon.sites.list(space)
    assert site["access"] == "unknown" and "checked_at" not in site
    assert site["blocks"] == ["Club invoice check", "Monthly report"]
    looked, changed = daemon.sites.looked(space, ORIGIN, "signed_in", "fine")
    assert changed and looked["access"] == "signed_in" and looked["checked_at"]
    assert daemon.sites.looked(space, ORIGIN, "signed_in", "fine")[1] is False
    daemon.sites.add(space, ORIGIN, "The club", f"{ORIGIN}/account", "Monthly report")
    assert daemon.sites.get(space, ORIGIN)["access"] == "signed_in"  # onboarding again keeps the look
    daemon.spaces.erase(space)
    assert daemon.sites.list(space) == [] and not daemon.sites.trusted(space, ORIGIN)
    assert daemon.sites.trusted(other, ORIGIN)


# --- trust -----------------------------------------------------------------------------------------


def test_trust_reads_sites_only_a_former_app_grants_nothing(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Channel", "apps": [ORIGIN]})["id"]
    with FakeShell(daemon.relay) as shell:
        opened = dispatch(daemon, space, ToolCall("c1", "page_open", {"url": f"{ORIGIN}/channel"}))
        assert opened.card is not None and "not one of this project's sites" in opened.card["label"]
        asked = dispatch(daemon, space, ToolCall("c2", "add_app", {"origin": "https://studio.example"}))
        assert asked.card is not None
        daemon.gate.resolve(asked.card["id"], "approve")
        assert "https://studio.example" in daemon.spaces.get(space)["apps"]
        again = dispatch(daemon, space, ToolCall("c3", "page_open", {"url": "https://studio.example/x"}))
        assert again.card is not None  # an app the person added describes the project; it opens nothing
        assert not any(c["hand"] == "open" for c in shell.calls)
        trust(daemon, space)
        assert dispatch(daemon, space, ToolCall("c4", "page_open", {"url": f"{ORIGIN}/channel"})).card is None


def test_a_hand_on_a_trusted_site_looks_first_and_a_signed_out_site_is_refused(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Channel"})["id"]
    daemon.sites.add(space, ORIGIN, "Fixture", f"{ORIGIN}/account", "A chore")
    with FakeShell(daemon.relay) as shell:
        shell.pages[f"{ORIGIN}/account"] = {"final": f"{ORIGIN}/signin?next=/account", "password": True}
        refused = dispatch(daemon, space, ToolCall("c1", "page_open", {"url": f"{ORIGIN}/channel"}))
        assert (
            refused.card is None and "not signed in" in refused.result and "Sign in again" in refused.result
        )
        looked = [c for c in shell.calls if c["hand"] == "open"]
        assert [c["args"] for c in looked] == [{"url": f"{ORIGIN}/account", "hidden": True}]
        assert shell.tabs[1]["closed"] is True  # the look closes its hidden tab
        assert daemon.sites.get(space, ORIGIN)["access"] == "signed_out"


# --- the look --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seen", "access", "words"),
    [
        (Seen(True, url=f"{ORIGIN}/account"), "signed_in", "opened without asking"),
        (
            Seen(True, url="https://accounts.example.com/login"),
            "signed_out",
            "sent her to accounts.example.com",
        ),
        (Seen(True, url=f"{ORIGIN}/signin?next=/account"), "signed_out", "sign-in page"),
        (Seen(True, url=f"{ORIGIN}/u/1/Auth/start"), "signed_out", "sign-in page"),
        (Seen(True, url=f"{ORIGIN}/home", password=True), "signed_out", "asked for a password"),
        (Seen(False, why="the page did not finish loading"), "unknown", "could not reach"),
        (Seen(True, url=f"{ORIGIN}/authors/mira"), "signed_in", "opened without asking"),
        (Seen(True, url="https://studio.sunbeam-club.example/home"), "signed_out", "a different site"),
    ],
)
def test_the_looks_decision_table(seen: Seen, access: str, words: str) -> None:
    got, reason = decide(ORIGIN, seen)
    assert got == access and words in reason


def test_a_look_with_no_browser_changes_nothing_and_a_fresh_look_is_not_repeated(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Channel"})["id"]
    daemon.sites.add(space, ORIGIN, "Fixture", f"{ORIGIN}/account", "A chore")
    assert sites.check(daemon, space, ORIGIN, force=True)["access"] == "unknown"
    assert "checked_at" not in daemon.sites.get(space, ORIGIN)
    events = heard(daemon)
    with FakeShell(daemon.relay) as shell:
        assert sites.check(daemon, space, ORIGIN)["access"] == "signed_in"
        assert sites.check(daemon, space, ORIGIN)["access"] == "signed_in"
        assert len([c for c in shell.calls if c["hand"] == "open"]) == 1  # the second stood on the first
        shell.refuse["open"] = {"ok": False, "reason": "timeout", "output": "the page did not finish loading"}
        unreachable = sites.check(daemon, space, ORIGIN, force=True)
        assert unreachable["access"] == "unknown" and "could not reach" in unreachable.get("reason", "")
    assert [(e["type"], e["site"]["access"]) for e in events] == [("site", "signed_in"), ("site", "unknown")]


# --- the sketch's real sites -----------------------------------------------------------------------


def _node(node_id: str, kind: str = "app", slot: str = "apps", **more: Any) -> dict[str, Any]:
    return {"id": node_id, "kind": kind, "slot": slot, "label": "The club", "origin": "athena", **more}


def test_a_site_is_her_pencil_on_an_app_node_until_the_person_confirms_it() -> None:
    mine = _node("a", origin="you", confirmed=True)
    ops: list[Any] = [{"op": "add", "node": mine}, {"op": "add", "node": _node("b", site={"url": OTHER})}]
    sketch, _ = apply({"nodes": [], "edges": []}, ops)
    assert sketch["nodes"][1]["site"] == {
        "origin": OTHER,
        "url": OTHER + "/",
        "label": "The club",
        "confirmed": False,
    }
    # On the person's own node a site is still her proposal: the node keeps its ink.
    sketch, _ = apply(
        sketch, [{"op": "change", "node": cast("Any", {"id": "a", "site": {"url": f"{OTHER}/me"}})}]
    )
    a = sketch["nodes"][0]
    assert a["confirmed"] is True and a["site"]["confirmed"] is False and a["site"]["url"] == f"{OTHER}/me"
    inked, applied = confirm(sketch, ["a", "b"])
    assert all(n["site"]["confirmed"] for n in inked["nodes"]) and len(applied) == 2
    rubbed, applied = drop(sketch, ["a"])  # on an agreed node only the pencilled site goes
    assert "site" not in rubbed["nodes"][0] and applied[0]["op"] == "change"
    with pytest.raises(SketchError, match="agreed"):
        drop(inked, ["a"])
    with pytest.raises(SketchError, match="an app"):
        apply(sketch, [{"op": "add", "node": cast("Any", _node("c", "step", "steps", site={"url": OTHER}))}])
    with pytest.raises(SketchError, match="http"):
        apply(sketch, [{"op": "add", "node": cast("Any", _node("d", site={"url": "ftp://x.example"}))}])


# --- the access step -------------------------------------------------------------------------------


def to_verdict(client: TestClient, daemon: Daemon, sited: dict[str, str]) -> Draft:
    """A draft at its verdict whose app nodes carry confirmed sites: node id -> address."""
    draft = to_rehearse(client, daemon)
    lines(client.post(f"/drafts/{draft['id']}/rehearse", headers=H))
    stored = daemon.drafts.get(draft["id"])
    for node in stored["sketch"]["nodes"]:
        if node["id"] in sited:
            node["site"] = {"origin": sited[node["id"]], "url": sited[node["id"]] + "/account"}
            node["site"].update(label=node["label"], confirmed=True)
    return daemon.drafts.put(stored)


def keep(client: TestClient, draft: Draft) -> dict[str, Any]:
    r = client.post(f"/drafts/{draft['id']}/verdict", json={"verdict": "keep"}, headers=H)
    assert r.status_code == 200, r.text
    return dict(r.json())


def act(client: TestClient, draft: dict[str, Any], origin: str, what: str) -> Any:
    return client.post(f"/drafts/{draft['id']}/access", json={"origin": origin, "act": what}, headers=H)


def test_a_chore_with_no_real_site_skips_the_access_step(
    client: TestClient, daemon: Daemon, fake: Fake
) -> None:
    kept = keep(client, to_verdict(client, daemon, {}))
    assert kept["step"] == "saved" and "sites" not in kept
    assert daemon.sites.list(kept["space_id"]) == []


def test_a_pencilled_site_is_not_taken_to_access() -> None:
    sketch = cast("Sketch", {"nodes": [_node("a", confirmed=True, site={"origin": OTHER, "url": OTHER})]})
    sketch["nodes"][0]["site"]["label"], sketch["nodes"][0]["site"]["confirmed"] = "x", False
    assert access.confirmed_sites(sketch) == []


def test_keep_makes_the_confirmed_sites_the_projects_and_opens_the_access_step(
    client: TestClient, daemon: Daemon, fake: Fake
) -> None:
    events = heard(daemon)
    kept = keep(client, to_verdict(client, daemon, {"n2": ORIGIN, "n3": OTHER}))
    assert kept["step"] == "access"
    assert [(s["origin"], s["state"]) for s in kept["sites"]] == [(ORIGIN, "open"), (OTHER, "open")]
    listed = daemon.sites.list(kept["space_id"])
    assert [(s["origin"], s["access"]) for s in listed] == [(ORIGIN, "unknown"), (OTHER, "unknown")]
    assert listed[0]["blocks"] == ["Club invoice check"] and listed[0]["probe_url"] == f"{ORIGIN}/account"
    assert daemon.sites.trusted(kept["space_id"], ORIGIN)
    assert [e["site"]["origin"] for e in events if e["type"] == "site"] == [ORIGIN, OTHER]
    assert act(client, kept, "https://nowhere.example", "check").status_code == 404
    assert act(client, kept, ORIGIN, "dance").status_code == 400


def test_sign_in_check_retry_skip_and_all_done(client: TestClient, daemon: Daemon, fake: Fake) -> None:
    kept = keep(client, to_verdict(client, daemon, {"n2": ORIGIN, "n3": OTHER}))
    assert "not open" in act(client, kept, ORIGIN, "check").json()["reason"]  # no browser yet
    with FakeShell(daemon.relay) as shell:
        shell.pages[f"{ORIGIN}/account"] = {"final": f"{ORIGIN}/signin", "password": True}
        r = act(client, kept, ORIGIN, "sign_in")
        assert r.status_code == 200, r.text
        tab = r.json()["sites"][0]["tab"]
        wheel = next(c for c in shell.calls if c["hand"] == "wheel")
        assert wheel["tab"] == tab and "never sees your password" in wheel["args"]["say"]
        assert shell.tabs[tab]["hidden"] is False
        # The person has not signed in yet: the look sees the sign-in page; the site stays open.
        tried = act(client, kept, ORIGIN, "check").json()
        assert tried["step"] == "access" and tried["sites"][0]["state"] == "open"
        assert "sign-in page" in tried["sites"][0]["reason"]
        # They sign in: the site now opens on its own page with no password field.
        shell.pages[f"{ORIGIN}/account"] = {"final": f"{ORIGIN}/account"}
        done = act(client, kept, ORIGIN, "check").json()
        assert done["sites"][0]["state"] == "signed_in" and "tab" not in done["sites"][0]
        assert done["step"] == "access"
        skipped = act(client, kept, OTHER, "skip").json()
    assert skipped["step"] == "saved"
    assert [s["state"] for s in skipped["sites"]] == ["signed_in", "skipped"]
    by = {s["origin"]: s for s in daemon.sites.list(kept["space_id"])}
    assert by[ORIGIN]["access"] == "signed_in" and by[OTHER]["access"] == "signed_out"
    assert "skipped" in by[OTHER].get("reason", "")
    assert act(client, kept, ORIGIN, "check").status_code == 400  # the step is over


def test_a_move_to_another_site_is_caught_in_onboarding_and_that_site_used_instead(
    client: TestClient, daemon: Daemon, fake: Fake
) -> None:
    """Owner, 2026-10-31: a sign-in that ends on another address of the same company is caught while
    the chore is set up, and the site it moved to becomes the trusted one."""
    studio = "https://studio.sunbeam-club.example"
    kept = keep(client, to_verdict(client, daemon, {"n2": ORIGIN}))
    with FakeShell(daemon.relay) as shell:
        shell.pages[f"{ORIGIN}/account"] = {"final": f"{studio}/channel"}
        moved = act(client, kept, ORIGIN, "check").json()["sites"][0]
        assert moved["state"] == "open" and moved["moved_to"] == f"{studio}/channel"
        assert "a different site" in moved["reason"]
        used = act(client, kept, ORIGIN, "use_moved").json()
        assert [(s["origin"], s["state"]) for s in used["sites"]] == [(studio, "open")]
        assert not daemon.sites.trusted(kept["space_id"], ORIGIN)
        assert daemon.sites.trusted(kept["space_id"], studio)
        assert daemon.sites.get(kept["space_id"], studio)["blocks"] == ["Club invoice check"]
        shell.pages[f"{studio}/channel"] = {"final": f"{studio}/channel"}
        done = act(client, kept, studio, "check").json()
    assert done["step"] == "saved" and done["sites"][0]["state"] == "signed_in"
    assert act(client, kept, studio, "use_moved").status_code == 400  # the step is over


def test_use_moved_needs_a_move(client: TestClient, daemon: Daemon, fake: Fake) -> None:
    kept = keep(client, to_verdict(client, daemon, {"n2": ORIGIN}))
    r = act(client, kept, ORIGIN, "use_moved")
    assert r.status_code == 400 and "did not end on another site" in r.json()["reason"]


def test_before_the_step_ends_every_signed_in_site_is_checked_again(
    client: TestClient, daemon: Daemon, fake: Fake
) -> None:
    """A sign-in on one site can sign her out of another: the last site done checks them all."""
    kept = keep(client, to_verdict(client, daemon, {"n2": ORIGIN, "n3": OTHER}))
    with FakeShell(daemon.relay) as shell:
        shell.pages[f"{ORIGIN}/account"] = {"final": f"{ORIGIN}/account"}
        shell.pages[f"{OTHER}/account"] = {"final": f"{OTHER}/signin", "password": True}
        assert act(client, kept, ORIGIN, "check").json()["sites"][0]["state"] == "signed_in"
        # Signing in to the second site signs her out of the first.
        shell.pages[f"{OTHER}/account"] = {"final": f"{OTHER}/account"}
        shell.pages[f"{ORIGIN}/account"] = {"final": f"{ORIGIN}/signin", "password": True}
        again = act(client, kept, OTHER, "check").json()
        assert again["step"] == "access"
        first = again["sites"][0]
        assert first["state"] == "open" and first["reason"].startswith("After the last sign-in")
        shell.pages[f"{ORIGIN}/account"] = {"final": f"{ORIGIN}/account"}
        done = act(client, kept, ORIGIN, "check").json()
    assert done["step"] == "saved" and [s["state"] for s in done["sites"]] == ["signed_in", "signed_in"]


def test_the_access_step_never_takes_a_password(client: TestClient, daemon: Daemon, fake: Fake) -> None:
    kept = keep(client, to_verdict(client, daemon, {"n2": ORIGIN}))
    r = client.post(
        f"/drafts/{kept['id']}/access", json={"origin": ORIGIN, "act": "check", "password": "x"}, headers=H
    )
    stored = daemon.store.query("SELECT * FROM drafts WHERE id = ?", (kept["id"],))[0]
    assert "password" not in str(dict(stored)).replace("never sees your password", "")
    assert r.status_code in (200, 400)


# --- the overview's routes -------------------------------------------------------------------------


def test_the_overview_lists_sites_looks_again_and_signs_in_again(client: TestClient, daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Club"})["id"]
    daemon.sites.add(space, ORIGIN, "Fixture", f"{ORIGIN}/account", "Club invoice check")
    listed = client.get(f"/spaces/{space}/sites", headers=H).json()["sites"]
    assert [s["access"] for s in listed] == ["unknown"]
    assert client.post(f"/spaces/{space}/sites/check", json={"origin": OTHER}, headers=H).status_code == 404
    with FakeShell(daemon.relay) as shell:
        shell.pages[f"{ORIGIN}/account"] = {"final": f"{ORIGIN}/signin", "password": True}
        lapsed = client.post(f"/spaces/{space}/sites/check", json={"origin": ORIGIN}, headers=H).json()
        assert lapsed["access"] == "signed_out"
        started = client.post(f"/spaces/{space}/sites/sign_in", json={"origin": ORIGIN}, headers=H).json()
        assert started["origin"] == ORIGIN and any(c["hand"] == "wheel" for c in shell.calls)
        shell.pages[f"{ORIGIN}/account"] = {"final": f"{ORIGIN}/account"}
        back = client.post(f"/spaces/{space}/sites/check", json={"origin": ORIGIN}, headers=H).json()
        assert back["access"] == "signed_in"
    assert client.get("/spaces/spc_000000000000/sites", headers=H).status_code == 404


def test_opening_the_overview_looks_again_only_at_stale_sites(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Club"})["id"]
    trust(daemon, space)
    daemon.sites.add(space, OTHER, "Club", f"{OTHER}/account", "Club invoice check")
    with FakeShell(daemon.relay) as shell:
        assert sites.refresh(daemon, space) == 1
        for _ in range(200):
            if daemon.sites.get(space, OTHER).get("checked_at"):
                break
            threading_wait()
        assert [c["args"]["url"] for c in shell.calls if c["hand"] == "open"] == [f"{OTHER}/account"]
    assert sites.refresh(daemon, space) == 0  # no browser, no look


def threading_wait() -> None:
    import threading

    threading.Event().wait(0.01)


def test_sign_in_needs_her_browser(daemon: Daemon) -> None:
    space = daemon.spaces.create({"name": "Club"})["id"]
    trust(daemon, space)
    with pytest.raises(ApiError, match="not open"):
        sites.sign_in(daemon, space, ORIGIN)
