# Apps - wired by kind, and shared between paired computers

Built 2026-11-04. Decisions: [ADR 0025](../adr/0025-a-projects-apps-have-kinds.md) (kinds, wiring, the client, her tools) and [ADR 0026](../adr/0026-apps-are-offered-across-paired-devices.md) (offered apps, the `apps` grant, splitting work across two computers). Absorbs the business channel's Phase 3.1 (the client for an app's own tool door).

## What it does

A project's **Apps** section (the project page) lists its apps in four kinds, each named in plain words:

- **A website** - a public address her browser opens. Trust still comes only from a chore's onboarding (ADR 0014).
- **A page on this computer** - a localhost address her browser opens. Adding it here is its onboarding: the project's site is written at once, so her page hands run at their own class (a click is still a card).
- **An app on this computer** - an app whose tools answer at a localhost address (Gravitone's agent door). An access key, if it needs one, is pasted once, sealed, and never shown again.
- **A tool she starts** - a command she runs as a child process when she needs it, stopped after ten minutes unused and when the daemon ends.

**Add app** asks for the kind first, then that kind's short form; a check runs at once and shows what it found: the tools, each marked "on its own" or "asks you first", or the reason it could not reach it. An app found unreachable keeps its tools; a later call tries again.

For the two program kinds, the row shows its **copies**: this computer, and any paired computer's copy attached with **Add <device>'s copy** (and taken off with **Detach**). In **Settings > Devices**, **Apps this computer offers** wires programs at device level, outside every project: switched to *offered*, they can be used by paired computers that hold the "use the apps this computer offers" permission, and files may be brought from the one output folder named there.

Her side: inside the project she is offered each tool as `<app>__<tool>`, and each paired copy's as `<app>_on_<device>__<tool>`, so she can split one job across both computers herself. A tool that only reads runs at once (`app_read`); any other files a card (`app_act`), on this computer, even for the other computer's copy. `app_fetch` brings a file from an app's output folder into the project's files. She can also propose an app with `add_app` by kind; a command she proposes is shown word for word on its card.

## How it works

- **Where apps live.** The two browser kinds stay the origins in `spaces.apps`, so chores, drafts and the stage read them unchanged; the kind is derived from the host. Programs, device-level apps and attached copies are the `apps` and `app_remotes` tables, erased with their project (`src/athena/apps/store.py`). Routes: `src/athena/apps/routes.py` (`/spaces/{id}/apps*`, `/apps*`).
- **The client** (`src/athena/apps/client.py`): Streamable HTTP to loopback addresses only (ported from Athena Portable; no proxy, no redirect, 1 MiB answers, 20 s per call, the token only in its header and redacted from every reason), and stdio children spawned from argv with no shell, their process tree ended when reaped. A tool's class comes from its annotations: read-only, or neither destructive nor open-world, runs on its own; anything else asks first.
- **Her tools** (`src/athena/apps/tools.py`): built from the last check's list; an input schema with a top-level `oneOf`/`anyOf`/`allOf` (Gravitone's are a `oneOf` per op) is flattened, because engines refuse one.
- **Across computers** (`src/athena/peer/apps.py`): the offering computer serves `/peer/apps` (label, kind, tools - never an address, command, key or folder), `/peer/apps/{id}/call` (its own class floor: a tool that asks first is refused without the approving card's id, which it records in its peer audit) and `/peer/apps/{id}/file` (only under the output folder, links resolved, 1 GiB at most, written in 1 MiB chunks). The asking computer lists offers at `GET /devices/{peer_id}/apps`.
- **Screens.** `apps/desktop/src/main/projects/apps/` (the section, the kind-first form, copies) and `main/settings/devices/OfferedApps.tsx`.

## Verified

- Tests: `tests/test_apps_store.py`, `test_apps_routes.py`, `test_apps_client.py` (both transports against stdlib fakes, reaping, a dead child restarted once, the token never echoed), `test_apps_tools.py`, `test_peer_apps.py` (two daemons over a real loopback socket: listing, grant, class floor, approval id, file escapes, end to end through her tools); desktop `main/projects/apps/apps.test.tsx` (each kind's body, the four kinds' words, copies, offered panel, banned words).
- **The seam on the real Gravitone** (`scripts/apps_seam.py`, 2026-11-04, 6/6): two daemons on this computer and Gravitone's agent door in local mode with an `act` token. A wires Gravitone (four tools: `gt_read`, `gt_spend` on their own; `gt_launch`, `gt_job` ask first); B offers it with an output folder; A attaches B's copy; a read runs on both copies; a `gt_job status` on B's copy is a card on A that, signed, runs once with the card's id in B's audit; a file comes home byte-identical. It found one defect no unit test had: Gravitone's top-level `oneOf`, now flattened.

## Open

- **The two-computer run, owner present.** The same walk on two real PCs over the private network (the seam admits loopback, as the peer tests do): pair them with the `apps` permission, run Gravitone on both, wire and offer it on the second, attach it, and have her split one job between them. Not yet run; Tailscale has never been exercised by any test.
- **Gravitone's music-video family** (business Phase 3.0, in gravitone-gcloud) is unbuilt, so a real render split waits on it; reads and job status work today.
- A key for a tool she starts is not passed to the child; a stdio app that needs one takes it from its own environment.
- Not yet seen in a running Tauri window.
