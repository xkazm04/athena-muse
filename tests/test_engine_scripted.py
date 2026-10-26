from __future__ import annotations

from typing import Any

import pytest

from athena.engine import TextDelta, ToolCall, Usage, status
from athena.engine.prices import estimate
from athena.engine.scripted import ScriptedEngine
from athena.keys import KeyStore

ALL = [
    {"type": "function", "function": {"name": n}} for n in ("recall", "remember", "propose_brief", "add_app")
]


def run(text: str, tools: list[dict[str, Any]] = ALL) -> list[Any]:
    return list(ScriptedEngine().complete([{"role": "user", "content": text}], tools))


def test_remember() -> None:
    out = run("Remember: I like green tea")
    call = next(c for c in out if isinstance(c, ToolCall))
    assert (call.name, call.arguments) == ("remember", {"text": "I like green tea"})
    assert isinstance(out[-1], Usage)


def test_brief_and_add_app_and_recall() -> None:
    assert next(c for c in run("write a brief: ship it") if isinstance(c, ToolCall)).name == "propose_brief"
    app = next(c for c in run("add the app https://example.com/x") if isinstance(c, ToolCall))
    assert (app.name, app.arguments["origin"]) == ("add_app", "https://example.com/x")
    assert next(c for c in run("what do you know about tea") if isinstance(c, ToolCall)).name == "recall"


def test_brief_not_offered_in_core() -> None:
    core = [t for t in ALL if t["function"]["name"] in ("recall", "remember")]
    assert not [c for c in run("brief: x", core) if isinstance(c, ToolCall)]


def test_plain_reply_is_labelled_and_chunked() -> None:
    out = run("hello there friend of mine")
    text = "".join(c.text for c in out if isinstance(c, TextDelta))
    assert "Simulated" in text and "hello there" in text
    assert sum(isinstance(c, TextDelta) for c in out) > 1


def test_after_tool_result_confirms_once() -> None:
    msgs = [{"role": "user", "content": "remember x"}, {"role": "tool", "content": "Kept."}]
    out = list(ScriptedEngine().complete(msgs, ALL))
    assert not [c for c in out if isinstance(c, ToolCall)]
    assert "Done" in "".join(c.text for c in out if isinstance(c, TextDelta))


def test_prices() -> None:
    assert estimate("muse-spark-1.3", 1_000_000, 1_000_000) == 5.5
    assert estimate("muse-wonder-1.0", 1_000_000, 0) == 4.0
    assert estimate("mystery", 10, 10) is None


def test_status_scripted_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("META_API_KEY", raising=False)
    assert status(KeyStore(None)) == {
        "engine": "scripted",
        "model": "scripted",
        "key": "absent",
        "simulated": True,
    }
