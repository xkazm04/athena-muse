"""Outside agents a person connects to one project (spark agent-leases).

An agent works through Athena's MCP server (ADR 0015) under a lease the person minted for it: a name
(`label`), the tools it may use (by default the collaboration set: the project's app tools,
`app_fetch`, `file_list`, `show_report`, `card_status` and the notes), how long it lasts, and
optionally unattended calls (:mod:`athena.agents.ceiling`) that only run once the person signs the
`agent_grant` card filed at the mint.

The rows (`agent_leases`) are kept so the window can show who was connected; a token lives only in
memory (`daemon.mcp`), so a daemon that starts again ends every lease it finds. An ended lease is
listed for an hour, then dropped. Both tables are erased with the project.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from athena.agents.ceiling import Ceiling, check, whole
from athena.agents.notes import Notes
from athena.clock import mint, now_iso
from athena.contracts import (
    AGENT_LABEL_MAX,
    AGENT_MINUTES_DEFAULT,
    AGENT_MINUTES_MAX,
    AGENTS_MAX,
    AgentConnect,
    AgentLease,
    AgentState,
    Card,
)
from athena.errors import ApiError
from athena.store import Store

if TYPE_CHECKING:
    from athena.app import Daemon
    from athena.mcp import Lease, Leases

#: The tools only an agent's lease is offered.
AGENT_NAMES = ("card_status", "note_add", "note_list")
#: How long an ended lease stays in the list.
ENDED_KEPT = timedelta(hours=1)
GONE = "That agent is no longer connected, so nothing was allowed."


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _when(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _and(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def default_tools(daemon: Daemon, space_id: str) -> list[str]:
    """The collaboration set: the project's app tools, `app_fetch` when it has apps, `file_list`,
    `show_report` when the project offers it, and the agent's own tools."""
    from athena import mcp_views
    from athena.apps import tools as apps_tools

    apps = apps_tools.classes(daemon, space_id)
    names = [n for n in apps if n != apps_tools.FETCH]
    if apps_tools.FETCH in apps:
        names.append(apps_tools.FETCH)
    names.append("file_list")
    names += [t["function"]["name"] for t in mcp_views.offered(daemon, space_id)]
    return [*names, *AGENT_NAMES]


def offered_names(daemon: Daemon, space_id: str) -> set[str]:
    """Every name an agent's lease may be given: what the project offers an outside client (her
    browser's tools included, which come and go with the desktop) and the agent's own tools."""
    from athena import mcp
    from athena.browser import actions as browser

    probe = mcp.Lease("", space_id, 0.0, "")
    names = {t["function"]["name"] for t in mcp._offered(daemon, probe)}
    return names | set(browser.NAMES) | set(AGENT_NAMES)


