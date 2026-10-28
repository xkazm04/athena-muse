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


# --- the stage (ADR 0007) -------------------------------------------------------------------------
# The simulated frame reads the design frame the way a model would: the coverage lines it lists.

_COVERAGE_LINE = re.compile(r"^- (need|apps|inputs|steps|hand|output|never): (0\.5|0|1|skipped)$", re.M)
QUOTE_WORDS = 8  # the person's first words, quoted into the need node

_PROPOSALS: dict[str, tuple[str, str, str, list[str]]] = {
    # slot: (kind, the proposal's label, the question, its suggested answers)
    "apps": (
        "app",
        "The website where it happens",
        "Where does this happen?",
        ["A website", "Email", "Both"],
    ),
    "inputs": (
        "source",
        "The page she reads first",
        "What should she read first?",
        ["A web page", "My email", "A letter"],
    ),
    "steps": (
        "step",
        "Check, then compare",
        "What order does she work in?",
        ["Check, then compare", "Compare first", "You tell her"],
    ),
    "hand": (
        "gate",
        "You sign before anything is sent",
        "What should wait for your signature?",
        ["Anything she sends", "Only payments", "Nothing"],
    ),
    "output": (
        "output",
        "A short summary for you",
        "What do you get at the end?",
        ["A short summary", "A list of problems", "A filled form"],
    ),
    "never": (
        "never",
        "Never pay anything",
        "What must she never do?",
        ["Never pay", "Never delete", "Never write to anyone"],
    ),
}


def _coverage(messages: list[dict[str, Any]]) -> dict[str, str]:
    system = str(messages[0].get("content") or "") if messages else ""
    return dict(_COVERAGE_LINE.findall(system))


def _stage(messages: list[dict[str, Any]], said: str) -> tuple[str, list[ToolCall]]:
    """The first time (need empty): draw the need in the person's first words, ask about the first
    empty slot. Later: propose one node for the next empty slot and ask about it."""
    cov = _coverage(messages)
    if cov.get("need", "0") == "0":
        first = " ".join(said.split()[:QUOTE_WORDS]) or "The job"
        label = first if len(first) <= LABEL_MAX else first[: LABEL_MAX - 1].rstrip() + "…"
        draw = ToolCall(
            "call_sim1",
            "sketch",
            {"op": "add", "kind": "step", "slot": "need", "label": label, "quote": first},
        )
        cov["need"] = "1"
        line = "(Simulated) I drew what you said."
    else:
        draw = None
        line = "(Simulated) Here is a guess for you to check."
    slot = next((s for s in _PROPOSALS if cov.get(s, "0") == "0"), None)
    if slot is None:
        return "(Simulated) Every part of the sketch has something in it; confirm what is right.", (
            [draw] if draw else []
        )
    kind, label, question, answers = _PROPOSALS[slot]
    calls = (
        [draw]
        if draw
        else [ToolCall("call_sim1", "sketch", {"op": "add", "kind": kind, "slot": slot, "label": label})]
    )
    calls.append(
        ToolCall("call_sim2", "ask", {"slot": slot, "text": question, "suggestions": " | ".join(answers)})
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
