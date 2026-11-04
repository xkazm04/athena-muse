# 0025 - A project's apps have kinds, and each kind is wired its own way

Status: accepted
Date: 2026-11-04

## Context

A project's apps were one list of origins (`spaces.apps`, ADR 0003). The same structure stood for a
public website she drives in her browser and for anything running on this computer: a local web UI,
an app answering on a loopback port, a tool started from a command. `normalise_origin` let
`http://localhost:3000` through as if it were a website, with no kind, no label and no way to say
how she reaches it. There was no client for an app's own tool door: Athena is an MCP server (ADR
0015) but called none. The business channel planned that client as its Phase 3.1, a port of
athena-portable's `connectors/mcp/` (HTTP on loopback only, tested against a fake server only).

The doctrine stands: an app is reached as the owner reaches it, through her browser or the app's own
tool door, never through a wrapper of ours (business-channel design, 2026-10-28).

## Decision

1. **Four kinds.** `website` (a public origin, her browser), `local_page` (a loopback origin, her
   browser), `mcp_http` (an app on this computer answering MCP at a loopback URL), `mcp_stdio` (a tool
   she starts as a child process from argv). A plain command that does not speak MCP is not a kind:
   a CLI comes in through an MCP door of its own. The screen names the kinds in plain words and never
   says "MCP".
2. **Where they live.** The two browser kinds stay the origins in `spaces.apps`; their kind is derived
   from the host, so chores, drafts and the stage read them unchanged. The process kinds, and apps
   wired on this device outside every project, live in a new `apps` table (and `app_remotes`, ADR
   0026), walled and erased with their space. `GET /spaces/{id}/apps` answers all four as one list.
3. **Wiring is per kind.** The owner picks the kind first; each kind has its own short form and a
   probe that shows what was found (the tools, with their class, or the page answering). Her
   `add_app` action carries the kind too and is still a card; a command she proposes is shown verbatim
   on its card, since running it is code execution by configuration.
4. **A local page's trust.** Wiring a `local_page` through the form is its onboarding: it writes the
   project's `sites` row at the gated floor, with no sign-in probe. This amends ADR 0014 for loopback
   origins only; a public site still gets trust only from a chore's onboarding.
5. **The client.** Athena's own: Streamable HTTP on loopback URLs (ported from portable), and stdio
   children it spawns on first use, owns and reaps (after `APP_IDLE_S` unused and at shutdown, the
   process tree ended). A token is pasted once, sealed with the connectors seal, never sent back.
6. **Her tools.** Each app's tools are offered inside the project as `<slug>__<tool>` from the last
   probe. A tool whose annotations say it only reads runs under `app_read` (auto); any other files an
   `app_act` card. `app_fetch` pulls a file from an app's declared output folder into the project's
   files. This absorbs the business channel's Phase 3.1.

## Consequences

- Gravitone is reached as an `mcp_http` app with its own `act` token; its rule that an agent never
  spends holds on its side.
- The tool list is what the last probe saw; a call to an app that went away answers in plain words and
  marks it `unreachable`.
- Website and local-page apps keep the old 24-origin cap; process apps share it per project.
