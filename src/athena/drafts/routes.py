"""Routes over drafts (ADR 0007): shaping, authoring, the preview, the key, the test run and the
verdict. Writing, the preview and the test run are background jobs (ADR 0020): their POST starts the
job and follows it, `GET .../job` follows it again from any window, `POST .../job/stop` stops it. The
shaping stream and the calls that wait on a model run off the event loop, so a long call never stalls
the daemon."""

from __future__ import annotations

import json
import typing
from collections.abc import AsyncIterator, Iterator
from typing import Any, cast, get_args

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import BaseRoute, Route

from athena import engine as engine_mod
from athena import routes_turn
from athena.app import Daemon
from athena.contracts import AccessAct, Draft, DraftNotes, KeyBody, StageView
from athena.drafts import access, author, jobs, key, preview, rehearse, save, shape
from athena.engine import Engine, EngineError, cli
from athena.errors import ApiError
from athena.keys import KeyStore


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ApiError("bad_request", "send a JSON object")
    return data


STAGE_VIEWS: frozenset[str] = frozenset(typing.get_args(StageView))


def _node_ids(body: dict[str, Any]) -> list[str]:
    node_ids = body.get("node_ids")
    if not isinstance(node_ids, list) or not all(isinstance(n, str) for n in node_ids):
        raise ApiError("bad_request", "send node_ids as a list of ids")
    return node_ids


