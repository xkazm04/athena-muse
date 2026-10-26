"""Routes over the engine and the turn: /engine, /engine/key, /engine/probe, /run."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import BaseRoute, Route

from athena import engine as engine_mod
from athena.app import Daemon
from athena.contracts import EngineStatus
from athena.engine import EngineError
from athena.errors import ApiError
from athena.keys import KeyStore
from athena.turn import execute, run_turn

# Tests inject a mock transport here; the engine is built per request so it is read each time.
TRANSPORT: httpx.BaseTransport | None = None


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ApiError("bad_request", "send a JSON object")
    return data


def _line(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


def routes(daemon: Daemon) -> list[BaseRoute]:
    keys = KeyStore(daemon.data_dir)
    daemon.gate.set_executor(lambda card: execute(daemon, card))

    def current() -> EngineStatus:
        return engine_mod.status(keys)

    def announce() -> EngineStatus:
        status = current()
        daemon.events.publish({"type": "engine", "status": status})
        return status

    async def get_engine(_: Request) -> Response:
        return JSONResponse(current())

    async def engine_key(request: Request) -> Response:
        if request.method == "DELETE":
            keys.delete()
        else:
            key = (await _body(request)).get("key")
            if not isinstance(key, str):
                raise ApiError("bad_request", "send the key as text")
            keys.save(key)
        return JSONResponse(announce())

    async def probe(_: Request) -> Response:
        try:
            result = engine_mod.build_engine(keys, transport=TRANSPORT).probe()
            model = result.get("model", engine_mod.model_name())
            engine_id = "muse" if keys.get() else "scripted"
        except EngineError as e:
            result = {"ok": False, "error": e.reason}
            model = engine_mod.model_name()
            engine_id = "muse"
        row: dict[str, Any] = {
            "surface": "probe",
            "space_id": "",
            "engine": engine_id,
            "model": model,
            "latency_ms": result.get("latency_ms", 0),
            "ok": result["ok"],
        }
        if "error" in result:
            row["error"] = result["error"]
        daemon.ledger.record(**row)
        return JSONResponse(result)

    async def run(request: Request) -> Response:
        data = await _body(request)
        text, space_id = data.get("text"), data.get("space_id", "")
        if not isinstance(text, str) or not isinstance(space_id, str):
            raise ApiError("bad_request", "send text and space_id as strings")
        try:
            engine = engine_mod.build_engine(keys, transport=TRANSPORT)
        except EngineError as e:
            raise ApiError("engine_unavailable", e.reason) from e
        events = run_turn(daemon, engine, text, space_id)  # raises the 4xx before any streaming
        first = next(events)  # takes the project's turn slot now, so a busy project answers 409

        def lines() -> Iterator[bytes]:
            yield _line(first)
            for event in events:
                yield _line(event)

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    return [
        Route("/engine", get_engine, methods=["GET"]),
        Route("/engine/key", engine_key, methods=["POST", "DELETE"]),
        Route("/engine/probe", probe, methods=["POST"]),
        Route("/run", run, methods=["POST"]),
    ]