class Agents:
    def __init__(self, store: Store, leases: Leases) -> None:
        self._store = store
        self._leases = leases
        self._lock = threading.Lock()
        self.notes = Notes(store)
        # A token never outlives the daemon: every lease a start finds was ended by the last stop.
        store.run("UPDATE agent_leases SET revoked = ? WHERE revoked IS NULL", (now_iso(),))

    # --- the mint -------------------------------------------------------------------------------

    def connect(self, daemon: Daemon, space_id: str, body: Any) -> AgentConnect:
        """POST /spaces/{id}/agents: checks the body, mints the lease, files the grant card when it
        asks for unattended calls. Raises ApiError in plain words."""
        from athena.apps import tools as apps_tools

        if space_id == "" or not daemon.spaces.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        if not isinstance(body, dict):
            raise ApiError("bad_request", "send a JSON object")
        if daemon.mcp_url is None:
            raise ApiError("bad_request", "Athena cannot take an agent right now; try again in a moment")
        raw_label = body.get("label")
        label = " ".join(raw_label.split()) if isinstance(raw_label, str) else ""
        if not 1 <= len(label) <= AGENT_LABEL_MAX:
            raise ApiError("bad_request", f"Name the agent in 1 to {AGENT_LABEL_MAX} characters")
        minutes = AGENT_MINUTES_DEFAULT
        if body.get("minutes") is not None:
            minutes = whole(body.get("minutes"), 1, AGENT_MINUTES_MAX, "The minutes")
        tools = self._tools(daemon, space_id, body.get("tools"))
        app_tools = [n for n in apps_tools.classes(daemon, space_id) if n != apps_tools.FETCH]
        limits = check(body["ceiling"], app_tools, tools) if body.get("ceiling") is not None else None
        with self._lock:
            live = [h for h in self._leases.agents() if h.space_id == space_id]
            if len(live) >= AGENTS_MAX:
                raise ApiError(
                    "bad_request",
                    f"This project already has {AGENTS_MAX} agents connected. End one before "
                    "connecting another.",
                )
            if any((h.label or "").casefold() == label.casefold() for h in live):
                raise ApiError(
                    "bad_request",
                    f"An agent named {label} is already connected here. Give this one another name.",
                )
            lease_id = mint("agt_")
            ceiling: Ceiling | None = None
            if limits is not None:
                names, max_calls, ceiling_minutes, file_bytes = limits
                deadline = datetime.now(UTC) + timedelta(minutes=ceiling_minutes)
                ceiling = Ceiling(names, max_calls, deadline.timestamp(), file_bytes)
            lease = self._leases.mint(
                space_id,
                ttl=minutes * 60.0,
                tools=frozenset(tools),
                lease_id=lease_id,
                label=label,
                ceiling=ceiling,
            )
            expires = lease.expires.replace("+00:00", "Z")
            self._store.run(
                "INSERT INTO agent_leases(id, space_id, label, client, tools, ceiling_json, card_id, created,"
                " expires, revoked) VALUES (?,?,?,NULL,?,?,NULL,?,?,NULL)",
                (
                    lease_id,
                    space_id,
                    label,
                    json.dumps(tools),
                    json.dumps(ceiling.stored()) if ceiling is not None else None,
                    now_iso(),
                    expires,
                ),
            )
        if ceiling is not None and limits is not None:
            card = daemon.gate.file(
                space_id,
                "agent_grant",
                {"lease_id": lease_id, "tools": ceiling.tools, "max_calls": ceiling.max_calls},
                self._grant_label(daemon, space_id, label, ceiling, limits[2]),
            )
            with ceiling.lock:
                ceiling.card_id = card["id"]
                self.kept(lease)
        assert daemon.mcp_url is not None
        config = {
            "mcpServers": {
                "athena": {
                    "type": "http",
                    "url": daemon.mcp_url,
                    "headers": {"Authorization": f"Bearer {lease.token}"},
                }
            }
        }
        return {
            "lease": self.view(daemon, lease_id),
            "url": daemon.mcp_url,
            "token": lease.token,
            "config": json.dumps(config, indent=2),
        }

    def _tools(self, daemon: Daemon, space_id: str, raw: Any) -> list[str]:
        if raw is None:
            return default_tools(daemon, space_id)
        if not isinstance(raw, list) or not raw or not all(isinstance(n, str) for n in raw):
            raise ApiError("bad_request", "name the tools the agent may use, as a list")
        names = list(dict.fromkeys(raw))
        unknown = [n for n in names if n not in offered_names(daemon, space_id)]
        if unknown:
            raise ApiError("bad_request", f"This project has no tool called {_and(unknown)}")
        return names

    def _grant_label(self, daemon: Daemon, space_id: str, label: str, ceiling: Ceiling, minutes: int) -> str:
        from athena.apps import tools as apps_tools

        said: list[str] = []
        for name in ceiling.tools:
            entry = apps_tools.entry(daemon, space_id, name)
            said.append(f"{entry.tool['name']} in {entry.where}" if entry is not None else name)
        times = "once" if ceiling.max_calls == 1 else f"up to {ceiling.max_calls} times"
        span = "1 minute" if minutes == 1 else f"{minutes} minutes"
        return f"Let {label} run {_and(said)} {times} for {span} without asking"

    # --- what the window and the server read ----------------------------------------------------

    def view(self, daemon: Daemon, lease_id: str) -> AgentLease:
        rows = self._store.query("SELECT * FROM agent_leases WHERE id = ?", (lease_id,))
        if not rows:
            raise ApiError("unknown_ref", "no such agent")
        return self._view(daemon, rows[0])

    def _view(self, daemon: Daemon, row: Any) -> AgentLease:
        live = self._leases.agent(row["id"]) if row["revoked"] is None else None
        state: AgentState = "ended"
        if live is not None:
            state = "connected"
            ceiling = live.ceiling
            if ceiling is not None and not ceiling.signed and ceiling.card_id is not None:
                try:
                    if daemon.gate.get(ceiling.card_id)["state"] == "waiting":
                        state = "waiting"
                except ApiError:
                    pass
        out: AgentLease = {
            "id": row["id"],
            "space_id": row["space_id"],
            "label": row["label"],
            "state": state,
            "created": row["created"],
            "expires": row["expires"],
            "tools": json.loads(row["tools"]),
            "notes": self.notes.count(row["id"]),
        }
        client = live.client if live is not None and live.client else row["client"]
        if client:
            out["client"] = client
        if live is not None and live.ceiling is not None:
            out["ceiling"] = live.ceiling.view()
        elif row["ceiling_json"]:
            stored = json.loads(row["ceiling_json"])
            stored.pop("fetched", None)
            out["ceiling"] = stored
        return out

    def list(self, daemon: Daemon, space_id: str) -> list[AgentLease]:
        """Newest first; an ended lease is listed for an hour after it ended, then dropped."""
        if space_id == "" or not daemon.spaces.exists(space_id):
            raise ApiError("unknown_ref", "no such project")
        rows = self._store.query(
            "SELECT * FROM agent_leases WHERE space_id = ? ORDER BY rowid DESC", (space_id,)
        )
        now = datetime.now(UTC)
        out: list[AgentLease] = []
        for row in rows:
            view = self._view(daemon, row)
            if view["state"] == "ended":
                ended = _when(row["revoked"]) if row["revoked"] else _when(row["expires"])
                if now - ended > ENDED_KEPT:
                    self._store.run("DELETE FROM agent_leases WHERE id = ?", (row["id"],))
                    continue
            out.append(view)
        return out

    # --- changes ---------------------------------------------------------------------------------

    def revoke(self, daemon: Daemon, space_id: str, lease_id: str) -> AgentLease:
        """Ends the lease at once: its token is dropped and its unattended calls stop."""
        rows = self._store.query(
            "SELECT id FROM agent_leases WHERE id = ? AND space_id = ?", (lease_id, space_id)
        )
        if not rows:
            raise ApiError("unknown_ref", "no such agent")
        self._end(self._leases.agent(lease_id))
        self._store.run(
            "UPDATE agent_leases SET revoked = ? WHERE id = ? AND revoked IS NULL", (now_iso(), lease_id)
        )
        return self.view(daemon, lease_id)

    def _end(self, lease: Lease | None) -> None:
        if lease is None:
            return
        if lease.ceiling is not None:
            with lease.ceiling.lock:
                lease.ceiling.ended = True
        self._leases.drop(lease.token)

    def forget_space(self, space_id: str) -> None:
        """The project is erased (its rows went with it): every live agent token of it ends."""
        for lease in self._leases.drop_agents(space_id):
            if lease.ceiling is not None:
                with lease.ceiling.lock:
                    lease.ceiling.ended = True

    def announced(self, lease_id: str, client: str) -> None:
        """The name the agent's host gave at `initialize`."""
        self._store.run("UPDATE agent_leases SET client = ? WHERE id = ?", (client, lease_id))

    def kept(self, lease: Lease) -> None:
        """Writes the lease's unattended calls as they stand. Called under the ceiling's lock."""
        if lease.ceiling is None or lease.lease_id is None:
            return
        self._store.run(
            "UPDATE agent_leases SET ceiling_json = ?, card_id = ? WHERE id = ?",
            (json.dumps(lease.ceiling.stored()), lease.ceiling.card_id, lease.lease_id),
        )

    def sign(self, card: Card) -> str:
        """A signed `agent_grant` card: the lease's unattended calls may run from now on. A lease that
        ended (or a card that is not its grant) allows nothing."""
        lease = self._leases.agent(str(card["args"].get("lease_id", "")))
        ceiling = lease.ceiling if lease is not None else None
        if lease is None or ceiling is None:
            return GONE
        with ceiling.lock:
            if ceiling.ended or ceiling.card_id != card["id"]:
                return GONE
            ceiling.signed = True
            self.kept(lease)
        return f"{lease.label} may now run those calls without asking, within the limits you set."
