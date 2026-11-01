# 0017 - Devices pair over a private overlay, and Settings draws them

Status: accepted
Date: 2026-11-01

## Context

Athena runs on several of one person's computers and should be one Athena on all of them. Portable
has this (its ADR 0140, "One Athena pairs devices over a private overlay"): identity, a pairing
ceremony, an overlay-only peer listener, and a Devices page. This repo had none of it: no peer
code, no Devices item in Settings (ADR 0012).

The loopback daemon cannot be the thing other devices talk to. It binds `127.0.0.1` and its one
token is the window's; opening it to a network would put that token and every route in front of
every machine on the WiFi (ADR 0002). Portable's listener is built on the standard library's
`ThreadingHTTPServer`; this daemon is Starlette under uvicorn.

## Decision

1. **Ported: pairing and the Devices page.** `src/athena/peer/` carries portable's identity,
   registry, pairing book, audit trail, address classifier, outbound client with sealed keys,
   presence probe and link state, event bus, and the overlay probe, with the same laws:
   - transport is a Tailscale-class overlay (`100.64.0.0/10`, `fd7a:115c:a1e0::/48`); Athena adds
     no encryption of its own and says so;
   - a **second listener** on port 17491 (`--peer-port`; `--no-peer` turns the surface off) binds
     the overlay address only, and only while a live peer row exists, a pairing window or an
     unclaimed approval is open, or the beacon is on;
   - the address class is decided before anything is read (a fixed bodiless 403 for anything not
     overlay); then a per-peer bearer token, compared by fingerprint against every row; then the
     route's grant (`chat`, `approve`, `memory`);
   - a person's approval in this window is the only mint door; grants only narrow; the token is
     claimed once; a PC that is let in is asked to let the other PC in too (two human approvals);
     revoke is immediate;
   - `peers.json` holds fingerprints only; the token this device calls out with is sealed by the
     connector seal (DPAPI on Windows) beside a `reach.json`.
