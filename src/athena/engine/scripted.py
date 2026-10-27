"""The no-key engine: deterministic, labelled simulated everywhere it shows."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from athena.contracts import EngineId, Probe
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
