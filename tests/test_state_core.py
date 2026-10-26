"""Spaces, the memory wall, erase, the gate, the ledger, conversation, settings, events."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import pytest

from athena.app import Daemon
from athena.contracts import Card
from athena.errors import ApiError
from athena.spaces import normalise_origin


def _bad(fn: Any, *a: Any, **k: Any) -> ApiError:
    with pytest.raises(ApiError) as e:
        fn(*a, **k)
    return e.value


# --- spaces ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("https://x.com", "https://x.com"),
        ("https://x.com:443", "https://x.com"),
        ("http://x.com:80/", "http://x.com"),
        ("HTTPS://Example.COM", "https://example.com"),
        ("http://localhost:1420", "http://localhost:1420"),
        ("https://x.com:8443", "https://x.com:8443"),
    ],
)
def test_origin_accepted(raw: str, want: str) -> None:
    assert normalise_origin(raw) == want


@pytest.mark.parametrize(
    "raw",
    [
        "ftp://x.com",
        "x.com",
        "https://x.com/path",
        "https://x.com/?q=1",
        "https://x.com#frag",
        "https://user:pw@x.com",
        "https://user@x.com",
        "https://",
        "https://x.com:notaport",
        "javascript:alert(1)",
    ],
)
def test_origin_refused(raw: str) -> None:
    assert _bad(normalise_origin, raw).error == "bad_request"


def test_name_folds_whitespace_and_caps_refuse(daemon: Daemon) -> None:
    assert daemon.spaces.create({"name": "  Big   Launch \n"})["name"] == "Big Launch"
    assert daemon.spaces.create({"name": "x" * 60})["name"] == "x" * 60
    assert "name" in _bad(daemon.spaces.create, {"name": "x" * 61}).reason
    assert _bad(daemon.spaces.create, {"name": "   "}).error == "bad_request"
    assert _bad(daemon.spaces.create, {}).error == "bad_request"


def test_brief_cap_refused_not_cut(daemon: Daemon) -> None:
    assert len(daemon.spaces.create({"name": "a", "brief": "b" * 1600})["brief"]) == 1600
    assert "brief" in _bad(daemon.spaces.create, {"name": "a", "brief": "b" * 1601}).reason
    assert len(daemon.spaces.list()) == 1


def test_apps_cap_refused_and_deduped(daemon: Daemon) -> None:
    sp = daemon.spaces.create({"name": "a", "apps": ["https://x.com", "https://X.com:443"]})
    assert sp["apps"] == ["https://x.com"]
    ok = [f"https://a{i}.com" for i in range(24)]
    assert len(daemon.spaces.create({"name": "b", "apps": ok})["apps"]) == 24
    assert "apps" in _bad(daemon.spaces.create, {"name": "c", "apps": [*ok, "https://more.com"]}).reason


def test_hue_cap_and_default(daemon: Daemon) -> None:
    assert daemon.spaces.create({"name": "a", "hue": 359})["hue"] == 359
    assert _bad(daemon.spaces.create, {"name": "a", "hue": 360}).error == "bad_request"
    assert _bad(daemon.spaces.create, {"name": "a", "hue": -1}).error == "bad_request"
    assert _bad(daemon.spaces.create, {"name": "a", "hue": True}).error == "bad_request"
    sp = daemon.spaces.create({"name": "b"})
    assert sp["hue"] == int(sp["id"][4:], 16) % 360


def test_101st_space_refused(daemon: Daemon) -> None:
    for i in range(100):
        daemon.spaces.create({"name": f"p{i}"})
    assert "100" in _bad(daemon.spaces.create, {"name": "one too many"}).reason
    assert len(daemon.spaces.list()) == 100


def test_update_touches_updated_and_orders_list(daemon: Daemon) -> None:
    a = daemon.spaces.create({"name": "a"})
    b = daemon.spaces.create({"name": "b"})
    assert [s["id"] for s in daemon.spaces.list()] == [b["id"], a["id"]]
    daemon.store.run("UPDATE spaces SET updated = '2000-01-01T00:00:00Z'")
    out = daemon.spaces.update(a["id"], {"brief": "new"})
    assert out["brief"] == "new"
    assert out["updated"] > "2000-01-01T00:00:00Z"
    assert daemon.spaces.list()[0]["id"] == a["id"]
    assert _bad(daemon.spaces.update, "spc_nope", {"name": "x"}).error == "unknown_ref"


def test_exists(daemon: Daemon) -> None:
    sp = daemon.spaces.create({"name": "a"})
    assert daemon.spaces.exists("") and daemon.spaces.exists(sp["id"]) and not daemon.spaces.exists("spc_x")


# --- the wall -------------------------------------------------------------------------------------


def test_wall_visibility(daemon: Daemon) -> None:
    a = daemon.spaces.create({"name": "A"})["id"]
    b = daemon.spaces.create({"name": "B"})["id"]
    daemon.memory.write_fact(a, "the launch codename is Heron")
    daemon.memory.write_fact("", "the person prefers tea")
    assert [r["line"] for r in daemon.memory.recall(a, "heron")] == ["the launch codename is Heron"]
    assert daemon.memory.recall(b, "heron") == []
    assert daemon.memory.recall("", "heron") == []
    for view in (a, b, ""):
        assert len(daemon.memory.recall(view, "tea")) == 1
    assert daemon.memory.kept(a)[0]["line"].endswith("Heron")
    assert daemon.memory.kept(b) == []


def test_recall_query_hardening(daemon: Daemon) -> None:
    daemon.memory.write_fact("", "alpha beta")
    assert daemon.memory.recall("", "") == []
    assert daemon.memory.recall("", '"*()-:') == []
    assert len(daemon.memory.recall("", 'alpha OR "NEAR(" nothing')) == 1


def test_make_core_moves_fact_and_refuses_episode(daemon: Daemon) -> None:
    a = daemon.spaces.create({"name": "A"})["id"]
    b = daemon.spaces.create({"name": "B"})["id"]
    fact = daemon.memory.write_fact(a, "likes herons")
    ep = daemon.memory.append_episode(a, "talked about herons")
    assert _bad(daemon.memory.make_core, a, ep["id"]).error == "bad_request"
    assert _bad(daemon.memory.make_core, b, fact["id"]).error == "unknown_ref"
    assert _bad(daemon.memory.make_core, "", fact["id"]).error == "unknown_ref"
    assert _bad(daemon.memory.make_core, a, "mem_nope").error == "unknown_ref"
    moved = daemon.memory.make_core(a, fact["id"])
    assert moved["space_id"] == ""
    assert len(daemon.memory.recall(b, "herons")) == 1  # now core: visible everywhere
    assert daemon.memory.counts(a) == {"episodes": 1, "facts": 0}


def test_memory_page_line_and_forget(daemon: Daemon) -> None:
    a = daemon.spaces.create({"name": "A"})["id"]
    row = daemon.memory.write_fact(a, "word  " * 100)
    assert len(row["line"]) == 240 and row["line"].endswith("…") and "\n" not in row["line"]
    for i in range(3):
        daemon.memory.append_episode(a, f"e{i}")
    page = daemon.memory.page(a, None, 2)
    assert (page["showing"], page["total"]) == (2, 4)
    assert page["rows"][0]["line"] == "e2"
    assert daemon.memory.page(a, "fact", 10)["total"] == 1
    assert daemon.memory.page("", None, 10)["total"] == 0
    daemon.memory.forget(row["id"])
    assert _bad(daemon.memory.forget, row["id"]).error == "unknown_ref"
    assert daemon.memory.recall(a, "word") == []  # the index forgot too


# --- erase ----------------------------------------------------------------------------------------


def test_erase_removes_everything_and_resets_active(daemon: Daemon) -> None:
    a = daemon.spaces.create({"name": "A"})["id"]
    other = daemon.spaces.create({"name": "O"})["id"]
    daemon.memory.write_fact(a, "fact")
    daemon.memory.append_episode(a, "ep one")
    daemon.memory.append_episode(a, "ep two")
    daemon.memory.write_fact(other, "keep me")
    daemon.conversation.append(a, "person", "hi")
    daemon.conversation.append(a, "athena", "hello")
    daemon.conversation.append(other, "person", "stay")
    daemon.gate.file(a, "add_app", {"origin": "https://x.com"}, "add")
    daemon.gate.file(other, "add_app", {"origin": "https://y.com"}, "add")
    daemon.settings.set("active_space_id", a)
    assert daemon.active_space() == a
    out = daemon.spaces.erase(a)
    assert out == {"id": a, "episodes": 2, "facts": 1, "turns": 2}
    assert daemon.settings.active_space() == ""
    assert not daemon.spaces.exists(a)
    assert daemon.memory.counts(a) == {"episodes": 0, "facts": 0}
    assert daemon.conversation.list(a) == []
    assert [c["space_id"] for c in daemon.gate.list()] == [other]
    assert daemon.memory.counts(other)["facts"] == 1
    assert len(daemon.conversation.list(other)) == 1


def test_erase_core_or_unknown_refused(daemon: Daemon) -> None:
    assert _bad(daemon.spaces.erase, "").error == "unknown_ref"
    assert _bad(daemon.spaces.erase, "spc_nope").error == "unknown_ref"


def test_erase_busy_while_turn_held(daemon: Daemon) -> None:
    a = daemon.spaces.create({"name": "A"})["id"]
    with daemon.busy.turn(a):
        assert _bad(daemon.spaces.erase, a).error == "space_busy"
    assert daemon.spaces.exists(a)
    daemon.spaces.erase(a)


# --- gate -----------------------------------------------------------------------------------------


def test_card_resolves_exactly_once_under_race(daemon: Daemon) -> None:
    calls: list[str] = []
    daemon.gate.set_executor(lambda card: calls.append(card["id"]) or "done")
    card = daemon.gate.file("", "add_app", {"origin": "https://x.com"}, "add x")
    barrier = threading.Barrier(2)
    results: list[object] = []

    def go() -> None:
        barrier.wait()
        try:
            results.append(daemon.gate.resolve(card["id"], "approve"))
        except ApiError as e:
            results.append(e)

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    won = [r for r in results if not isinstance(r, ApiError)]
    lost = [r for r in results if isinstance(r, ApiError)]
    assert len(won) == 1 and len(lost) == 1
    assert lost[0].error == "bad_request" and lost[0].reason == "already decided"
    assert calls == [card["id"]]
    assert daemon.gate.get(card["id"])["state"] == "approved"


def test_gate_decline_no_executor_and_unknown(daemon: Daemon) -> None:
    ran: list[Card] = []
    daemon.gate.set_executor(lambda c: ran.append(c) or "x")
    c1 = daemon.gate.file("", "forget", {}, "forget it")
    out = daemon.gate.resolve(c1["id"], "decline")
    assert out["state"] == "declined" and "resolved" in out and ran == []
    assert _bad(daemon.gate.resolve, "card_nope", "approve").error == "unknown_ref"
    assert _bad(daemon.gate.get, "card_nope").error == "unknown_ref"
    fresh = Daemon.open(None)
    c2 = fresh.gate.file("", "forget", {}, "x")
    assert fresh.gate.resolve(c2["id"], "approve")["state"] == "approved"  # no executor: still resolves


def test_gate_list_filters_newest_first(daemon: Daemon) -> None:
    c1 = daemon.gate.file("", "forget", {}, "one")
    c2 = daemon.gate.file("", "forget", {}, "two")
    daemon.gate.resolve(c1["id"], "approve")
    assert [c["id"] for c in daemon.gate.list()] == [c2["id"], c1["id"]]
    assert [c["id"] for c in daemon.gate.list("waiting")] == [c2["id"]]
    assert "resolved" not in daemon.gate.get(c2["id"])


# --- ledger, conversation, settings ---------------------------------------------------------------


def test_ledger_rows_and_totals(daemon: Daemon) -> None:
    empty = daemon.ledger.page(10)
    assert empty["totals"] == {"calls": 0, "cost_usd": 0.0, "cost_estimated": False}
    unpriced = daemon.ledger.record(
        surface="probe", space_id="", engine="scripted", model="m", latency_ms=3, ok=True
    )
    assert "cost_usd" not in unpriced and "error" not in unpriced and unpriced["ok"] is True
    daemon.ledger.record(
        surface="turn", space_id="", engine="muse", model="m", latency_ms=9, ok=True,
        input_tokens=10, output_tokens=5, cost_usd=0.25, cost_estimated=True,
    )  # fmt: skip
    daemon.ledger.record(
        surface="turn",
        space_id="",
        engine="muse",
        model="m",
        latency_ms=9,
        ok=False,
        error="boom",
        cost_usd=0.5,
    )
    page = daemon.ledger.page(2)
    assert len(page["rows"]) == 2 and page["rows"][0]["error"] == "boom"
    assert page["totals"] == {"calls": 3, "cost_usd": 0.75, "cost_estimated": True}


def test_conversation_last_n_oldest_first(daemon: Daemon) -> None:
    for i in range(5):
        daemon.conversation.append("", "person", f"m{i}")
    t = daemon.conversation.append("", "athena", "r", cost_usd=0.01, card_id="card_1")
    assert t["cost_usd"] == 0.01 and t["card_id"] == "card_1"
    assert [x["text"] for x in daemon.conversation.list("", 3)] == ["m3", "m4", "r"]
    assert "cost_usd" not in daemon.conversation.list("", 6)[0]
    assert daemon.conversation.erase_space("") == 6


def test_settings(daemon: Daemon) -> None:
    assert daemon.settings.get("k", "dflt") == "dflt"
    daemon.settings.set("k", "v1")
    daemon.settings.set("k", "v2")
    assert daemon.settings.get("k") == "v2"
    assert daemon.settings.active_space() == ""


def test_active_space_fails_closed(daemon: Daemon) -> None:
    a = daemon.spaces.create({"name": "A"})["id"]
    daemon.settings.set("active_space_id", a)
    daemon.store.run("DELETE FROM spaces")
    assert daemon.active_space() == ""


def test_store_migrate_idempotent_and_rollback(daemon: Daemon) -> None:
    daemon.store.migrate()
    assert daemon.store.query("SELECT value FROM meta WHERE key = 'schema_version'")[0][0] == "1"
    with pytest.raises(RuntimeError), daemon.store.tx() as db:
        db.execute("INSERT INTO settings(key, value) VALUES ('x', 'y')")
        raise RuntimeError
    assert daemon.settings.get("x", "gone") == "gone"


# --- events ---------------------------------------------------------------------------------------


def test_events_reach_subscriber_from_a_thread(daemon: Daemon) -> None:
    async def main() -> list[Any]:
        it = daemon.events.subscribe()
        first = asyncio.ensure_future(anext(it))
        await asyncio.sleep(0.05)  # subscriber registers on first iteration
        threading.Thread(
            target=daemon.events.publish, args=({"type": "active_space", "space_id": "s"},)
        ).start()
        got = [await asyncio.wait_for(first, 2)]
        await it.aclose()  # type: ignore[attr-defined]
        return got

    assert asyncio.run(main()) == [{"type": "active_space", "space_id": "s"}]
    assert daemon.events._subs == []  # unregistered on close


def test_events_full_queue_drops_for_that_subscriber_only(daemon: Daemon) -> None:
    async def main() -> tuple[int, int]:
        slow = daemon.events.subscribe()
        fast = daemon.events.subscribe()
        t1, t2 = asyncio.ensure_future(anext(slow)), asyncio.ensure_future(anext(fast))
        await asyncio.sleep(0.05)
        for i in range(300):
            daemon.events.publish({"type": "active_space", "space_id": str(i)})
            if i % 50 == 0:
                await asyncio.sleep(0)
        await asyncio.sleep(0.05)
        await t1
        await t2
        n1 = 1
        while daemon.events._subs[0][1].qsize():
            await anext(slow)
            n1 += 1
        return n1, 300

    n, _ = asyncio.run(main())
    assert n <= 257  # bounded: 1 taken + at most 256 queued