2. **Rewritten for this daemon.** The peer listener is a self-contained `ThreadingHTTPServer`
   (`peer/listener.py`) with its own route table; portable's `daemon.routes` and `DaemonServer`
   do not exist here. The loopback routes (`/devices*`) are Starlette routes (`peer/devices.py`)
   behind the daemon's bearer, and blocking calls run in worker threads. The events stream is
   `GET /devices/events?token=` (the app's existing `/events` is the settings/card bus). Refusals
   are `{ok: false, error, reason, detail}`: `error` is the word a program acts on, `reason` the
   sentence a person is shown.
3. **Files live in `<data>/peer/`**, not `$ATHENA_HOME`: this repo has one data folder (ADR 0012,
   "Where it lives"). Copying the whole folder to another computer therefore copies the identity;
   the Devices page tells the person to pair the new computer instead. Nothing is written until
   something pairs.
4. **Settings gains a fifth item, Devices.** The constellation, the pairing wizard and the
   approve card are portable's, drawn in this window's idiom (feature doc:
   `docs/features/devices.md`).

### Memory replication

Ported from portable's ADR 0140 WP2 (`src/athena/peer/replicate.py`), with its laws: only write-once
kinds travel (`episode`, `fact`), a copy can never be stale, same id and same sha256 is skipped,
same id with another sha keeps the local row and files the remote copy for a person, the cursor
is held back to the oldest unfinished item minus ten minutes of clock skew, a pass reads at most
40 pages of 500 with 5 s per call, passes never overlap, and a manifest 401 reads `removed_there`
(403 `not_shared`, silence `unreachable`). It differs where the stores do. Memory here is rows in
SQLite, not markdown files, so the manifest is `{id, kind, created, sha256}` over the text with no
`path`, and `GET /peer/brain/file?id=` answers JSON `{id, kind, created, text}`. **Only the core
space replicates**: a project's space id is minted per device, so the same id on two computers
names two projects; project rows are never listed and answer 404. A received row goes through
`Memory.receive`, which inserts under the sender's id and stamp (idempotent; refuses any other
kind, any id not shaped `mem_<12 hex>`, any stamp not in this daemon's UTC form) in the same table
the FTS triggers watch, so recall stays honest. There are no procedurals, no provenance to defer
on and no erase tombstones in this daemon, so `deferred` is always 0. Conflicts are kept at
`<data>/peer/conflicts/<id>.<peer_id>.json`, counted from the files, logged by id only; cursors
are `<data>/peer/cursors.json`. The puller starts and stops through `host.on_start` /
`host.on_close`; `peer/wiring.py` registers its routes. `GET /devices` shows
`peers[].memory = {last_pull_at, pulled, conflicts, deferred, state}` (`null` until the first
pull) and hands it to the link derivation, so a manifest 401 shows `removed_there`. The Devices
drawer and the screen-reader list say it in words.

### Vitals

Ported from portable's ADR 0143 (`src/athena/vitals/`): the stdlib probe per OS (ctypes on Windows,
`/proc` on Linux, `nvidia-smi` for an NVIDIA GPU, every failure `None`), the sampler thread, the gate
(RAM 92/85 %, CPU 90 % for three samples to 70 %, battery under 30 %, disk under 1 GB, hysteresis) and
the `VitalsView` wire shape, with the laws "unknown is `None`, never zero" and "a reading older than
90 s is unknown". It is trimmed to what this daemon has: no sleep cycle, no task runner and no ledger
runs summary, so `runs` and `sleep` are always `null` (the keys stay, so the shape is portable's), the
running term of the slot formula is 0 (`slots` is how many 600 MB tasks the RAM has room for, capped at
3) and the sleep-only hold rule and the task table's `task_room` are not ported. Disk is measured on
the data directory. `VitalsService` (`vitals/service.py`) is built by `peer/wiring.py` only in a daemon
with a data directory, sets `host.presence.own_vitals`, publishes `vitals.changed {room, held, slots}`
on the host bus only when one of the three moves, serves loopback `GET /vitals`, and starts and stops
the sampler through `host.on_start` / `host.on_close`, so a test or a second Athena never spawns
`nvidia-smi`. The authorized `GET /peer/hello` carries `vitals`; the presence probe keeps each peer's
last view (cleaned key by key, `vitals/wire.py`) with its arrival time, hides one older than
`VITALS_STALE_S`, fills `peers[].vitals` and `self.vitals` on `GET /devices`, and publishes
`peer.changed` only when a peer's room or held reason moves. The window draws the room word under each
computer ("Online - room ok"), the drawer's meters, GPU, power and disk, and the held sentence, and
reads the list again on `vitals.changed` and every 30 s while a computer's drawer is open. Not ported:
Athena being told the fleet in her turn frame.

### Remote composer and the phone page

A paired device granted `chat` sends `POST /peer/message {text}` (at most 8000 characters) and the
**daemon** runs it: `remote.py` builds the engine as `/run` does, takes the turn's slot at once (no
engine answers 503, a refusal a turn can make answers now), files the turn under a `job_` id and drains
`run_turn(daemon, engine, text, "")` on a worker thread into a buffer of at most 2000 events, closed with
`remote.closed {reason, showing, total, footer}` and forgotten after 10 minutes with nothing new. A peer
with four turns still running gets 429 `busy`. The sender reads `GET /peer/turns/<id>?from=n` as SSE with
an `id:` per event (only the sender, else 403 `not_sender`; a stream quiet for 15 s ends with `retry`).
Waiting cards are the gate's: `GET /peer/decisions` (grant `approve`) lists them and `POST
/peer/decisions/<id> {choice}` resolves one through `gate.resolve`, so an approved card's executor runs in
the daemon. The asking PC's loopback `POST /devices/<peer>/message` and `GET /devices/<peer>/turns/<id>`
forward with the sealed key and relay the stream as it arrives. The daemon's `type` events are re-shaped
into the `kind` vocabulary the phone page reads (`text.delta`, `tool.result`, `decision.requested`,
`turn.finished`, `turn.error`).

The phone page is portable's hand-written HTML, CSS and ES modules, unchanged but for its strings, served
by `phone.py` at `/m`, `/m/` and `/m/<file>` (seven named files, `nosniff`, `no-referrer`, a self-only CSP,
no-cache, open but behind the address gate). The peer listener gained prefix routes and a bytes reply for it.

How this differs from portable: there is no window to wake, so no `window_closed`, `remote.accept`,
`remote.end` or `remote.decided`, no `via` on `/run` and no `target_app`; a turn that files a card closes
with `waiting` and the card is answered on its own through `/peer/decisions` (nothing continues the turn).
Not ported: running the message on the other device's page (this app has no host calls) and serving the
phone page over HTTPS, so the service worker still never registers on the plain-HTTP overlay address.

### Setup conversation

Ported from portable's ADR 0140 WP4 (`src/athena/peer/setup.py`). From Settings > Devices, "Set up with
Athena" opens a conversation in her own window; she speaks first (`start: true` with no message makes
her read the overlay and say what she found), explains what Tailscale is before proposing to install
it, and walks the steps. Seven tools with fixed argv, never a model's string: `overlay_status`,
`list_overlay_peers`, `probe_peer` (the five states; `peer_ip` must be inside the overlay ranges and is
only dialled through `peer.client.call`) answer at once, and `install_overlay` (`winget`, started not
awaited), `overlay_login` (the sign-in URL opens only if https on tailscale.com), `firewall_allow`
(`netsh` show, an elevated add for the peer port from `100.64.0.0/10`, show again; Windows only,
elsewhere "not on this computer yet" and nothing runs) and `open_pairing` are cards. `open_pairing`
answers with the PC code and never the phone URL, which goes to the window as `pair.opened`.
`GET /peer/hello` carries `setup_phase` (null until the conversation opens, then installing,
signing_in, approving, waiting, pairing, paired, ready) and `PeerHost.wanted()` holds the listener up
for `SETUP_LISTEN_S` (30 min) after it opens (`listen_for_setup`).

How it differs: portable's gate files a tool call and the same call returns later; here a gated step is
one `setup_act` card (args `{tool, kind?}`), and the fixed command runs only in `turn.execute` when
the person signs it, so a failed step (winget did not start, Windows said no) returns the card to
waiting. The conversation is not a project turn: `peer.setup.run_setup_turn` reuses `turn._rounds` with
its own tool set and frame under the reserved space id `setup`, so project turns, the MCP server and
her browser never offer the seven names, and it carries no memory or page context (it writes no
episodes). It sees what came of the cards through a "Cards so far" list in its frame, and her window
sends `start: true` after a setup card is signed so she carries on. `ActionName` gains `setup_read`
(auto, for the three reads' lines) and `setup_act` (gated). The loopback routes are `POST
/devices/setup`, `POST /devices/setup/run` (NDJSON like `/run`) and `GET /devices/setup/conversation`;
her window shows the conversation on a Tauri event (`athena://setup`) from the main window.

## Not ported

Everything portable's ADR 0140 built is ported except: Athena being told the fleet in her turn frame
(there is no `frame.fleet` here), running a remote message on the other device's page (this app has no
host calls), memory outside the core space (project space ids are per device), and the phone page over
HTTPS (the service worker therefore never registers on the plain-HTTP overlay address).

## Consequences

- With no overlay installed, pairing cannot start: the listener stays down and `GET /devices` says
  `overlay.state: absent`. "Set up with Athena" walks the person through installing and signing in.
- Pairing state (open windows, unclaimed approvals) is in memory: a restart forgets them. Rows
  survive.
- Two daemons on one machine cannot both bind 17491; the second keeps its listener down and reports
  `listener.error`.
- When a PC revokes another and has no other peer, its listener closes, so the revoked PC reads it
  as asleep rather than `removed_there` until some other peer keeps the listener up. Portable has
  the same behaviour.
- Tests: `tests/test_peer.py` pairs two hosts over real loopback sockets (the test-only
  `admit_loopback` switch), including the two-way approval, presence, and revoke.
