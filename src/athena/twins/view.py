"""A twin as the wire shows it: `TwinSummary` (a row of the ledger), `TwinDetail` (the document) and the
overview `TwinPage`. The daemon owns every derived number here: coverage, ready and readiness from
the pieces, a channel's health from when it last spoke, the week's figures from the ledger, and the
stat strip from the rows, exactly as the prototype's SCHEMA computes them. An unmeasured figure is an
omitted key ("-" on screen), never 0.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from athena.app import Daemon
from athena.contracts import (
    ChannelKind,
    MemoryFact,
    Mission,
    MissionTurn,
    NotionPage,
    Sample,
    TwinChannel,
    TwinDetail,
    TwinPage,
    TwinStats,
    TwinSummary,
    TwinWeek,
)
from athena.twins import catalogue, style
from athena.twins.rubric import coverage, piece, readiness, ready
from athena.twins.store import Twins

ACTIVE_HOURS = 24  # a channel that spoke within this long is active
QUIET_DAYS = 14  # within this long quiet, else stale
WEEK_DAYS = 7


def _now() -> datetime:
    return datetime.now(UTC)


def _parse(iso: str) -> datetime | None:
    try:
        when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo is not None else when.replace(tzinfo=UTC)


def health(last_at: str, now: datetime) -> str | None:
    """active, quiet or stale by when the channel last spoke; None when it never has."""
    when = _parse(last_at) if last_at else None
    if when is None:
        return None
    if now - when <= timedelta(hours=ACTIVE_HOURS):
        return "active"
    return "quiet" if now - when <= timedelta(days=QUIET_DAYS) else "stale"


def channels(daemon: Daemon, twin_id: str) -> list[TwinChannel]:
    out: list[TwinChannel] = []
    now = _now()
    for row in daemon.twins.rows("channels", twin_id):
        kind = cast("ChannelKind", row["id"])
        conn = daemon.connectors.connection(kind)
        channel: TwinChannel = {
            "kind": kind,
            "account": conn.get("account", ""),
            "status": conn["status"],
            "autonomy": row["autonomy"],
            "bar": int(row["bar"]),
        }
        if row.get("split"):
            channel["split"] = row["split"]
        if row.get("scope"):
            channel["scope"] = row["scope"]
        said = health(row.get("last_at", ""), now)
        if said is not None:
            channel["health"] = cast("Any", said)
            channel["last_at"] = row["last_at"]
        out.append(channel)
    return out


def connected(daemon: Daemon) -> set[str]:
    return {c["kind"] for c in daemon.connectors.connections()["connections"] if c["status"] == "connected"}


def mission(twins: Twins, row: dict[str, Any]) -> Mission:
    body = {k: v for k, v in row.items() if not k.startswith("_")}
    body["turns"] = [cast("MissionTurn", t) for t in twins.rows("turns", row["id"])]
    return cast("Mission", body)


def missions(twins: Twins, twin_id: str) -> list[Mission]:
    return [mission(twins, m) for m in twins.rows("missions", twin_id)]


def week(daemon: Daemon, space_id: str) -> TwinWeek:
    """The last seven days. What a twin sent is the missions' (WP4); the cost is its Project's ledger
    rows on surface `twin`, omitted until one of them was priced."""
    since = (_now() - timedelta(days=WEEK_DAYS)).isoformat(timespec="seconds").replace("+00:00", "Z")
    row = daemon.store.query(
        "SELECT COUNT(cost_usd) AS n, COALESCE(SUM(cost_usd), 0.0) AS cost FROM ledger"
        " WHERE surface = 'twin' AND space_id = ? AND ts >= ?",
        (space_id, since),
    )[0]
    out: TwinWeek = {}
    if row["n"]:
        out["cost_usd"] = round(float(row["cost"]), 4)
    return out


def _name_and_purpose(daemon: Daemon, twin_id: str, space_id: str) -> tuple[str, str]:
    """The latest `name` and `purpose` pieces; the Project's name until there is a name."""
    name, purpose = "", ""
    for node in daemon.twins.sketch(twin_id)["nodes"]:
        if str(node["kind"]) == "name":
            name = node["label"]
        elif str(node["kind"]) == "purpose":
            purpose = node["label"]
    return name or daemon.spaces.get(space_id)["name"], purpose


