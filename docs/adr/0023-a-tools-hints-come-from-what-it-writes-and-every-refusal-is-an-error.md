# 0023 - A tool's hints come from what it writes, and every refusal is an error

Status: accepted
Date: 2026-11-03

## Context

[ADR 0015](0015-athenas-tools-reach-every-engine-through-one-mcp-server.md) decision 3 set the MCP annotations from the consent class: `readOnlyHint` for AUTO, `destructiveHint` for GATED. The class answers whether a call needs a signature. It does not answer whether the call changes anything. `remember` and `record_put` are AUTO and they write, so an agent host that trusts `readOnlyHint` would treat them as safe to run without asking its own user.

When A3 built the in-host view ([ADR 0021](0021-the-project-report-is-also-a-view-inside-agent-hosts.md)), it changed two rules in code without writing them down:

- `readOnlyHint` comes from a `WRITES` table in `mcp.py`, held to the catalog by a test.
- A refusal answers `isError: true`.

The door inferred a refusal from the dispatch's result: no streamed line and no card meant refused. Two browser paths broke that inference because they stream a line when they fail. One is `page_open` on a site the person is signed out of ("Not signed in to ..."). The other is an AUTO page hand whose browser call fails. Both answered `isError: false`, so a host read a failure as a success. Two more paths failed in the same way: `page_open` whose browser call fails, which also streamed "Opened ...", and `tabs_read` with no answer from her browser.

## Decision

- **`readOnlyHint` is read from `WRITES`, never from the consent class.** Each catalog action says whether running it changes anything: memory, the project, a record, a sketch, her browser (a tab opened or scrolled), or the world. A name outside the catalog is never read-only. `destructiveHint` stays "not AUTO", and `openWorldHint` stays "a page hand". This supersedes the "`readOnlyHint` for AUTO" clause of ADR 0015 decision 3. The rest of decision 3 stands.
- **A refusal is flagged where it is decided.** `Dispatched.refused` is set by the branch that refuses, in `turn.dispatch`, `browser.actions.act`, `records.actions.act` and `report.chat.act`. Refusals include a bad argument, no project, a kind the project does not keep, a site signed out, a missing tab or file, a browser call that failed, and report parts of which none could be shown. A refusal may still stream a line that says what happened. The `page_open` whose open failed now says "Could not open ...", never "Opened ...".
- **The MCP door reads the flag** (`mcp.call_tool`: `isError = done.refused`) and infers nothing. A call that ran, or that filed a card, is not an error. Every refusal is an error, and so is an `ApiError` raised mid-call.

## Consequences

- A new dispatch branch must set `refused` on each refusal it returns. Leaving it out reads as success at the door. `tests/test_mcp_refusals.py` holds the four browser failure paths, and `tests/test_mcp_server.py` holds the sweep of argument refusals.
- The chat turn is unchanged. The model reads the same result text, and the person sees the same lines, except "Could not open ..." where "Opened ..." was false.
