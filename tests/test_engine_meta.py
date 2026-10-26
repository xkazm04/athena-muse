from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from athena.engine import EngineError, TextDelta, ToolCall, Usage, build_engine
from athena.engine.meta import MuseEngine
from athena.keys import KeyStore


def sse(*chunks: Any) -> httpx.Response:
    body = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


def engine(handler: Any, model: str = "muse-spark-1.3") -> MuseEngine:
    return MuseEngine(
        "sk-test", model=model, base_url="https://x.test/v1", transport=httpx.MockTransport(handler)
    )


def delta(**d: Any) -> dict[str, Any]:
    return {"choices": [{"delta": d}]}


def test_streamed_text_split_tool_call_and_usage() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return sse(
            delta(content="Hel"),
            delta(content="lo"),
            delta(
                tool_calls=[{"index": 0, "id": "c1", "function": {"name": "remember", "arguments": '{"te'}}]
            ),
            delta(tool_calls=[{"index": 0, "function": {"arguments": 'xt": "tea"}'}}]),
            {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 5}},
        )

    out = list(engine(handler).complete([{"role": "user", "content": "hi"}], [{"type": "function"}]))
    assert [c.text for c in out if isinstance(c, TextDelta)] == ["Hel", "lo"]
    assert ToolCall("c1", "remember", {"text": "tea"}) in out
    assert out[-1] == Usage(12, 5)
    req = seen[0]
    assert req.headers["authorization"] == "Bearer sk-test"
    sent = json.loads(req.content)
    assert sent["stream"] is True and sent["stream_options"] == {"include_usage": True}
    assert req.url.path == "/v1/chat/completions"


def test_bad_tool_json_becomes_empty_args() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return sse(
            delta(tool_calls=[{"index": 0, "id": "c", "function": {"name": "recall", "arguments": "{oops"}}])
        )

    assert list(engine(handler).complete([], [])) == [ToolCall("c", "recall", {})]


def test_json_fallback() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        call = {"id": "c", "function": {"name": "recall", "arguments": '{"query":"q"}'}}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "whole", "tool_calls": [call]}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    out = list(engine(handler).complete([], []))
    assert out == [TextDelta("whole"), ToolCall("c", "recall", {"query": "q"}), Usage(3, 2)]


@pytest.mark.parametrize(
    ("status", "words"), [(401, "refused the key"), (403, "refused the key"), (429, "rate limiting")]
)
def test_http_errors_in_plain_words(status: int, words: str) -> None:
    with pytest.raises(EngineError) as e:
        list(engine(lambda _: httpx.Response(status, text="no")).complete([], []))
    assert words in e.value.reason
    assert "sk-test" not in e.value.reason


def test_network_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(EngineError, match="Could not reach Meta"):
        list(engine(handler).complete([], []))


def test_stream_options_400_retries_once_without() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        bodies.append(body)
        if "stream_options" in body:
            return httpx.Response(400, text="unknown field stream_options")
        return sse(delta(content="ok"))

    assert list(engine(handler).complete([], [])) == [TextDelta("ok")]
    assert len(bodies) == 2 and "stream_options" not in bodies[1]


def test_other_400_is_not_retried() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, text="bad model")

    with pytest.raises(EngineError):
        list(engine(handler).complete([], []))
    assert calls == 1


def test_contributor_model_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setenv("META_MODEL", "muse-spark-1.3-contributor")
    with pytest.raises(EngineError, match="trains on your content"):
        build_engine(KeyStore(None))


def test_build_engine_picks_by_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("META_MODEL", raising=False)
    ks = KeyStore(None)
    assert build_engine(ks).id == "scripted"
    ks.save("sk-abc")
    eng = build_engine(ks)
    assert (eng.id, eng.model, eng.simulated) == ("muse", "muse-spark-1.3", False)
    assert "sk-abc" not in repr(eng)


def test_probe() -> None:
    ok = engine(lambda _: httpx.Response(200, json={"choices": []})).probe()
    assert ok["ok"] and ok["model"] == "muse-spark-1.3" and "latency_ms" in ok
    assert engine(lambda _: httpx.Response(401)).probe() == {"ok": False, "error": "Meta refused the key"}
