"""Routes over the chore library (ADR 0005): `GET /chores` and `GET /chores/{id}`.

The library is read from disk on each request, so a rebuilt `sensed.json`, `proofs.json` or
`bench.json` shows without a restart. A broken chore is skipped and logged, never a 500.
"""

from __future__ import annotations

import re

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Route

from athena.chores.spec import ChoreError, detail, library_dir, load_chore, load_library, summary
from athena.errors import ApiError

#: A chore id is its folder name: lowercase words joined by hyphens.
CHORE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")


async def chores_index(_: Request) -> Response:
    return JSONResponse({"chores": [summary(c) for c in load_library()]})


async def chore_item(request: Request) -> Response:
    chore_id = request.path_params["id"]
    root = library_dir() / chore_id
    if not CHORE_ID.fullmatch(chore_id) or not (root / "playbook.json").is_file():
        raise ApiError("unknown_ref", "there is no chore by that id")
    try:
        chore = load_chore(root)
    except ChoreError as e:
        # The list skips a broken chore, so asking for it by id answers as the list does.
        raise ApiError("unknown_ref", f"the chore {chore_id} cannot be loaded: {e}") from e
    return JSONResponse(detail(chore))


def routes() -> list[BaseRoute]:
    return [
        Route("/chores", chores_index, methods=["GET"]),
        Route("/chores/{id}", chore_item, methods=["GET"]),
    ]
