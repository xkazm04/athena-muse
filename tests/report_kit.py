"""The report's test kit. Records are put with plain SQL into the `records` table, and read back by
`SqlRecords` (the four reads the report uses: latest, count, kinds, on_change), so the report's tests do
not wait on the records package (WP1.1). A `Fake` engine answers the composer from a queue."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from athena.app import Daemon
from athena.clock import mint
from athena.contracts import EngineId, Probe, RecordItem, RecordKind
from athena.engine import EngineError, TextDelta, ToolCall, Usage
from athena.records.store import Records

MUSIC: list[RecordKind] = ["creator", "track", "thread", "agreement", "render", "release", "stat"]


class SqlRecords(Records):
    """The latest revision per key, straight from SQL."""

    def latest(
        self, space_id: str, kind: RecordKind | None = None, key: str | None = None
    ) -> list[RecordItem]:
        sql = (
            "SELECT * FROM records r WHERE space_id = ? AND rev = (SELECT MAX(rev) FROM records"
            " WHERE space_id = r.space_id AND kind = r.kind AND key = r.key)"
        )
        params: list[Any] = [space_id]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        if key is not None:
            sql += " AND key = ?"
            params.append(key)
        rows = self._store.query(sql + " ORDER BY created DESC, rowid DESC", tuple(params))
        return [
            {
                "id": r["id"],
                "space_id": r["space_id"],
                "kind": r["kind"],
                "key": r["key"],
                "rev": r["rev"],
                "body": json.loads(r["body"]),
                "by": r["by"],
                "created": r["created"],
            }
            for r in rows
        ]

    def count(self, space_id: str, kind: RecordKind) -> int:
        return len(self.latest(space_id, kind))

    def kinds(self, space_id: str) -> list[RecordKind]:
        rows = self._store.query("SELECT kinds FROM spaces WHERE id = ?", (space_id,))
        return json.loads(rows[0]["kinds"] or "[]") if rows else []


def use_sql_records(daemon: Daemon) -> Daemon:
    daemon.records = SqlRecords(daemon.store)
    return daemon


def project(daemon: Daemon, kinds: list[RecordKind] = MUSIC, name: str = "Night Drive Music") -> str:
    space_id = daemon.spaces.create({"name": name, "brief": "An AI-music channel"})["id"]
    daemon.store.run("UPDATE spaces SET kinds = ? WHERE id = ?", (json.dumps(kinds), space_id))
    return space_id


_n = [0]


def put(
    daemon: Daemon, space_id: str, kind: RecordKind, key: str, body: dict[str, Any], created: str = ""
) -> None:
    """One revision (rev+1 of its key), written as plain SQL."""
    _n[0] += 1
    created = created or f"2026-10-01T00:00:{_n[0] % 60:02d}Z"
    rev = daemon.store.query(
        "SELECT COALESCE(MAX(rev), 0) + 1 AS r FROM records WHERE space_id = ? AND kind = ? AND key = ?",
        (space_id, kind, key),
    )[0]["r"]
    daemon.store.run(
        "INSERT INTO records(id, space_id, kind, key, rev, body, by, created) VALUES (?,?,?,?,?,?,?,?)",
        (mint("rec_"), space_id, kind, key, rev, json.dumps(body), "athena", created),
    )


def track(daemon: Daemon, space_id: str, n: int, **extra: Any) -> str:
    url = f"https://example.test/song/{n}"
    body = {"url": url, "title": f"Song {n}", "creator_key": "c1", "found_at": "2026-10-01T00:00:00Z"}
    put(daemon, space_id, "track", url, {**body, **extra}, created=f"2026-10-0{1 + n % 9}T00:00:00Z")
    return url


def stat(daemon: Daemon, space_id: str, metric: str, value: float, at: str) -> None:
    put(daemon, space_id, "stat", f"{metric}@{at}", {"metric": metric, "value": value, "measured_at": at})


class Fake:
    """A composer that answers from a queue (a string each), or raises when `fail` is set."""

    id: EngineId = "scripted"
    model = "fake"
    simulated = True
    cost_estimated = False

    def __init__(self, answers: list[str] | None = None, fail: str = "") -> None:
        self.answers = list(answers or [])
        self.fail = fail
        self.asked: list[list[dict[str, Any]]] = []

    def probe(self) -> Probe:
        return {"ok": True}

    def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> Iterator[TextDelta | ToolCall | Usage]:
        self.asked.append(messages)
        if self.fail:
            raise EngineError(self.fail)
        answer = self.answers.pop(0) if self.answers else "I would rather not."
        yield TextDelta(answer)
        yield Usage(input_tokens=100, output_tokens=50)


def spec(*blocks: dict[str, Any], title: str = "Night Drive", callout: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"v": 1, "vocab": 1, "title": title, "blocks": list(blocks)}
    if callout is not None:
        out["callout"] = callout
    return out


def block(block_id: str, kind: str, title: str = "A block", span: int = 6, **rest: Any) -> dict[str, Any]:
    return {"id": block_id, "kind": kind, "title": title, "span": span, "config": {}, **rest}