def summary(daemon: Daemon, twin_id: str) -> TwinSummary:
    row = daemon.twins.row(twin_id)
    name, purpose = _name_and_purpose(daemon, twin_id, row["space_id"])
    found = missions(daemon.twins, twin_id)
    out: TwinSummary = {
        "id": twin_id,
        "space_id": row["space_id"],
        "name": name,
        "purpose": purpose,
        "state": row["state"],
        "channels": channels(daemon, twin_id),
        "week": week(daemon, row["space_id"]),
        "readiness": readiness(coverage(daemon.twins.sketch(twin_id))),
        "open_missions": sum(m["state"] in ("open", "handed_back") for m in found),
        "waiting_count": 0,  # drafts waiting for a signature are the missions' (WP4)
        "missions": found,
        "waiting": [],
        "created": row["created"],
        "updated": row["updated"],
    }
    if row["since"]:
        out["since"] = row["since"]
    if row["paused_because"]:
        out["paused_because"] = row["paused_because"]
    return out


def samples(twins: Twins, twin_id: str) -> list[Sample]:
    return [cast("Sample", r) for r in twins.rows("samples", twin_id)]


def pages(twins: Twins, twin_id: str) -> list[NotionPage]:
    return [cast("NotionPage", r) for r in twins.rows("pages", twin_id)]


def memory(twins: Twins, twin_id: str) -> list[MemoryFact]:
    """The facts as the wire shows them; the sample a fact came from stays in the store."""
    return [
        cast("MemoryFact", {k: v for k, v in r.items() if k != "sample"})
        for r in twins.rows("memory", twin_id)
    ]


def dials(twins: Twins, twin_id: str) -> list[Any]:
    chosen = {r["id"]: (int(r["value"]), r["source"]) for r in twins.rows("dials", twin_id)}
    return cast("list[Any]", style.dials(chosen))


def detail(daemon: Daemon, twin_id: str) -> TwinDetail:
    twins = daemon.twins
    base = summary(daemon, twin_id)
    sketch = twins.sketch(twin_id)
    cov = coverage(sketch)
    picked = {r["id"] for r in twins.rows("chores", twin_id)}
    out = cast(
        "TwinDetail",
        {
            **base,
            "pieces": [piece(n) for n in sketch["nodes"]],
            "coverage": cov,
            "ready": ready(cov),
            "dials": dials(twins, twin_id),
            "style_presets": list(style.PRESETS),
            "samples": samples(twins, twin_id),
            "pages": pages(twins, twin_id),
            "chores": catalogue.listed(picked, connected(daemon)),
            "memory": memory(twins, twin_id),
        },
    )
    ask = twins.ask(twin_id)
    if ask is not None and base["state"] == "setting_up":
        out["ask"] = ask
    practice = [m for m in base["missions"] if m.get("practice")]
    if practice:
        out["rehearsal"] = practice[-1]
    return out


def _sum(values: list[Any]) -> Any:
    """A stat over the rows: None (omitted) when no row measured it; money to the cent, as SCHEMA's."""
    found = [v for v in values if v is not None]
    if not found:
        return None
    total = sum(found)
    return round(total, 2) if isinstance(total, float) else total


def page(daemon: Daemon) -> TwinPage:
    rows = [summary(daemon, twin_id) for twin_id in daemon.twins.ids()]
    stats: TwinStats = {
        "live": sum(t["state"] == "live" for t in rows),
        "waiting_for_you": sum(
            t["waiting_count"] + sum(m["state"] == "handed_back" for m in t["missions"]) for t in rows
        ),
        "missions_open": sum(t["open_missions"] for t in rows),
    }
    loose = cast("dict[str, Any]", stats)
    for key, field in (
        ("sent_week", "sent"),
        ("sent_alone_week", "sent_alone"),
        ("held_by_risk_week", "held_by_risk"),
        ("cost_usd_week", "cost_usd"),
    ):
        total = _sum([cast("dict[str, Any]", t["week"]).get(field) for t in rows])
        if total is not None:
            loose[key] = total
    return {"twins": rows, "stats": stats}
