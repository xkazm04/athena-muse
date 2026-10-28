"""Drafts and shaping (ADR 0007): describe -> shape -> agreed over the routes, with the flow (never the
model) deciding coverage, and a failed reply leaving the draft exactly as it was."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from starlette.testclient import TestClient

from athena import routes_turn
from athena.app import Daemon
from athena.contracts import FOLLOW_UPS_MAX, NAME_MAX, NEED_MAX, EngineId, Probe
from athena.drafts import shape
from athena.engine import EngineError, TextDelta, ToolCall, Usage
from athena.errors import ApiError
from athena.server import create_app

H = {"Authorization": "Bearer t"}
NEED = (
    "Each month I check the after-school club's invoice against the days my kids actually went "
    "(the school portal has attendance) and dispute the extra days."
)


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("META_API_KEY", raising=False)
    yield
    routes_turn.TRANSPORT = None


def lines(r: httpx.Response) -> list[dict[str, Any]]:
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in r.text.splitlines() if line]


def new_draft(client: TestClient, need: str = NEED) -> dict[str, Any]:
    r = client.post("/drafts", json={"need": need}, headers=H)
    assert r.status_code == 201, r.text
    return dict(r.json())


def say(client: TestClient, draft_id: str, text: str = "", choice: str | None = None) -> list[dict[str, Any]]:
    body: dict[str, Any] = {"text": text}
    if choice is not None:
        body["choice"] = choice
    return lines(client.post(f"/drafts/{draft_id}/say", json=body, headers=H))


def of(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e for e in events if e["type"] == kind]


class Stage:
    """A stand-in model: one scripted round per call (words, then calls); past the script, silence."""

    id: EngineId = "scripted"
    model = "stage"
    simulated = True
    cost_estimated = False

    def __init__(self, *rounds: tuple[str, list[ToolCall]], fail_at: int = 0) -> None:
        self.rounds = list(rounds)
        self.fail_at = fail_at
        self.calls = 0
        self.tools: list[str] = []
        self.system = ""

    def probe(self) -> Probe:
        return {"ok": True}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        self.calls += 1
        self.tools = [t["function"]["name"] for t in tools]
        self.system = str(messages[0]["content"])
        if self.calls == self.fail_at:
            raise EngineError("Claude Code stopped")
        if self.calls <= len(self.rounds):
            text, calls = self.rounds[self.calls - 1]
            if text:
                yield TextDelta(text)
            yield from calls
        yield Usage(input_tokens=10, output_tokens=5)


def sketch_call(n: int, **args: str) -> ToolCall:
    return ToolCall(f"c{n}", "sketch", args)


def ask_call(n: int, slot: str, text: str = "Where does it happen?", answers: str = "A | B") -> ToolCall:
    return ToolCall(f"c{n}", "ask", {"slot": slot, "text": text, "suggestions": answers})


def run(daemon: Daemon, engine: Stage, draft_id: str, text: str = "") -> list[dict[str, Any]]:
    return list(shape.say(daemon, engine, draft_id, text, None))  # type: ignore[arg-type]


def drafted(daemon: Daemon) -> str:
    draft = shape.start(daemon, NEED)
    return draft["id"]


# --- acceptance 1: the scripted engine walks describe -> shape -> agreed -------------------------


def test_scripted_walk_from_describe_to_agreed(client: TestClient, daemon: Daemon) -> None:
    draft = new_draft(client)
    assert draft["step"] == "describe" and draft["agreed"] is False
    assert draft["id"].startswith("drf_") and len(draft["id"]) == 16
    assert client.get("/settings/active-space", headers=H).json() == {"space_id": draft["space_id"]}
    assert daemon.conversation.list(draft["space_id"]) == []  # nothing is run yet
    name = daemon.spaces.get(draft["space_id"])["name"]
    assert len(name) <= NAME_MAX and name.endswith("…") and NEED.startswith(name[:-1])

    first = say(client, draft["id"])
    assert first[0]["type"] == "start" and first[-1]["type"] == "done"
    node = of(first, "sketch")[0]["ops"][0]["node"]
    assert (node["slot"], node["origin"], node["confirmed"]) == ("need", "you", True)
    assert of(first, "ask")[0]["ask"]["slot"] == "apps" and of(first, "ask")[0]["ask"]["follow_up"] == 0
    assert [e["type"] for e in first[-2:]] == ["coverage", "done"]
    assert of(first, "coverage")[0]["coverage"]["need"] == 1
    assert daemon.spaces.get(draft["space_id"])["name"] == node["label"]  # renamed from the need node

    proposals: dict[str, str] = {}
    for answer in ("A website", "", "Check, then compare", "", "", ""):
        events = say(client, draft["id"], answer) if answer else say(client, draft["id"], "", choice="Both")
        added = of(events, "sketch")[0]["ops"][0]["node"]
        assert added["origin"] == "athena" and added["confirmed"] is False
        proposals[added["slot"]] = added["id"]
        assert of(events, "ask")[0]["ask"]["slot"] == added["slot"]
        assert of(events, "coverage")[0]["agreed"] is False
    assert list(proposals) == ["apps", "inputs", "steps", "hand", "output", "never"]

    got = client.get(f"/drafts/{draft['id']}", headers=H).json()
    assert got["step"] == "shape" and got["agreed"] is False
    assert got["coverage"] == {
        "need": 1,
        "apps": 0.5,
        "inputs": 0.5,
        "steps": 0.5,
        "hand": 0.5,
        "output": 0.5,
        "never": 0.5,
    }
    r = client.post(
        f"/drafts/{draft['id']}/confirm",
        json={"node_ids": [proposals["apps"], proposals["hand"], proposals["output"]]},
        headers=H,
    )
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["agreed"] is True
    assert done["coverage"] == {**got["coverage"], "apps": 1, "hand": 1, "output": 1}
    assert client.get(f"/drafts/{draft['id']}", headers=H).json() == done


# --- acceptance 2: a model cannot claim completion or the person's words -------------------------


def test_claiming_done_with_hand_empty_does_not_agree(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    for slot in ("need", "apps", "output"):
        engine = Stage(("Drawn.", [sketch_call(1, op="add", kind="step", slot=slot, label=f"The {slot}")]))
        run(daemon, engine, draft_id, f"about the {slot}")
    ids = [n["id"] for n in daemon.drafts.get(draft_id)["sketch"]["nodes"]]
    shape.confirm(daemon, draft_id, ids)
    events = run(daemon, Stage(("All done! The sketch is complete and agreed.", [])), draft_id, "so?")
    cov = of(events, "coverage")[0]
    assert cov["coverage"]["hand"] == 0 and cov["agreed"] is False
    assert daemon.drafts.get(draft_id)["agreed"] is False


def test_a_quote_not_in_the_persons_words_is_her_proposal(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    engine = Stage(
        (
            "Drawn.",
            [
                sketch_call(
                    1, op="add", slot="need", kind="step", label="Dispute", quote="dispute every invoice"
                ),
                sketch_call(
                    2, op="add", slot="apps", kind="app", label="Portal", quote="THE SCHOOL portal has"
                ),
                sketch_call(3, op="add", slot="steps", kind="step", label="Short", quote="extra days"),
            ],
        )
    )
    events = run(daemon, engine, draft_id)
    nodes = [op["node"] for e in of(events, "sketch") for op in e["ops"]]
    assert [(n["origin"], n["confirmed"]) for n in nodes] == [
        ("athena", False),  # not what the person said
        ("you", True),  # verbatim, case-insensitive
        ("athena", False),  # too short to prove anything
    ]
    assert [n["id"] for n in nodes] == ["n1", "n2", "n3"]


def test_a_quote_from_a_picked_suggestion_counts(client: TestClient, daemon: Daemon) -> None:
    draft = new_draft(client)
    say(client, draft["id"])
    say(client, draft["id"], "", choice="On the club's parent website")
    engine = Stage(
        (
            "Drawn.",
            [
                sketch_call(
                    1, op="add", slot="apps", kind="app", label="Club site", quote="the club's parent website"
                )
            ],
        )
    )
    events = run(daemon, engine, draft["id"], "ok")
    assert of(events, "sketch")[0]["ops"][0]["node"]["origin"] == "you"


# --- acceptance 3: a failed or empty reply is an error, never progress -----------------------------


def test_an_empty_reply_is_an_error_and_changes_nothing(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    before = daemon.drafts.get(draft_id)
    events = run(daemon, Stage(("", [])), draft_id)
    assert events[-1] == {
        "type": "error",
        "error": "engine_unavailable",
        "reason": "She did not answer; try again.",
    }
    assert not of(events, "coverage")
    assert daemon.drafts.get(draft_id) == before
    roles = [t["role"] for t in daemon.conversation.list(before["space_id"])]
    assert roles == ["person"]


def test_a_reply_that_fails_after_drawing_leaves_the_draft_as_it_was(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    run(
        daemon,
        Stage(("Drawn.", [sketch_call(1, op="add", slot="need", kind="step", label="Check the bill")])),
        draft_id,
    )
    before = daemon.drafts.get(draft_id)
    engine = Stage(
        ("", [sketch_call(1, op="add", slot="apps", kind="app", label="Portal"), ask_call(2, "apps")]),
        fail_at=2,
    )
    events = run(daemon, engine, draft_id, "next")
    assert of(events, "sketch")  # streamed as applied, then voided by the error
    assert events[-1]["type"] == "error" and events[-1]["error"] == "engine_unavailable"
    assert not of(events, "coverage") and not of(events, "done")
    assert daemon.drafts.get(draft_id) == before
    assert daemon.drafts.asked(draft_id) == {}
    assert daemon.ledger.page(10)["rows"][0]["ok"] is False


def test_an_engine_error_over_the_route_streams_error(
    client: TestClient, daemon: Daemon, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft = new_draft(client)
    routes_turn.TRANSPORT = httpx.MockTransport(lambda _: httpx.Response(401))
    monkeypatch.setenv("META_API_KEY", "sk-live-abc")
    events = say(client, draft["id"])
    assert events[-1] == {"type": "error", "error": "engine_unavailable", "reason": "Meta refused the key"}
    got = client.get(f"/drafts/{draft['id']}", headers=H).json()
    assert got["step"] == "describe" and got["sketch"] == {"nodes": [], "edges": []}


def test_words_alone_are_a_frame_and_step_moves_to_shape(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    events = run(daemon, Stage(("Tell me more about the club.", [])), draft_id)
    assert of(events, "coverage") and events[-1]["type"] == "done"
    assert daemon.drafts.get(draft_id)["step"] == "shape"


def test_ops_without_words_are_a_frame_with_her_question_as_the_line(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    engine = Stage(
        ("", [sketch_call(1, op="add", slot="apps", kind="app", label="Portal"), ask_call(2, "apps")])
    )
    events = run(daemon, engine, draft_id)
    assert of(events, "text") == [{"type": "text", "delta": "Where does it happen?"}]
    assert (
        daemon.conversation.list(daemon.drafts.get(draft_id)["space_id"])[-1]["text"]
        == "Where does it happen?"
    )


# --- the design turn: tools, frame, refusals -------------------------------------------------------


def test_a_design_turn_offers_recall_sketch_and_ask_only_and_frames_the_rubric(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    engine = Stage(("Hello.", []))
    run(daemon, engine, draft_id)
    assert engine.tools == ["recall", "sketch", "ask"]
    for line in ("- need: 0", "- hand: 0", "Never say or imply the sketch is complete", "2 to 4 short", NEED):
        assert line in engine.system


def test_a_second_ask_and_one_past_the_cap_are_refused(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    events = run(daemon, Stage(("Q.", [ask_call(1, "apps"), ask_call(2, "hand", "Who signs?")])), draft_id)
    assert [e["ask"]["slot"] for e in of(events, "ask")] == ["apps"]
    for n in range(FOLLOW_UPS_MAX):
        events = run(daemon, Stage(("Q.", [ask_call(1, "apps")])), draft_id, f"answer {n}")
        assert of(events, "ask")[0]["ask"]["follow_up"] == n + 1
    engine = Stage(("Q.", [ask_call(1, "apps")]))
    events = run(daemon, engine, draft_id, "and again")
    assert not of(events, "ask")
    assert daemon.drafts.asked(draft_id) == {"apps": FOLLOW_UPS_MAX + 1}


def test_ask_needs_two_to_four_answers(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    for answers in ("Only one", "a | b | c | d | e", "same | Same"):
        events = run(daemon, Stage(("Q.", [ask_call(1, "apps", answers=answers)])), draft_id, "hi")
        assert not of(events, "ask"), answers


def test_a_refused_sketch_call_tells_the_model_why_and_streams_nothing(daemon: Daemon) -> None:
    draft_id = drafted(daemon)

    class Watch(Stage):
        results: list[str]

        def complete(
            self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
        ) -> Iterator[TextDelta | ToolCall | Usage]:
            self.results = [str(m["content"]) for m in messages if m.get("role") == "tool"]
            yield from super().complete(messages, tools)

    engine = Watch(("Hm.", [sketch_call(1, op="link", link_from="x", link_to="y")]), ("Sorry.", []))
    events = run(daemon, engine, draft_id)
    assert not of(events, "sketch")
    assert engine.results and engine.results[0].startswith("Not drawn: there is no node 'x'")


def test_stage_turns_are_in_the_conversation_and_on_the_ledger_as_design(
    client: TestClient, daemon: Daemon
) -> None:
    draft = new_draft(client)
    say(client, draft["id"])
    say(client, draft["id"], "A website")
    turns = client.get(f"/conversation?space_id={draft['space_id']}", headers=H).json()["turns"]
    assert [t["role"] for t in turns] == ["person", "athena", "person", "athena"]
    assert turns[0]["text"] == NEED and turns[2]["text"] == "A website"
    assert "Where does this happen?" in turns[1]["text"]  # her question is kept with her line
    rows = client.get("/ledger", headers=H).json()["rows"]
    assert rows and {r["surface"] for r in rows} == {"design"}
    assert {r["space_id"] for r in rows} == {draft["space_id"]}


# --- validation and the rest of the routes -----------------------------------------------------------


def test_new_draft_validation(client: TestClient, daemon: Daemon) -> None:
    for body in ({}, {"need": ""}, {"need": "   "}, {"need": 7}, {"need": "x" * (NEED_MAX + 1)}):
        assert client.post("/drafts", json=body, headers=H).status_code == 400, body
    assert daemon.spaces.list() == []


def test_say_validation_is_a_4xx_before_streaming(client: TestClient) -> None:
    draft = new_draft(client)
    path = f"/drafts/{draft['id']}/say"
    assert client.post("/drafts/drf_000000000000/say", json={"text": "hi"}, headers=H).status_code == 404
    assert client.post(path, json={"text": 3}, headers=H).status_code == 400
    assert client.post(path, json={"text": "a", "choice": "b"}, headers=H).status_code == 400
    say(client, draft["id"])
    assert (
        client.post(path, json={"text": "  "}, headers=H).status_code == 400
    )  # past describe, say something


def test_say_past_shape_is_refused(client: TestClient, daemon: Daemon) -> None:
    draft = new_draft(client)
    daemon.drafts.put({**daemon.drafts.get(draft["id"]), "step": "author"})
    r = client.post(f"/drafts/{draft['id']}/say", json={"text": "hi"}, headers=H)
    assert r.status_code == 400 and r.json()["error"] == "bad_request"


def test_a_busy_draft_answers_409(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    space_id = daemon.drafts.get(draft_id)["space_id"]
    with daemon.busy.turn(space_id):
        for act in (
            lambda: shape.say(daemon, Stage(), draft_id, "hi", None),  # type: ignore[arg-type]
            lambda: shape.confirm(daemon, draft_id, []),
            lambda: shape.abandon(daemon, draft_id),
        ):
            with pytest.raises(ApiError) as e:
                act()
            assert e.value.error == "space_busy"


def test_confirm_an_unknown_node_is_400(client: TestClient) -> None:
    draft = new_draft(client)
    r = client.post(f"/drafts/{draft['id']}/confirm", json={"node_ids": ["n9"]}, headers=H)
    assert r.status_code == 400
    assert (
        client.post(f"/drafts/{draft['id']}/confirm", json={"node_ids": "n1"}, headers=H).status_code == 400
    )


def test_unknown_draft_is_404(client: TestClient) -> None:
    for method, path in (("GET", "/drafts/drf_x"), ("DELETE", "/drafts/drf_x")):
        r = client.request(method, path, headers=H)
        assert r.status_code == 404 and r.json()["error"] == "unknown_ref"
    r = client.post("/drafts/drf_x/confirm", json={"node_ids": []}, headers=H)
    assert r.status_code == 404


def test_absent_values_are_omitted(client: TestClient) -> None:
    draft = new_draft(client)
    assert set(draft) == {
        "id",
        "space_id",
        "step",
        "need",
        "sketch",
        "coverage",
        "agreed",
        "created",
        "updated",
    }


def test_skip_open_and_a_node_landing_unskips(daemon: Daemon) -> None:
    draft_id = drafted(daemon)
    run(
        daemon,
        Stage(("Drawn.", [sketch_call(1, op="add", slot="apps", kind="app", label="Portal")])),
        draft_id,
    )
    skipped = daemon.drafts.skip_open(draft_id)
    assert skipped["coverage"] == {s: "skipped" for s in skipped["coverage"]}  # 0 and 0.5 alike
    run(
        daemon,
        Stage(("Drawn.", [sketch_call(1, op="add", slot="hand", kind="gate", label="You sign")])),
        draft_id,
        "x",
    )
    cov = daemon.drafts.get(draft_id)["coverage"]
    assert cov["hand"] == 0.5 and cov["apps"] == "skipped" and cov["never"] == "skipped"


# --- acceptance 4: erasing the Project erases the draft --------------------------------------------


def test_erasing_the_project_erases_the_draft_and_its_folder(tmp_path: Path) -> None:
    daemon = Daemon.open(tmp_path)
    client = TestClient(create_app(daemon, "t"))
    draft = new_draft(client)
    folder = daemon.drafts.folder(draft["id"])
    assert folder == tmp_path / "drafts" / draft["id"]
    folder.mkdir(parents=True)
    (folder / "playbook.json").write_text("{}", encoding="utf-8")
    assert client.delete(f"/spaces/{draft['space_id']}", headers=H).status_code == 200
    assert not folder.exists()
    assert client.get(f"/drafts/{draft['id']}", headers=H).status_code == 404
    daemon.store.close()


def test_abandoning_a_draft_keeps_the_project(tmp_path: Path) -> None:
    daemon = Daemon.open(tmp_path)
    client = TestClient(create_app(daemon, "t"))
    draft = new_draft(client)
    folder = daemon.drafts.folder(draft["id"])
    assert folder is not None
    folder.mkdir(parents=True)
    r = client.delete(f"/drafts/{draft['id']}", headers=H)
    assert r.status_code == 200 and r.json() == {"id": draft["id"]}
    assert not folder.exists()
    assert client.get(f"/drafts/{draft['id']}", headers=H).status_code == 404
    assert client.get(f"/spaces/{draft['space_id']}", headers=H).status_code == 200
    daemon.store.close()


def test_the_rest_of_the_drafts_routes_are_not_built_yet(client: TestClient) -> None:
    draft = new_draft(client)
    assert client.post(f"/drafts/{draft['id']}/write", headers=H).status_code == 501


def test_start_runs_nothing(daemon: Daemon) -> None:
    draft = shape.start(daemon, NEED)
    assert draft["step"] == "describe"
    assert daemon.conversation.list(draft["space_id"]) == []
    assert daemon.ledger.page(10)["totals"]["calls"] == 0
