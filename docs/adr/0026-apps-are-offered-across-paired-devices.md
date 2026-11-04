# 0026 - A device offers its apps to paired devices, and one Athena splits work across them

Status: accepted
Date: 2026-11-04

## Context

Devices pair over a private overlay (ADR 0017). A paired device may send a message into core and
answer approvals; nothing lets her use an app that runs on the other computer, and projects are not
replicated there. The owner's case is the same app on two computers (Gravitone on two PCs) with one
job split between them and the outputs gathered in one project.

## Decision

1. **The offering device wires its own apps.** On PC B the owner wires an app at device level (outside
   every project, in Settings) and marks it offered, naming the one output folder files may be pulled
   from. B never runs configuration another device sent it.
2. **A new grant, `apps`.** Appended to `chat`, `approve`, `memory`; given at pairing; a phone never
   asks for it. B's listener serves `GET /peer/apps` (what it offers: label, kind, tools, never an
   address, argv or token), `POST /peer/apps/{app_id}/call`, and `GET /peer/apps/{app_id}/file?path=`.
3. **One app, instances per device.** In A's project an app can attach B's offered match as a
   remote instance (`app_remotes`). Her tools for it are offered as `<slug>_on_<device>__<tool>`, so she
   decides the split in the turn; a long job detaches and is read on a later call.
4. **A gates; B holds a floor.** A's gate and ledger own every call: a gated tool files the card on A.
   B re-derives each tool's class from its own listing and refuses a gated tool that arrives without
   the approving card's id, which it records in its audit (it cannot verify it).
5. **The output comes home.** `app_fetch` on a remote instance streams a file from B's offered output
   folder (path checked on B, `APP_FILE_MAX_BYTES` cap) into A's project files, with the device as its
   origin.

## Consequences

- A device's offered apps are reachable only by peers holding `apps`; revoking the peer ends it.
- Proven first with two daemons on one computer (loopback admission, as the peer tests do); the real
  two-computer run over Tailscale is owner-present and recorded in `docs/features/apps.md`.
- Splitting by a routine (a queue fanned out across instances) is not built; she splits in the turn.