def _line(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


async def _stream(events: Iterator[dict[str, Any]]) -> Response:
    # Takes the project's turn slot now, so a busy project answers 409; off the loop, as every line is.
    first = await run_in_threadpool(next, events)

    def lines() -> Iterator[bytes]:
        yield _line(first)
        for event in events:
            yield _line(event)

    return StreamingResponse(lines(), media_type="application/x-ndjson")


NDJSON = "application/x-ndjson"


def _follow(job: jobs.Job, after: int) -> Response:
    """A job's follow stream (protocol: contracts.py, above RehearsalPhase). Each wait runs off the
    loop and is short, so a client that leaves is let go within FOLLOW_WAIT_S; the job runs on."""

    async def lines() -> AsyncIterator[bytes]:
        yield _line({"type": "job", "job": job.snapshot()})
        i = max(0, after)
        while True:
            events, ended = await run_in_threadpool(job.wait, i, jobs.FOLLOW_WAIT_S)
            for event in events:
                yield _line(event)
            i += len(events)
            if ended and not events:
                return

    return StreamingResponse(lines(), media_type=NDJSON)


#: The person's notes while she works: lines per list, as the key's missing and never lines are.
NOTES_STEPS: frozenset[str] = frozenset({"describe", "shape", "author", "preview", "rehearse"})


def _note_lines(raw: Any, what: str) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise ApiError("bad_request", f"send {what} as a list of lines")
    out = [line for line in (" ".join(x.split()) for x in raw) if line]
    if len(out) > key.LINES_MAX:
        raise ApiError("bad_request", f"at most {key.LINES_MAX} {what} lines")
    if any(len(line) > key.LINE_MAX for line in out):
        raise ApiError("bad_request", f"each {what} line is at most {key.LINE_MAX} characters")
    return out


def put_notes(daemon: Daemon, draft_id: str, body: dict[str, Any]) -> Draft:
    """Replaces `Draft.notes`: trimmed non-empty lines, each at most LINE_MAX, at most LINES_MAX per
    list; allowed at any step before the verdict."""
    draft = daemon.drafts.get(draft_id)
    if draft["step"] not in NOTES_STEPS:
        raise ApiError("bad_request", "notes are for while she works; the test run is already scored")
    notes: DraftNotes = {
        "expect": _note_lines(body.get("expect"), "expect"),
        "never": _note_lines(body.get("never"), "never"),
    }
    stored = cast("dict[str, Any]", dict(daemon.drafts.get(draft_id)))
    stored["notes"] = notes
    return daemon.drafts.put(cast("Draft", stored))


def routes(daemon: Daemon) -> list[BaseRoute]:
    keys = KeyStore(daemon.data_dir)

    def engine() -> Engine:
        try:
            # The turn routes' transport, read per request so tests can inject a mock one.
            return engine_mod.build_engine(
                keys, stored=daemon.settings.engine_choice(), transport=routes_turn.TRANSPORT
            )
        except EngineError as e:
            raise ApiError("engine_unavailable", e.reason) from e

    async def drafts(request: Request) -> Response:
        need = (await _body(request)).get("need")
        if not isinstance(need, str):
            raise ApiError("bad_request", "send the need as text")
        draft = shape.start(daemon, need)  # the first turn runs on the first say
        return JSONResponse(draft, status_code=201)

    async def draft(request: Request) -> Response:
        draft_id = request.path_params["id"]
        if request.method == "DELETE":
            shape.abandon(daemon, draft_id)
            return JSONResponse({"id": draft_id})
        return JSONResponse(daemon.drafts.get(draft_id))

    async def say(request: Request) -> Response:
        body = await _body(request)
        text, choice, view = body.get("text", ""), body.get("choice"), body.get("view")
        if not isinstance(text, str) or not (choice is None or isinstance(choice, str)):
            raise ApiError("bad_request", "send text, and choice if you picked one, as text")
        if view is not None and view not in STAGE_VIEWS:
            raise ApiError("bad_request", f"the view is one of {', '.join(sorted(STAGE_VIEWS))}")
        daemon.drafts.get(request.path_params["id"])  # an unknown draft is a 404 before the engine
        draft_id = request.path_params["id"]
        return await _stream(
            shape.say(daemon, engine(), draft_id, text, choice, cast("StageView | None", view))
        )

    async def confirm(request: Request) -> Response:
        node_ids = _node_ids(await _body(request))
        return JSONResponse(shape.confirm(daemon, request.path_params["id"], node_ids))

    async def drop(request: Request) -> Response:
        node_ids = _node_ids(await _body(request))
        return JSONResponse(shape.drop(daemon, request.path_params["id"], node_ids))

    def optional_engine() -> Engine | None:
        try:
            return engine()
        except ApiError:
            return None  # the key step needs one only for missing and never lines; it says so then

    async def write(request: Request) -> Response:
        draft_id = request.path_params["id"]
        daemon.drafts.get(draft_id)
        work = author.write(daemon, engine(), draft_id)  # validates; nothing runs until the job does
        return _follow(daemon.jobs.start(daemon, draft_id, "write", work, timeout_s=None), 0)

    async def preview_cards(request: Request) -> Response:
        draft_id = request.path_params["id"]
        chore = preview.check(daemon, draft_id)
        work = preview.work(daemon, engine(), draft_id, chore)
        return _follow(daemon.jobs.start(daemon, draft_id, "preview", work, timeout_s=cli.CLI_TIMEOUT_S), 0)

    async def put_key(request: Request) -> Response:
        body = await _body(request)
        daemon.drafts.get(request.path_params["id"])
        draft = await run_in_threadpool(
            key.put_key, daemon, optional_engine(), request.path_params["id"], cast("KeyBody", body)
        )
        return JSONResponse(draft)

    async def run(request: Request) -> Response:
        draft_id = request.path_params["id"]
        chore = rehearse.check(daemon, draft_id)
        work = rehearse.work(daemon, engine(), draft_id, chore)
        return _follow(daemon.jobs.start(daemon, draft_id, "rehearse", work, timeout_s=cli.CLI_TIMEOUT_S), 0)

    async def job(request: Request) -> Response:
        draft_id = request.path_params["id"]
        draft = daemon.drafts.get(draft_id)
        raw = request.query_params.get("after", "0")
        if not raw.isdigit():
            raise ApiError("bad_request", "after is a whole number of events")
        running = daemon.jobs.get(draft_id)
        if running is not None:
            return _follow(running, int(raw))
        if "job" not in draft:
            raise ApiError("unknown_ref", "she has not started any work on this draft")
        # After a restart only what was kept: the snapshot, with the stored state.
        return StreamingResponse(iter([_line({"type": "job", "job": draft["job"]})]), media_type=NDJSON)

    async def job_stop(request: Request) -> Response:
        draft_id = request.path_params["id"]
        daemon.drafts.get(draft_id)
        await run_in_threadpool(daemon.jobs.stop, daemon, draft_id)
        return JSONResponse(daemon.drafts.get(draft_id))

    async def notes(request: Request) -> Response:
        body = await _body(request)
        return JSONResponse(await run_in_threadpool(put_notes, daemon, request.path_params["id"], body))

    async def verdict(request: Request) -> Response:
        body = await _body(request)
        word, note = body.get("verdict"), body.get("note")
        if word not in ("keep", "revise") or not (note is None or isinstance(note, str)):
            raise ApiError("bad_request", "send verdict, keep or revise, and a note as text if you have one")
        return JSONResponse(save.verdict(daemon, request.path_params["id"], word, note))

    async def access_act(request: Request) -> Response:
        body = await _body(request)
        origin, what = body.get("origin"), body.get("act")
        if not isinstance(origin, str) or what not in get_args(AccessAct):
            raise ApiError(
                "bad_request", "send the site's origin and an act: sign_in, check, skip or use_moved"
            )
        draft = await run_in_threadpool(
            access.act, daemon, request.path_params["id"], origin, cast("AccessAct", what)
        )
        return JSONResponse(draft)

    return [
        Route("/drafts", drafts, methods=["POST"]),
        Route("/drafts/{id}", draft, methods=["GET", "DELETE"]),
        Route("/drafts/{id}/say", say, methods=["POST"]),
        Route("/drafts/{id}/confirm", confirm, methods=["POST"]),
        Route("/drafts/{id}/drop", drop, methods=["POST"]),
        Route("/drafts/{id}/write", write, methods=["POST"]),
        Route("/drafts/{id}/preview", preview_cards, methods=["POST"]),
        Route("/drafts/{id}/key", put_key, methods=["PUT"]),
        Route("/drafts/{id}/rehearse", run, methods=["POST"]),
        Route("/drafts/{id}/verdict", verdict, methods=["POST"]),
        Route("/drafts/{id}/job", job, methods=["GET"]),
        Route("/drafts/{id}/job/stop", job_stop, methods=["POST"]),
        Route("/drafts/{id}/notes", notes, methods=["PUT"]),
        Route("/drafts/{id}/access", access_act, methods=["POST"]),
    ]
