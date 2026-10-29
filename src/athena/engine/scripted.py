"""The no-key engine: deterministic, labelled simulated everywhere it shows."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from athena.contracts import LABEL_MAX, EngineId, Probe
from athena.engine import TextDelta, ToolCall, Usage

URL = re.compile(r"https?://[^\s,;)\"']+", re.IGNORECASE)


def _words(text: str) -> int:
    return len(text.split())


def _rest(text: str, word: str) -> str:
    i = text.lower().find(word)
    rest = text[i + len(word) :] if i >= 0 else text
    return rest.strip(" \t\r\n:,-.") or text.strip()


def _chunks(text: str) -> Iterator[str]:
    parts = text.split(" ")
    for i in range(0, len(parts), 3):
        yield " ".join(parts[i : i + 3]) + (" " if i + 3 < len(parts) else "")


# --- the stage (ADR 0007, 0010) -------------------------------------------------------------------
# The simulated frame reads the design frame the way a model would: the places it lists (in order,
# with each one's meaning and usual kind) and the coverage lines under them. Any rubric plays.

_PLACE_LINE = re.compile(r"^- ([a-z_]+): (.+) \(usual kind: ([a-z_]+)\)$", re.M)
_COVERAGE_LINE = re.compile(r"^- ([a-z_]+): (0\.5|0|1|skipped)$", re.M)
QUOTE_WORDS = 8  # the person's first words, quoted into the first place's node

_PROPOSALS: dict[str, tuple[str, str, list[str]]] = {
    # the chore's places: (the proposal's label, the question, its suggested answers)
    "apps": ("The website where it happens", "Where does this happen?", ["A website", "Email", "Both"]),
    "inputs": (
        "The page she reads first",
        "What should she read first?",
        ["A web page", "My email", "A letter"],
    ),
    "steps": (
        "Check, then compare",
        "What order does she work in?",
        ["Check, then compare", "Compare first", "You tell her"],
    ),
    "hand": (
        "You sign before anything is sent",
        "What should wait for your signature?",
        ["Anything she sends", "Only payments", "Nothing"],
    ),
    "output": (
        "A short summary for you",
        "What do you get at the end?",
        ["A short summary", "A list of problems", "A filled form"],
    ),
    "never": (
        "Never pay anything",
        "What must she never do?",
        ["Never pay", "Never delete", "Never write to anyone"],
    ),
}
_ANY_ANSWERS = ["Like that", "Something else", "Not sure yet"]


def _cut(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _proposal(place: str, meaning: str) -> tuple[str, str, list[str]]:
    """The canned proposal for a place: the chore's own lines, else one made from its meaning."""
    if place in _PROPOSALS:
        return _PROPOSALS[place]
    words = " ".join(meaning.split())
    return _cut(words[:1].upper() + words[1:], LABEL_MAX), f"What about {words}?", _ANY_ANSWERS


def _frame(messages: list[dict[str, Any]]) -> tuple[list[tuple[str, str, str]], dict[str, str]]:
    """((place, meaning, usual kind) in rubric order, coverage per place) from the design frame."""
    system = str(messages[0].get("content") or "") if messages else ""
    places = _PLACE_LINE.findall(system)
    names = {p for p, _, _ in places}
    return places, {p: v for p, v in _COVERAGE_LINE.findall(system) if p in names}


def _stage(messages: list[dict[str, Any]], said: str) -> tuple[str, list[ToolCall]]:
    """The first time (the first place empty): draw it in the person's first words, ask about the
    next empty place. Later: propose one node for the next empty place and ask about it."""
    places, cov = _frame(messages)
    if not places:
        return "(Simulated) I have nothing to draw here.", []
    first, _, first_kind = places[0]
    if cov.get(first, "0") == "0":
        words = " ".join(said.split()[:QUOTE_WORDS]) or "The job"
        draw = ToolCall(
            "call_sim1",
            "sketch",
            {"op": "add", "kind": first_kind, "slot": first, "label": _cut(words, LABEL_MAX), "quote": words},
        )
        cov[first] = "1"
        line = "(Simulated) I drew what you said."
    else:
        draw = None
        line = "(Simulated) Here is a guess for you to check."
    nxt = next(((p, m, k) for p, m, k in places[1:] if cov.get(p, "0") == "0"), None)
    if nxt is None:
        return "(Simulated) Every part of the sketch has something in it; confirm what is right.", (
            [draw] if draw else []
        )
    place, meaning, kind = nxt
    label, question, answers = _proposal(place, meaning)
    calls = (
        [draw]
        if draw
        else [ToolCall("call_sim1", "sketch", {"op": "add", "kind": kind, "slot": place, "label": label})]
    )
    calls.append(
        ToolCall("call_sim2", "ask", {"slot": place, "text": question, "suggestions": " | ".join(answers)})
    )
    return line, calls


class ScriptedEngine:
    id: EngineId = "scripted"
    model = "scripted"
    simulated = True
    cost_estimated = False

    def probe(self) -> Probe:
        return {"ok": True, "model": "scripted", "latency_ms": 0}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        offered = {t.get("function", {}).get("name") for t in tools}
        prompt = sum(_words(str(m.get("content") or "")) for m in messages)
        last = messages[-1] if messages else {}
        if "ask" in offered:  # a stage turn (ADR 0007): one simulated frame, then nothing more
            if last.get("role") != "tool":
                reply, calls = _stage(messages, self._last_person(messages))
                for chunk in _chunks(reply):
                    yield TextDelta(chunk)
                yield from calls
            yield Usage(input_tokens=prompt, output_tokens=0)
            return
        call: ToolCall | None = None
        if last.get("role") == "tool":
            body = str(last.get("content") or "").strip().splitlines()
            first = body[0][:120] if body else "done"
            reply = f"(Simulated) Done. {first}"
        else:
            reply, call = self._reply(self._last_person(messages), offered)
        for chunk in _chunks(reply):
            yield TextDelta(chunk)
        if call is not None:
            yield call
        yield Usage(input_tokens=prompt, output_tokens=_words(reply))

    @staticmethod
    def _last_person(messages: list[dict[str, Any]]) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                return str(m.get("content") or "")
        return ""

    @staticmethod
    def _reply(text: str, offered: set[Any]) -> tuple[str, ToolCall | None]:
        low = text.lower()
        url = URL.search(text)
        if "remember" in low and "remember" in offered:
            fact = _rest(text, "remember")
            return "(Simulated) I will keep that.", ToolCall("call_sim1", "remember", {"text": fact})
        if "brief" in low and "propose_brief" in offered:
            brief = _rest(text, "brief")
            return "(Simulated) Here is a brief for you to sign.", ToolCall(
                "call_sim1", "propose_brief", {"brief": brief}
            )
        if url and "app" in low and "add_app" in offered:
            return "(Simulated) I can add that app once you sign.", ToolCall(
                "call_sim1", "add_app", {"origin": url.group(0)}
            )
        if ("what do you know" in low or "recall" in low) and "recall" in offered:
            query = _rest(text, "recall") if "recall" in low else text.strip()
            return "(Simulated) Let me look.", ToolCall("call_sim1", "recall", {"query": query})
        topic = text.strip()[:80] or "that"
        return f"(Simulated reply, no Meta key yet.) You said: {topic}", None
