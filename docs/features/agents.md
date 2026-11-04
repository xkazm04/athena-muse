# Agents - let an outside agent use a project

Built 2026-11-04. Decision: [ADR 0027](../adr/0027-an-outside-agent-works-a-project-through-athena.md). Builds on her MCP server (ADR 0015) and on [Apps](apps.md) (ADRs 0025, 0026).

## What it does

A project's **Agents** section, below Apps, lets the person hand the project to another agent, such as Claude Code or a script, with Athena still in the middle:

- **Let an agent use this project** asks for:
  - a name;
  - how long (30 min, 1 h or 4 h);
  - which parts it may use: the apps, bringing files home, notes, and the report;
  - optionally, **calls it may run without asking**: the app tools that ask first which it may run unattended, up to N times, for M minutes, with files up to X MB.
- The MCP config is then shown **once**, with Copy. It is gone from the screen when closed.
- Limits wait for one signature, a card like any other ("Let Seam Claude run ... without asking"). Until it is signed, every call the agent makes that asks first is an ordinary card.
- The list shows each agent's name and the program it is, where it stands (waiting for your signature, connected and when it ends, ended), "x of y" calls used, and its notes. **Revoke** ends it at once.
- An agent's cards say who asks ("Claude asks: ..."). The agent can read the answer to its own cards and leave notes for the next agent.

An agent on another computer is connected in that computer's Athena, to its project. The two cooperate through the app copies the computers share ([Apps](apps.md)): Gravitone's own job list is the state both see.

## How it works

- `src/athena/agents/`:
  - `store.py`: leases (`agent_leases`), connect, list, revoke and sign, erased with the project and ended on start.
  - `ceiling.py`: the pure rule plus an atomic take.
  - `tools.py`: `card_status`, the notes, unattended calls and the file allowance.
  - `notes.py`.
  - `routes.py`: `/spaces/{id}/agents*` and `/spaces/{id}/agent-notes`.
- `mcp.py` keeps the lease's name, the host's name and its limits. `gate.py` prefixes an agent's cards. `peer/apps.py` carries `agent` to the offering computer's audit.
- Screens: `apps/desktop/src/main/projects/agents/`.

## Verified

- Tests:
  - `tests/test_agents_ceiling.py`, `test_agents_leases.py`, `test_agents_unattended.py` (eight calls at once against five allowed run five and file three), and `test_agents_peer.py`, which runs two daemons and checks the audit keeps the name beside the grant.
  - Desktop `main/projects/agents/agents.test.tsx`: every state at two widths, the config shown once and never in a name, the exact request body, focus, and banned words. Also `agents.css.test.ts`.
- **The seam** (`scripts/agents_seam.py`, 2026-11-04, 6/6): a real `claude -p` (2.1.318, haiku) on the built daemon with the config as shown. It covers:
  - the note;
  - one unattended call, then a card that says who asks;
  - `card_status` waiting;
  - revoke refusing the token.

## Open

- The seam's app is the repo's stdio test app. An agent on real Gravitone, on two computers, belongs to the two-computer owner run in [Apps](apps.md#open).
- Not yet seen in a running Tauri window.
- Notes per agent filter by name, which is unique among live agents.
