"""The records routes: space_records, record_history, record_verdict, space_kinds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena.contracts import ROUTES, KindsBody, RecordList, TrackVerdictBody
from athena.errors import ApiError
from athena.records.kinds import check_kind

if TYPE_CHECKING:
    from athena.app import Daemon


async def _body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ApiError("bad_request", "send a JSON object")
    return data


def routes(daemon: Daemon) -> list[BaseRoute]:
    def _space(request: Request) -> str:
        space_id = str(request.path_params["id"])
        if not space_id or not daemon.spaces.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        return space_id

    async def space_records(request: Request) -> Response:
        space_id = _space(request)
        kind_q = request.query_params.get("kind") or None
        key = request.query_params.get("key") or None
        kind = check_kind(kind_q) if kind_q is not None else None
        listed: RecordList = {"records": daemon.records.latest(space_id, kind, key)}
        return JSONResponse(listed)

    async def record_history(request: Request) -> Response:
        listed: RecordList = {"records": daemon.records.history(str(request.path_params["id"]))}
        return JSONResponse(listed)

    async def record_verdict(request: Request) -> Response:
        record_id = str(request.path_params["id"])
        daemon.records.get(record_id)  # unknown_ref before the body is read
        data = await _body(request)
        # The shape is checked by Records.verdict.
        return JSONResponse(daemon.records.verdict(record_id, cast("TrackVerdictBody", data)))

    async def space_kinds(request: Request) -> Response:
        space_id = _space(request)
        data = await _body(request)
        # The shape is checked by Records.set_kinds.
        return JSONResponse(daemon.records.set_kinds(space_id, cast("KindsBody", data)))

    return [
        Route(ROUTES["space_records"], space_records, methods=["GET"]),
        Route(ROUTES["record_history"], record_history, methods=["GET"]),
        Route(ROUTES["record_verdict"], record_verdict, methods=["POST"]),
        Route(ROUTES["space_kinds"], space_kinds, methods=["PUT"]),
    ]
