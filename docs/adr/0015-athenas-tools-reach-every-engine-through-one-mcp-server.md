# 0015 - Athena's tools reach every engine through one MCP server

Status: accepted; decision 3's "`readOnlyHint` for AUTO" superseded by [0023](0023-a-tools-hints-come-from-what-it-writes-and-every-refusal-is-an-error.md) (the hint is read from what an action writes, and every refusal is an error)
Date: 2026-10-31

## Context

The business channel (docs/concepts/business-channel, gap G0) needs an engine that really calls tools:
open a page, read it, find a field, and then ask for a signature. Until now the Claude Code engine ran
with every tool off (`--tools ""`, ADR 0006) and spoke op lines that Athena parsed, so it could never
use an MCP server or a skill, and any tool it might reach on its own (its own browser, a peer's MCP)
would bypass the gate, the cards and the ledger. The plan's wave 2 chose "tools on, but only Athena's
MCP server": the engine calls tools, and every call still passes Athena's gate.

## Decision

1. **The daemon serves MCP at `POST /mcp`** on its loopback port: JSON-RPC 2.0, one message per
   request (Streamable HTTP with JSON replies only, no SSE); `initialize`, `ping`, `tools/list`,
   `tools/call`; a notification answers 202. Unknown methods (Claude Code sends `server/discover`
   first) answer -32601 and the client carries on.
2. **The bearer is a lease, never the daemon's token.** A lease names one project, the tools it may
   see, and when it ends (30 minutes by default, 4 hours at most). A turn mints one for its own run
   and drops it when the run ends; `POST /mcp/lease` (behind the daemon's token) mints one for any
   other client, such as the scripted session. The daemon's token is refused at `/mcp`, and a lease
   is refused everywhere else.
3. **The tools are the action catalog, and one function runs them.** `turn.dispatch` is the single
   path for a catalog call from a turn's round (op lines, Muse function calling) and from the MCP
   server, so the class always comes from `CATALOG`, never from the caller: AUTO runs and answers;
   GATED files a card and answers `structuredContent: {pending: {card_id}}`. The card runs once,
   when the person signs it, through the existing gate (which now keeps the run's words as the card's
   `outcome`). Tool annotations: `readOnlyHint` for AUTO, `destructiveHint` for GATED.
4. **Claude Code runs with tools on for a chat turn** (measured on 2.1.316, 2026-10-31): the same
   flags as ADR 0006, `--tools ""` still turning every built-in off, plus `--mcp-config` naming only
   Athena's server with the lease as its `Authorization` header, `--strict-mcp-config`,
   `--allowedTools` naming exactly the turn's tools as `mcp__athena__<tool>`, and `--max-turns 16`.
   The init line then lists only `mcp__athena__*` tools. The CLI runs its own loop; the turn reads
   its stream and the server's lines and cards through the lease, in order, as one `TurnEvent`
   stream. One ledger row covers the run. `ATHENA_CLAUDE_TOOLS=0` turns it back to op lines; the
   stage, the bench and the rehearsals keep op lines (their tools are not the catalog's).
5. **The Muse API carries the same catalog as function calling** through the round loop and
   `dispatch`; nothing is MCP-specific in the actions.

## Measured

- A stub server on the loopback with one `recall` tool, `claude -p` with the flags above (2.1.316,
  sonnet, n=1): init listed `["mcp__athena__recall"]`, the server saw `server/discover`, `initialize`,
  `notifications/initialized`, `tools/list`, `tools/call`, each with the bearer; 2 turns, $0.0053
  (CLI's own figure, est.).
- The live turn on the real daemon and her browser is in the concept doc's Phase 0 section.

## Consequences

- A tool-calling engine and an external agent see one catalog behind one gate; adding an action is
  one entry in `CATALOG` and one branch of `dispatch`.
- A Claude Code chat turn may make up to 16 model calls instead of six; its cost is still one row.
- A lease file (the MCP config with the token) exists only in the run's temporary folder.
- Peer tools (`<peer>__<tool>`, Phase 3) arrive through the same `tools/list` with the peer's
  annotations; the class still comes from Athena.
