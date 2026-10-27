"""Muse over Chat Completions (OpenAI-compatible), streamed, with a non-streamed fallback."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

import httpx

from athena.clock import mint
from athena.contracts import EngineId, Probe
from athena.engine import EngineError, TextDelta, ToolCall, Usage

TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _http_error(status: int) -> EngineError:
    if status in (401, 403):
        return EngineError("Meta refused the key")
    if status == 429:
        return EngineError("Meta is rate limiting; try again in a minute")
    return EngineError(f"Meta answered with an error ({status})")


def _args(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _usage(raw: Any) -> Usage | None:
    if not isinstance(raw, dict):
        return None
    return Usage(int(raw.get("prompt_tokens") or 0), int(raw.get("completion_tokens") or 0))


class MuseEngine:
    id: EngineId = "muse"
    simulated = False
    cost_estimated = True

    def __init__(
        self, key: str, *, model: str, base_url: str, transport: httpx.BaseTransport | None = None
    ) -> None:
        self._key = key
        self.model = model
        self._base = base_url.rstrip("/")
        self._transport = transport

    def __repr__(self) -> str:
        return f"MuseEngine(model={self.model!r}, key=***)"

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=TIMEOUT, transport=self._transport)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        body: dict[str, Any] = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            body["tools"] = tools
        try:
            with self._client() as client:
                for with_usage in (True, False):
                    if with_usage:
                        body["stream_options"] = {"include_usage": True}
                    else:
                        body.pop("stream_options", None)
                    with client.stream(
                        "POST", f"{self._base}/chat/completions", json=body, headers=self._headers()
                    ) as resp:
                        if resp.status_code >= 400:
                            text = resp.read().decode("utf-8", "replace")
                            if resp.status_code == 400 and with_usage and "stream_options" in text:
                                continue  # the API will not take usage on the stream; ask once without
                            raise _http_error(resp.status_code)
                        if "application/json" in resp.headers.get("content-type", ""):
                            yield from self._whole(json.loads(resp.read()))
                        else:
                            yield from self._sse(resp)
                        return
        except httpx.HTTPError as e:
            raise EngineError("Could not reach Meta") from e

    def _whole(self, data: Any) -> Iterator[TextDelta | ToolCall | Usage]:
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise EngineError("Meta sent a reply Athena could not read") from e
        if message.get("content"):
            yield TextDelta(str(message["content"]))
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            call_id = str(tc.get("id") or mint("call_"))
            yield ToolCall(call_id, str(fn.get("name") or ""), _args(fn.get("arguments") or ""))
        usage = _usage(data.get("usage"))
        if usage:
            yield usage

    def _sse(self, resp: httpx.Response) -> Iterator[TextDelta | ToolCall | Usage]:
        calls: dict[int, dict[str, str]] = {}
        usage: Usage | None = None
        for line in resp.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except ValueError:
                continue
            usage = _usage(chunk.get("usage")) or usage
            for choice in chunk.get("choices") or []:
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    yield TextDelta(str(delta["content"]))
                for tc in delta.get("tool_calls") or []:
                    slot = calls.setdefault(int(tc.get("index") or 0), {"id": "", "name": "", "args": ""})
                    slot["id"] = str(tc.get("id") or slot["id"])
                    fn = tc.get("function") or {}
                    slot["name"] += str(fn.get("name") or "")
                    slot["args"] += str(fn.get("arguments") or "")
        for _, slot in sorted(calls.items()):
            yield ToolCall(slot["id"] or mint("call_"), slot["name"], _args(slot["args"]))
        if usage:
            yield usage

    def probe(self) -> Probe:
        body = {"model": self.model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
        started = time.monotonic()
        try:
            with self._client() as client:
                resp = client.post(f"{self._base}/chat/completions", json=body, headers=self._headers())
            if resp.status_code >= 400:
                raise _http_error(resp.status_code)
        except httpx.HTTPError:
            return {"ok": False, "error": "Could not reach Meta"}
        except EngineError as e:
            return {"ok": False, "error": e.reason}
        return {"ok": True, "model": self.model, "latency_ms": int((time.monotonic() - started) * 1000)}
