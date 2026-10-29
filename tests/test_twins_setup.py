"""Setting a twin up with Athena on the scripted engine (ADR 0010): the prototype's staged answers give
the prototype's coverage and readiness frame by frame, ready from frame 9; ink is proven by a quote;
the slips make the person's pieces; the sent mail keeps only its excerpt; a chore whose tool is not
connected cannot be picked; and erasing the Project erases the twin whole."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from athena import contracts
from athena.app import Daemon
from athena.contracts import TwinDetail, TwinPage
from athena.engine.scripted import TWIN_SETUP, TWIN_VOICE
from athena.store import TWIN_TABLES
from athena.twins import panels, setup
from athena.twins.rubric import TWIN_RUBRIC
from connectors_kit import BANNED, conforms
from twins_kit import FRAMES, NEED, SENT, World, prototype


@pytest.fixture
def world(daemon: Daemon, client: TestClient) -> World:
    return World(daemon, client)


def of(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e for e in events if e["type"] == kind]


def test_the_twin_rubric_is_the_prototypes() -> None:
    places = prototype()["places"]
    assert list(TWIN_RUBRIC.places) == [p["id"] for p in places]
    assert dict(TWIN_RUBRIC.required) == {p["id"]: p["required"] for p in places}
    assert setup.RULES.startswith(TWIN_SETUP) and panels.VOICE_RULES.startswith(TWIN_VOICE)


def test_the_staged_setup_matches_the_prototype_frame_by_frame(world: World) -> None:
    twin_id = world.create()
    after = world.play(twin_id)
    assert len(after) == len(FRAMES) == 12
    for i, (got, want) in enumerate(zip(after, FRAMES, strict=True)):
        assert got["coverage"] == want["coverage"], i
        assert (got["ready"], got["readiness"]) == (want["ready"], want["readiness"]), i
    assert [t["ready"] for t in after].index(True) == prototype()["setup"]["first_ready_frame"] == 9
    for twin in after:
        conforms(twin, TwinDetail)
    last = after[-1]
    assert last["name"] == "Partnerships" and last["purpose"].startswith("I want a twin that writes")
    assert [c["kind"] for c in last["channels"]] == ["gmail", "notion"]
    gmail = last["channels"][0]
    assert gmail["status"] == "connected" and gmail["split"] == {"first_message": "assist", "reply": "auto"}
    assert "ask" not in last  # the last frame asks nothing: the rehearsal starts
    # the setup's model calls are ledgered on the twin's surface, in its Project
    rows = world.daemon.ledger.page(500)["rows"]
    assert (
        rows
        and {r["surface"] for r in rows} == {"twin"}
        and {r["space_id"] for r in rows} == {last["space_id"]}
    )


def test_each_reply_streams_the_twins_own_lines(world: World) -> None:
    twin_id = world.create()
    events = world.say(twin_id, NEED)
    assert events[0]["type"] == "start" and events[0]["simulated"] is True and events[-1]["type"] == "done"
    pieces = [op["piece"] for e in of(events, "sketch") for op in e["ops"]]
    for p in pieces:
        conforms(p, contracts.Piece)
    assert [(p["id"], p["place"], p["origin"], p["confirmed"]) for p in pieces] == [
        ("p_name", "who", "athena", False),
        ("p_purpose", "who", "you", True),
        ("p_mtype", "mission", "athena", False),
    ]
    assert pieces[1]["quote"] == " ".join(NEED.split()[:8])
    (ask,) = [e["ask"] for e in of(events, "ask")]
    conforms(ask, contracts.TwinAsk)
    assert ask["place"] == "who" and "panel" not in ask and ask["follow_up"] == 0
    (cov,) = of(events, "coverage")
    assert (cov["readiness"], cov["ready"]) == (14, False) and cov["coverage"]["mission"] == 0.5

    # her next question opens the Google sign-in slip
    events = world.say(twin_id, choice="As me, from my studio")
    (ask,) = [e["ask"] for e in of(events, "ask")]
    assert (ask["place"], ask["panel"], ask["channel"]) == ("channels", "connect", "gmail")
    assert world.get(twin_id)["ask"] == ask  # kept, so a reopened setup shows it


def test_ink_is_proven_by_the_persons_words(world: World) -> None:
    twin_id = world.create()
    world.say(twin_id, NEED)
    events = world.say(twin_id, choice="As me, from my studio")
    sign = next(op["piece"] for e in of(events, "sketch") for op in e["ops"] if op["piece"]["id"] == "p_sign")
    assert (sign["origin"], sign["confirmed"], sign["quote"]) == ("you", True, "As me, from my studio")
    # a choice too short to prove anything stays her pencil
    other = World(world.daemon, world.client)
    second = other.create()
    other.say(second, NEED)
    events = other.say(second, choice="Me")
    sign = next(op["piece"] for e in of(events, "sketch") for op in e["ops"] if op["piece"]["id"] == "p_sign")
    assert (sign["origin"], sign["confirmed"]) == ("athena", False) and "quote" not in sign


def test_a_channel_is_inked_by_connecting_it_never_by_a_confirm(world: World) -> None:
    twin_id = world.create()
    world.say(twin_id, NEED)
    world.say(twin_id, choice="As me, from my studio")
    refused = world.post(twin_id, "twin_confirm", {"pieces": ["p_gmail"]}, status=400)
    assert "connect" in refused["reason"]
    world.connect_gmail()
    events = world.say(twin_id, choice="Sign in with Google")
    inked = of(events, "sketch")[0]["ops"][0]["piece"]  # right after start, before her reply
    assert events[1]["type"] == "sketch"
    assert (inked["id"], inked["origin"], inked["confirmed"], inked["detail"]) == (
        "p_gmail",
        "you",
        True,
        "me@example.test",
    )
    (ask,) = [e["ask"] for e in of(events, "ask")]
    assert ask["panel"] == "samples"
    twin = world.get(twin_id)
    assert twin["channels"] == [
        {
            "kind": "gmail",
            "account": "me@example.test",
            "status": "connected",
            "autonomy": "assist",
            "bar": 80,
        }
    ]
    # the samples slip was readied when her question opened it
    assert [s["id"] for s in twin["samples"]] == [m[0] for m in SENT]


def test_her_pieces_cannot_claim_what_a_slip_decides(world: World, daemon: Daemon) -> None:
    from athena.engine import ToolCall
    from athena.twins.setup import TwinDesign

    twin_id = world.create()
    world.say(twin_id, NEED)
    design = TwinDesign(daemon, twin_id)

    def sketch(**args: str) -> str:
        return design.call(ToolCall("c", "sketch", args))[0]

    assert "fills from the working slip" in sketch(
        op="add", place="autonomy", kind="line", label="Gmail: Auto"
    )
    assert "fills from the working slip" in sketch(op="add", place="memory", kind="line", label="Likes cats")
    assert "voice is learned only" in sketch(op="add", place="voice", kind="line", label="Writes warmly")
    assert "Not set" in sketch(op="dial", dial="warmth", value="5", quote="be warmer please")
    added = sketch(op="add", place="channels", kind="gmail", label="Gmail", quote=" ".join(NEED.split()[:8]))
    assert "your proposal" in added  # a quote never inks a channel
    assert design.sketch["nodes"][-1]["origin"] == "athena"


def test_samples_keep_only_their_excerpt_and_learn_the_voice(world: World, daemon: Daemon) -> None:
    twin_id = world.create()
    world.connect_gmail()
    twin = world.post(twin_id, "twin_samples", {"ids": ["s1", "s3"]})
    samples = {s["id"]: s for s in twin["samples"]}
    for s in samples.values():
        conforms(s, contracts.Sample)
    assert [k for k, s in samples.items() if s["suggest"]] == ["s1", "s2", "s3", "s4"]
    assert samples["s5"]["why_not"] == "A forward, not your own writing"
    assert samples["s6"]["why_not"] == "Written to your own team, not to someone outside"
    long_mail = SENT[0][4]
    assert samples["s1"]["words"] == len(long_mail.split())  # counted on the whole mail, the quote left out
    assert len(samples["s1"]["excerpt"]) <= 200 < len(long_mail)
    stored = "".join(r[0] for r in daemon.store.query("SELECT body FROM twin_samples"))
    assert long_mail not in stored and TAIL_PART not in stored
    every_table = "".join(
        str(tuple(r)) for t in TWIN_TABLES for r in daemon.store.query(f"SELECT * FROM {t}")
    )
    assert long_mail[-120:] not in every_table
    # her voice, in pencil, each piece naming the picked samples it shows in
    voice = [p for p in twin["pieces"] if p["place"] == "voice"]
    assert voice and all(p["origin"] == "athena" and not p["confirmed"] for p in voice)
    assert all(set(p["evidence"]) <= {"s1", "s3"} and p["evidence"] for p in voice)
    learned = {d["id"]: (d["value"], d["source"]) for d in twin["dials"]}
    assert learned["warmth"] == (4, "learned") and learned["detail"][1] == "preset"
    facts = {f["fact"]: f for f in twin["memory"]}
    money = facts["You once offered $50 for a track"]
    assert money["suggest"] == "drop" and money["reason"] == "A promise of money; it must never make one"
    assert (
        facts["You make a free visualizer in exchange for a credit"]["from"]
        == "Your mail to Mira Soleil, 3 Mar"
    )
    # a forward is shown and cannot be picked
    refused = world.post(twin_id, "twin_samples", {"ids": ["s5"]}, status=400)
    assert "forward" in refused["reason"]


TAIL_PART = "I write to the people behind them. I keep a running list"


def test_dials_and_presets(world: World) -> None:
    twin_id = world.create()
    twin = world.post(twin_id, "twin_dials", {"dials": {"warmth": 5}})
    dials = {d["id"]: d for d in twin["dials"]}
    assert (dials["warmth"]["value"], dials["warmth"]["source"]) == (5, "you")
    assert twin["style_presets"] == ["Friendly pro", "Brief and direct", "Warm storyteller"]
    twin = world.post(twin_id, "twin_dials", {"dials": {}, "preset": "Brief and direct"})
    dials = {d["id"]: d for d in twin["dials"]}
    assert (dials["warmth"]["value"], dials["warmth"]["source"]) == (5, "you")  # the person's stays
    assert (dials["directness"]["value"], dials["directness"]["source"]) == (5, "preset")
    world.post(twin_id, "twin_dials", {"dials": {"warmth": 9}}, status=400)
    world.post(twin_id, "twin_dials", {"dials": {"shouting": 3}}, status=400)


def test_a_chore_whose_tool_is_not_connected_cannot_be_picked(world: World) -> None:
    twin_id = world.create()
    chores = {c["id"]: c for c in world.get(twin_id)["chores"]}
    assert chores["calendar-hold"]["coming"] and chores["slack-thread"]["coming"]
    assert chores["file-outcome"]["coming"]  # Notion is not connected yet
    refused = world.post(twin_id, "twin_chores", {"ids": ["file-outcome"]}, status=400)
    assert "coming" in refused["reason"]
    world.connect_notion()
    twin = world.post(twin_id, "twin_chores", {"ids": ["file-outcome"]})
    chores = {c["id"]: c for c in twin["chores"]}
    assert chores["file-outcome"]["picked"] and "coming" not in chores["file-outcome"]
    assert chores["answer-comments"]["later"] is True
    assert [p["id"] for p in twin["pieces"]] == ["c-file-outcome"]
    refused = world.post(twin_id, "twin_chores", {"ids": ["calendar-hold"]}, status=400)
    assert "coming" in refused["reason"]
    world.post(twin_id, "twin_chores", {"ids": ["no-such"]}, status=404)


def test_pages_autonomy_and_memory_are_the_persons_ink(world: World) -> None:
    twin_id = world.create()
    world.connect_notion()
    twin = world.post(twin_id, "twin_pages", {"ids": ["a" * 32]})
    pages = {p["title"]: p for p in twin["pages"]}
    assert pages["Journal"]["suggest"] is False and pages["Journal"]["why_not"] == "It looks personal"
    (knowledge,) = [p for p in twin["pieces"] if p["place"] == "knowledge"]
    assert (knowledge["label"], knowledge["origin"], knowledge["confirmed"]) == (
        "Partnership offer",
        "you",
        True,
    )
    world.post(twin_id, "twin_pages", {"ids": ["f" * 32]}, status=404)
    # autonomy needs the channel on the twin first
    world.post(twin_id, "twin_autonomy", {"channel": "notion", "autonomy": "auto", "bar": 70}, status=400)
    world.say(twin_id, NEED)
    for _ in range(4):
        world.say(twin_id, choice="Keep it as it is")
    assert any(p["id"] == "p_notion" and p["confirmed"] for p in world.get(twin_id)["pieces"])
    twin = world.post(twin_id, "twin_autonomy", {"channel": "notion", "autonomy": "auto", "bar": 70})
    (piece,) = [p for p in twin["pieces"] if p["place"] == "autonomy"]
    assert (piece["label"], piece["detail"]) == ("Notion: Auto", "at 70 or more, empty risk list")
    world.post(twin_id, "twin_autonomy", {"channel": "notion", "autonomy": "auto", "bar": 100}, status=400)
    bad_split = {"channel": "notion", "autonomy": "auto", "bar": 70, "split": {"reply": "auto"}}
    world.post(twin_id, "twin_autonomy", bad_split, status=400)


def test_erasing_the_project_erases_the_twin_whole(world: World, daemon: Daemon) -> None:
    twin_id = world.create()
    world.play(twin_id, frames=10)
    space = world.get(twin_id)["space_id"]
    for table in TWIN_TABLES:
        assert daemon.store.query(f"SELECT COUNT(*) FROM {table} WHERE space_id = ?", (space,))[0][
            0
        ] > 0 or table in (
            "twin_examples",
            "twin_missions",
            "twin_turns",
        ), table
    r = world.client.delete(contracts.ROUTES["space"].format(id=space))
    assert r.status_code == 200, r.text
    for table in TWIN_TABLES:
        assert daemon.store.query(f"SELECT COUNT(*) FROM {table}")[0][0] == 0, table
    assert world.client.get(contracts.ROUTES["twin"].format(id=twin_id)).status_code == 404
    page: TwinPage = world.client.get(contracts.ROUTES["twins"]).json()
    assert page["twins"] == []


def test_a_twin_needs_a_project_of_its_own(world: World) -> None:
    assert world.client.post(contracts.ROUTES["twins"], json={"space_id": 7}).status_code == 400
    assert (
        world.client.post(contracts.ROUTES["twins"], json={"space_id": "spc_000000000000"}).status_code == 404
    )
    twin_id = world.create()
    space = world.get(twin_id)["space_id"]
    again = world.client.post(contracts.ROUTES["twins"], json={"space_id": space})
    assert again.status_code == 400 and "already has a twin" in again.json()["reason"]
    assert (
        world.client.post(
            contracts.ROUTES["twin_say"].format(id=twin_id), json={"text": "", "choice": "x"}
        ).status_code
        == 400
    )


def test_a_twin_without_a_project_makes_its_own_and_the_setup_names_it(world: World, daemon: Daemon) -> None:
    r = world.client.post(contracts.ROUTES["twins"], json={"space_id": ""})
    assert r.status_code == 201, r.text
    twin_id, space = r.json()["id"], r.json()["space_id"]
    assert space != "" and daemon.spaces.get(space)["name"] == setup.NEW_TWIN
    again = world.client.post(contracts.ROUTES["twins"], json={"space_id": space})
    assert again.status_code == 400 and "already has a twin" in again.json()["reason"]

    world.say(twin_id, NEED)
    world.say(twin_id, choice="As Alex from Low Tide Visuals")  # her `name` piece: "Partnerships"
    assert daemon.spaces.get(space)["name"] == "Partnerships"
    assert world.get(twin_id)["name"] == "Partnerships"

    # a Project the person named is never renamed by the setup
    daemon.spaces.update(space, {"name": "My outreach"})
    setup.rename_project(daemon, twin_id, "Partnerships")
    assert daemon.spaces.get(space)["name"] == "My outreach"


def test_what_the_setup_shows_is_in_plain_words(world: World) -> None:
    twin_id = world.create()
    after = world.play(twin_id)
    shown: list[str] = []
    for twin in after:
        shown += [p["label"] for p in twin["pieces"]] + [p.get("detail", "") for p in twin["pieces"]]
        if "ask" in twin:
            shown += [twin["ask"]["text"], *twin["ask"]["suggestions"]]
        shown += [f.get("reason", "") for f in twin["memory"]] + [c["does"] for c in twin["chores"]]
    for line in shown:
        assert not BANNED.search(line), line
