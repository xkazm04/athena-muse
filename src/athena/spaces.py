"""Projects (wire: spaces)."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from athena.busy import Busy
from athena.clock import mint, now_iso
from athena.contracts import (
    APPS_MAX,
    BRIEF_MAX,
    HUE_MAX,
    NAME_MAX,
    SPACE_PREFIX,
    SPACES_MAX,
    SpaceCounts,
    SpaceErased,
    SpaceSummary,
)
from athena.drafts.store import remove_folder
from athena.errors import ApiError
from athena.settings import ACTIVE_SPACE_KEY
from athena.store import TWIN_TABLES, Store

_DEFAULT_PORTS = {"http": 80, "https": 443}


def _bad(reason: str) -> ApiError:
    return ApiError("bad_request", reason)


_BARE_HOST = re.compile(r"[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*(:\d+)?/?")


def normalise_origin(raw: str) -> str:
    """`scheme://host[:port]`, http(s) only, lower-cased, default port dropped; a path, query or user
    part is refused with ApiError("bad_request"). A bare host (`example.com`) is read as https: the
    person types an address the way a browser accepts it."""
    if not isinstance(raw, str):
        raise _bad("an app must be a web address")
    text = raw.strip()
    if "://" not in text and _BARE_HOST.fullmatch(text):
        text = "https://" + text
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise _bad(f"not a web address: {text[:80]}") from None
    scheme = parts.scheme.lower()
    host = parts.hostname
    if scheme not in _DEFAULT_PORTS or not host:
        raise _bad("an app address must start with http:// or https://")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise _bad("an app address cannot carry a user name")
    if parts.path not in ("", "/") or parts.query or parts.fragment or text.endswith(("?", "#")):
        raise _bad("an app address is the site only, with no path, query or fragment")
    if ":" in host:
        host = f"[{host}]"
    suffix = "" if port is None or port == _DEFAULT_PORTS[scheme] else f":{port}"
    return f"{scheme}://{host}{suffix}"


def _name(v: Any) -> str:
    if not isinstance(v, str):
        raise _bad("name must be text")
    name = " ".join(v.split())
    if not 1 <= len(name) <= NAME_MAX:
        raise _bad(f"name must be 1 to {NAME_MAX} characters")
    return name


def _brief(v: Any) -> str:
    if not isinstance(v, str):
        raise _bad("brief must be text")
    if len(v) > BRIEF_MAX:
        raise _bad(f"brief is over {BRIEF_MAX} characters")
    return v


def _apps(v: Any) -> list[str]:
    if not isinstance(v, list):
        raise _bad("apps must be a list")
    out: list[str] = []
    for item in v:
        origin = normalise_origin(item)
        if origin not in out:
            out.append(origin)
    if len(out) > APPS_MAX:
        raise _bad(f"more than {APPS_MAX} apps")
    return out


def _hue(v: Any) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= HUE_MAX:
        raise _bad(f"hue must be a whole number from 0 to {HUE_MAX}")
    return v


class Spaces:
    def __init__(self, store: Store, busy: Busy, data_dir: Path | None = None) -> None:
        self._store = store
        self._busy = busy
        self._data_dir = data_dir  # where a draft's folder lives (ADR 0007); None = nothing on disk

    def _summary(self, r: sqlite3.Row) -> SpaceSummary:
        counts: SpaceCounts = {"episodes": 0, "facts": 0}
        for c in self._store.query(
            "SELECT kind, COUNT(*) AS n FROM memory WHERE space_id = ? GROUP BY kind", (r["id"],)
        ):
            counts["episodes" if c["kind"] == "episode" else "facts"] = c["n"]
        return {
            "id": r["id"],
            "name": r["name"],
            "brief": r["brief"],
            "apps": json.loads(r["apps"]),
            "hue": r["hue"],
            "created": r["created"],
            "updated": r["updated"],
            "counts": counts,
        }

    def list(self) -> list[SpaceSummary]:
        """Ordered by `updated` desc."""
        rows = self._store.query("SELECT * FROM spaces ORDER BY updated DESC, rowid DESC")
        return [self._summary(r) for r in rows]

    def get(self, space_id: str) -> SpaceSummary:
        """ApiError("unknown_ref") when absent."""
        rows = self._store.query("SELECT * FROM spaces WHERE id = ?", (space_id,))
        if not rows:
            raise ApiError("unknown_ref", "no such project")
        return self._summary(rows[0])

    def exists(self, space_id: str) -> bool:
        """True for CORE and for any space on record."""
        if space_id == "":
            return True
        return bool(self._store.query("SELECT 1 FROM spaces WHERE id = ?", (space_id,)))

    def create(self, body: dict[str, Any]) -> SpaceSummary:
        """`{name, brief?, apps?, hue?}`; caps refused, never cut; the 101st refused."""
        if "name" not in body:
            raise _bad("name is required")
        name = _name(body["name"])
        brief = _brief(body.get("brief", ""))
        apps = _apps(body.get("apps", []))
        hue = _hue(body["hue"]) if "hue" in body else None
        space_id = mint(SPACE_PREFIX)
        now = now_iso()
        with self._store.tx() as db:
            if db.execute("SELECT COUNT(*) FROM spaces").fetchone()[0] >= SPACES_MAX:
                raise _bad(f"at most {SPACES_MAX} projects")
            db.execute(
                "INSERT INTO spaces(id, name, brief, apps, hue, created, updated) VALUES (?,?,?,?,?,?,?)",
                (
                    space_id,
                    name,
                    brief,
                    json.dumps(apps),
                    hue if hue is not None else int(space_id[len(SPACE_PREFIX) :], 16) % (HUE_MAX + 1),
                    now,
                    now,
                ),
            )
        return self.get(space_id)

    def update(self, space_id: str, patch: dict[str, Any]) -> SpaceSummary:
        current = self.get(space_id)  # unknown_ref first
        name = _name(patch["name"]) if "name" in patch else current["name"]
        brief = _brief(patch["brief"]) if "brief" in patch else current["brief"]
        apps = _apps(patch["apps"]) if "apps" in patch else current["apps"]
        hue = _hue(patch["hue"]) if "hue" in patch else current["hue"]
        self._store.run(
            "UPDATE spaces SET name = ?, brief = ?, apps = ?, hue = ?, updated = ? WHERE id = ?",
            (name, brief, json.dumps(apps), hue, now_iso(), space_id),
        )
        return self.get(space_id)

    def erase(self, space_id: str) -> SpaceErased:
        """Under `busy.closing`: deletes stamped memory, the conversation, cards, drafts (rows, then
        their folders once the rows are gone), every twin and its parts, then the space."""
        if space_id == "" or not self.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        with self._busy.closing(space_id), self._store.tx() as db:
            counts = {
                r["kind"]: r["n"]
                for r in db.execute(
                    "SELECT kind, COUNT(*) AS n FROM memory WHERE space_id = ? GROUP BY kind", (space_id,)
                )
            }
            turns = db.execute("SELECT COUNT(*) FROM turns WHERE space_id = ?", (space_id,)).fetchone()[0]
            drafts = [r[0] for r in db.execute("SELECT id FROM drafts WHERE space_id = ?", (space_id,))]
            for table in ("memory", "turns", "cards", "page_reads", "drafts", *TWIN_TABLES):
                db.execute(f"DELETE FROM {table} WHERE space_id = ?", (space_id,))
            db.execute("DELETE FROM spaces WHERE id = ?", (space_id,))
            db.execute(
                "UPDATE settings SET value = '' WHERE key = ? AND value = ?", (ACTIVE_SPACE_KEY, space_id)
            )
        for draft_id in drafts:
            remove_folder(self._data_dir, draft_id)
        return {
            "id": space_id,
            "episodes": counts.get("episode", 0),
            "facts": counts.get("fact", 0),
            "turns": turns,
        }
