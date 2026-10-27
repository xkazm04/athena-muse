"""What Athena read on a chore's pages, kept for the turns that follow (ADR 0005, amended).

A turn's history carries Athena's words, not what her tools answered. On a chore that walks from
one app to the next, the ids she read on the first page (a bottle's med id, a member's id) were
gone by the third, and she rightly refused to guess them. So every portal READ answer is kept per
space, and a portal turn's frame lists the newest ones (one per tool and arguments, within a
budget). The answers were fenced as page data when they were read and stay fenced here. Erasing a
project erases its reads with it.
"""

from __future__ import annotations

import json
from typing import Any

from athena.app import Daemon
from athena.clock import now_iso

#: The most characters of earlier reads a frame carries; older reads beyond it are named, not shown.
FRAME_BUDGET = 16_000


def _key(app: str, tool: str, args: dict[str, Any]) -> str:
    return json.dumps([app, tool, args], sort_keys=True, ensure_ascii=False)


def record(daemon: Daemon, space_id: str, app: str, tool: str, args: dict[str, Any], answer: str) -> None:
    daemon.store.run(
        "INSERT INTO page_reads (space_id, created, app, tool, args, answer) VALUES (?, ?, ?, ?, ?, ?)",
        (space_id, now_iso(), app, tool, json.dumps(args, sort_keys=True, ensure_ascii=False), answer),
    )


def frame(daemon: Daemon, space_id: str, budget: int = FRAME_BUDGET) -> str:
    """The newest answer per (app, tool, args), newest first until the budget, shown oldest first."""
    rows = daemon.store.query(
        "SELECT app, tool, args, answer FROM page_reads WHERE space_id = ? ORDER BY id DESC", (space_id,)
    )
    seen: set[str] = set()
    shown: list[str] = []
    left = budget
    skipped = 0
    for r in rows:
        args = json.loads(r["args"])
        key = _key(r["app"], r["tool"], args)
        if key in seen:
            continue
        seen.add(key)
        given = ", ".join(f"{k}={v}" for k, v in args.items())
        block = f"### {r['tool']} on {r['app']}" + (f" ({given})" if given else "") + f"\n{r['answer']}"
        if len(block) > left:
            skipped += 1
            continue
        left -= len(block)
        shown.append(block)
    if not shown:
        return ""
    out = ["", "", "## Pages you read earlier in this chore", *reversed(shown)]
    if skipped:
        out.append(f"({skipped} older reads are not shown; read the page again if you need one.)")
    return "\n\n".join(out)
