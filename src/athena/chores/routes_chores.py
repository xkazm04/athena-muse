"""Routes over the chores (ADR 0005, ADR 0007): `GET /chores` and `GET /chores/{id}`.

Both libraries are listed: the app's `playbooks/` (`origin: "library"`) and the chores the person
kept in `<data_dir>/chores/` (`origin: "yours"`). They are read from disk on each request, so a
rebuilt `sensed.json`, `proofs.json` or `bench.json` shows without a restart. A broken chore is
skipped and logged, never a 500.
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena.app import Daemon
from athena.chores.spec import CHORE_ID, ChoreError, detail, find_chore, load_both, load_chore, summary
from athena.errors import ApiError

__all__ = ["CHORE_ID", "routes"]


def routes(daemon: Daemon) -> list[BaseRoute]:
    async def chores_index(_: Request) -> Response:
        return JSONResponse({"chores": [summary(c) for c in load_both(daemon.data_dir)]})

    async def chore_item(request: Request) -> Response:
        chore_id = request.path_params["id"]
        found = find_chore(chore_id, daemon.data_dir)
        if found is None:
            raise ApiError("unknown_ref", "there is no chore by that id")
        root, origin = found
        try:
            chore = load_chore(root, origin=origin)
        except ChoreError as e:
            # The list skips a broken chore, so asking for it by id answers as the list does.
            raise ApiError("unknown_ref", f"the chore {chore_id} cannot be loaded: {e}") from e
        return JSONResponse(detail(chore))

    return [
        Route("/chores", chores_index, methods=["GET"]),
        Route("/chores/{id}", chore_item, methods=["GET"]),
    ]
