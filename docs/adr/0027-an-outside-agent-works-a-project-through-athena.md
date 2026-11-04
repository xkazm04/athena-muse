# 0027 - An outside agent works a project through Athena, under a name and limits the person signs

Status: accepted
Date: 2026-11-04

## Context

Athena was designed around one person. Her MCP server ([ADR 0015](0015-athenas-tools-reach-every-engine-through-one-mcp-server.md)) already let an outside client hold a lease for one project, and a project's app tools, a paired computer's copy included ([ADR 0026](0026-apps-are-offered-across-paired-devices.md)), were in that lease's `tools/list`. An agent such as Claude Code could therefore drive Gravitone on two computers through Athena. Four things stopped it from being useful:

- After a gated call it got back `pending: {card_id}` and had no way to learn the result.
- Leases were anonymous. Cards, the ledger and the offering computer's audit could not say which agent asked.
- Only a script holding the daemon's token could mint a lease.
- An unattended agent stopped at every gated call.

The default lease was also the project's whole outside-client set, browser hands and twin sends included. That is too wide for a config someone copies into another program.

## Decision

1. **The person connects an agent, by name, in the project.** `POST /spaces/{id}/agents` (daemon token) takes the name the person types, a length (at most 4 h), the tools, and optional limits. It answers the lease and an MCP config, shown once. The token is held in memory only. A lease row persists so the list and Revoke survive a reload, and every lease ends when the daemon starts. `POST /mcp/lease` and a turn's own lease are unchanged.
2. **A narrow default.** Without named tools, an agent gets the collaboration set: the project's app tools, `app_fetch`, `file_list`, `show_report`, and three tools only an agent lease is offered: `card_status`, `note_add` and `note_list`.
3. **An agent can read its own cards.** `card_status(card_id, wait_seconds <= 20)` answers `waiting | approved | declined` with the card's outcome fenced as data. It answers `unknown` for any card the lease did not file, so it reveals nothing about other cards.
4. **Who asks is on everything an agent does.** Every card an agent files starts with `<name> asks:`, whatever module files it. The host's own `clientInfo.name` is kept beside the name the person gave it, but is never shown as that name. A call to a paired computer's copy carries the name in the body (`agent`). The offering computer records it in its audit beside the approval id, as text that never decides anything.
5. **Limits signed once, only over app tools.** The person may sign one `agent_grant` card with:
   - named app tools,
   - a call count,
   - a deadline,
   - a file allowance.

   Inside the limits, a gated app call runs without a new card. The count is taken atomically, and the grant card's id is the approval a paired computer records. Anything outside the limits, after the deadline, or once the count is spent is the ordinary card. Her browser, sends, `add_app`, memory, records, setup and the grant itself can never be named. The limits are never raised: a new agent is connected instead.
6. **Notes are append-only and per computer.** Agents leave handoffs (`note_add`, at most 2 000 characters) that any agent of the project and the person can read. They are erased with the project. They do not cross to a paired computer: the app's own state, such as Gravitone's job list, is what two computers share.
7. **An agent on another computer uses that computer's Athena.** No MCP is exposed on the private network and there is no new grant. Two agents cooperate through the same app copies the two Athenas already share (ADR 0026).

## Measured

- `scripts/agents_seam.py` (2026-11-04, 6/6) ran the built daemon on a loopback port, with a project holding the repo's stdio test app.
- It connected an agent through the route, signed limits of one `erase`, and ran `claude -p` 2.1.318 (haiku) with the config exactly as shown.
- The note was kept. The first `erase` ran without a card and the second filed `Seam Claude asks: ...`. `card_status` answered waiting, and after revoke the token got 401. The run took 20 s.

## Consequences

- An unattended agent costs the person one signature per session. Every later call it makes is still visible as a tool line, in the limits' `used` count, and in the offering computer's audit.
- In-limits calls write no ledger row. The ledger counts model calls and an agent's call is not one.
- The offering computer cannot verify a grant card's id, as with any approval id (ADR 0026).
- Agents connected from two computers do not see each other's notes.
