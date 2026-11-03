# 0021 - The project report is also a view inside agent hosts

Status: accepted
Date: 2026-11-03

## Context

Athena's MCP server ([ADR 0015](0015-athenas-tools-reach-every-engine-through-one-mcp-server.md)) hands an outside agent the action catalog under a lease for one project. The project's report ([ADR 0018](0018-projects-keep-records-and-her-report-is-composed-from-a-closed-kit.md)) is the one place where a business's state is shown. Until now it was only drawn in the desktop app. An agent host that asked "how is the channel doing" had `record_list` and nothing else: raw revisions, which it had to count itself. A count made by a model is exactly what ADR 0018 forbids.

The MCP Apps extension (`io.modelcontextprotocol/ui`, spec 2026-01-26, stable) lets a tool name a `ui://` resource that a host renders in a sandboxed frame. The view speaks JSON-RPC over `postMessage`: `ui/initialize`, then `ui/notifications/tool-input` and `ui/notifications/tool-result`. Hosts differ in what they render. Some render nothing and read only the text.

## Decision

- **One journey tool, `show_report`.** It is "show this project's report", not a wrapper over the report's routes. It takes no arguments. The project is the lease's, so a lease can never name another project's report.
  - It is a catalog action (`auto`) and passes the lease's door like every other tool. A tool the lease does not offer answers "There is no such tool here."
  - It is offered only on a lease with no tool list of its own (`POST /mcp/lease`, an outside client), and only on a project that keeps records. A turn's own lease names its chat tools, so the in-app model never sees it: the app already draws the report.
  - The MCP door answers it itself (`mcp_views.call`), not `turn.dispatch`. Its result carries `structuredContent`, which `Dispatched` cannot carry, and no turn ever calls it. The class still comes from `CATALOG`.
- **The text stands alone.** The first content block is the whole report in plain lines: the title, the callout, then each part's figures and rows. It is fenced as record data, not instructions. A host that never renders a view loses nothing but the layout.
- **The structure carries only computed numbers.** `structuredContent` is a projection of `report.compose.view`, the same validated spec and computed values the app draws. Each part has a title, at most five figures and five rows, and a count of what was left out. No span, limit or other number the spec wrote reaches the host.
- **The view is read-only and self-contained.** `ui://athena/report` (`text/html;profile=mcp-app`) is listed and read only while its tool is offered. Any other URI answers `-32002`.
  - Inline style and script, no external origin. It declares no `csp`, so the host's restrictive default holds.
  - The bridge is the standard one only: `ui/initialize` (declaring `inline` as its one display mode), `ui/notifications/initialized`, the tool result, `host-context-changed`, `size-changed`, and an answer to `ui/resource-teardown`.
  - It follows the host's theme (`hostContext.theme`) and its standard style variables, and falls back to the desktop's tokens.
  - Every string is written with `textContent`. It has no nested scroll and no actions.
- **No handoff link.** The desktop app registers no URL scheme (no deep-link plugin; its routes are in-window hashes). So the view offers no `ui/open-link` action and no scheme was invented. When the app gains a scheme, the one handoff is "open this project in Athena", carrying the project id and nothing else.
- **The server advertises** `capabilities.resources` and `capabilities.extensions["io.modelcontextprotocol/ui"]: {}` (the extensions framework's server shape). `_meta.ui` is sent to every client, whether or not it advertised the extension. The door keeps no per-client state, and the text fallback is complete either way.

## Deliberately not done

- No write actions in the view: no verdicts, pins or signatures. Consent stays in the app's cards.
- No view-to-model messages (`ui/message`, `ui/update-model-context`). Those are injection surfaces into the host's conversation.
- No app-only tools, no fullscreen and no picture-in-picture.
- No serialized JSON copy of the structure in a second text block. The core spec asks for one "for backwards compatibility". The readable text serves a text-only host better, and the JSON would double what the model reads.

## Consequences

- An agent host can show where a business stands without counting anything itself, and every figure traces to a records query, as in the app.
- A new view is one tool in `mcp_views`, one `CATALOG` entry and one HTML file under `src/athena/views/`.
- The view's look is plain on purpose. Its class names are the hook for the design contest.
- The view has not been rendered in a real host yet. The tests drive the route and check the document, not a host's frame.
