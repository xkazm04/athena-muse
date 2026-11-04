# Devices - pair a phone or another computer with this one

Built 2026-11-01. Decision: [ADR 0017](../adr/0017-devices-pair-over-a-private-overlay.md). The daemon side (identity, pairing, grants, presence, the event stream) lives in `src/athena/peer/`; ported from Athena Portable's Devices level.

## What it does

`#settings/devices` is the fifth Settings level. The overview tile words itself from one read of `GET /devices`: *No other device paired*, *N paired*, *N waiting for you*, or *checking* when the daemon did not answer (never "nothing paired" for a failed read).

The level is a constellation on one stage:

- **This computer** is the centre. Its details (the drawer) hold the private network's state, where it listens, its name to rename, and the switch that lets a paired phone reach Athena here.
- **Paired devices** sit on an orbit, oldest first. The line from the centre says how each stands now: lit with a slow breath (online), dim (asleep: the network sees it, Athena there does not answer), broken (out of reach), dotted for a link the other side removed or still waiting for its key, and a plain hairline for a phone, which is never probed. A device's drawer shows its kind, standing, last seen, what it may do, and **Revoke** (at once; pair it again to undo).
- **Requests waiting on you** are pulsing nodes. **Approve** is armed 1.5 s after the card is first shown, so a click already on its way cannot approve it; the store enforces the delay as well as the button. The grants can only be unticked, never added to; approving with none ticked is refused; **Decline** acts at once. A request that would replace a paired device says so.
- **Two '+' nodes**, phone and computer. The pairing wizard grows out of the one pressed (Escape or Back folds it back, the focus returns to the node):
  - *Phone*: a QR of the pairing address with the code beside it and a ring that runs down the five-minute window, then Approve, then Done. The address is a claim credential: drawn in the QR and printed once with a Copy button, never in a title or an accessible name. Where the encoder cannot hold it the code alone is shown.
  - *Computer*: either show a code for the other PC to type, or type the other PC's address (picked from the private network's online computers, or typed) and its code to join; the computer joined asks back, and that too is approved here.

A refused act is shown under the control that made it, in the daemon's words.

## How it works

- **Store.** `apps/desktop/src/main/settings/devices/store.ts` mirrors `GET /devices` and nothing more; every act (rename, beacon, pairing window, join, answer, revoke) is a request after which the list is read again, through the shared read discipline in `lib/mirror.ts` (one read at a time, an act's read supersedes the one out, an answer older than a newer read is dropped). It keeps when each request was first shown (`seenAt`) and which grants were unticked.
- **Wire.** `lib/fleet.ts` has the shapes and the event follower; `lib/api.ts` the routes. The follower is an `EventSource` on `/devices/events` (not `/events`), shared by every holder; `pair.requested`, `peer.changed` and `pair.opened` nudge a read, and `pair.opened` also hands over the code and the phone's address, which the list never carries. The daemon ends a quiet stream every 15 s and the browser reconnects.
- **Components.** `Constellation.tsx` (sky, drawer), `Wizard.tsx` (the step is read from the mirror every render, so a pending request for the wizard's own window *is* the Approve step and its leaving the list *is* Done), `QrSvg.tsx` with the in-tree encoder `qr.ts`, `Devices.tsx` (the level and the panel that wires the store), `devices.css` (tokens only).

## Verified

- `devices/store.test.ts`: the arm delay, grants narrowing, nothing-ticked refused, `stampSeen`, `sentenceOf`, request ordering (revoke then read; a stale read dropped), `pair.opened`.
- `devices/devices.test.tsx`: every state of the sky, drawer and both wizards from fixtures, the driven flows (open and fold with focus, Tab kept inside, approve to Done, a refused rename or join keeping what was typed), and that the dropped parts are absent. `devices/qr.test.ts`: the encoder against matrices pinned from two independent encoders.
- `model.test.ts`, `settings.test.tsx` (the tile, the level, the failed read), `settings.css.test.ts`.
- Not yet seen against a live daemon in a running Tauri window.


## Memory

A computer you share `memory` with is pulled every minute and whenever a device changes: its core episodes and facts (never a project's) arrive under their own ids, once. The drawer's "Memory" line and the screen-reader list say how many came across, when, and any conflicts kept aside (same id, different words: yours stays, theirs is saved under `<data>/peer/conflicts/`). `not shared`, `removed there` and `could not reach it` are plain words. Nothing shows before the first pull. Tests: `tests/test_peer_replicate.py`, `devices.test.tsx` (memory lines). See ADR 0017 "Memory replication".

## Vitals

Each computer shows how much room it has: the gate's word under its name in the constellation ("Online - room ok", "tight", "full") and, in its drawer, the room with its task slots, CPU and RAM meters, GPU, power and disk. When work has to wait the drawer says why in the gate's own sentence (RAM at 92 %, CPU high three readings running, battery under 30 %, less than 1 GB free on the data folder). Unknown is never zero: a figure that could not be measured reads "unknown" with no bar, and a computer not heard from in 90 s says "Not heard lately". A phone is not measured. Tests: `tests/test_vitals_probe.py`, `tests/test_vitals_gate.py`, `tests/test_vitals_service.py` (hello, presence, `GET /devices`), `devices/vitals.test.tsx`. See ADR 0017 "Vitals".

## Messages and the phone page

A paired computer's drawer has a box: type a message and that computer's Athena runs it as a turn in her own core conversation, with her own approvals there; her words, the tools she used and a card waiting for approval come back under the box. A computer that did not answer is named plainly; one that is busy says so. A phone paired with `chat` gets the page at `http://<overlay-address>:<peer-port>/m/` (the beacon switch): it chats the same way and, with `approve`, signs the gate's waiting cards from the phone. The page is hand-written HTML, CSS and ES modules in `src/athena/peer/mobile/`; it needs the Tailscale app on the phone, and Athena running on the computer. The page wears the same Loop Tide look as her window (cobalt glass with the loop's arc, the book's cards, the person's pink on Sign only; its tokens are copied from `theme/tokens.css` and a test holds them equal) and follows the computer's Settings look (theme, text size, calm motion), which `GET /peer/hello` carries as `look`; with the theme on auto it follows the phone's own light or dark. Tests: `tests/test_peer_remote.py`, `tests/test_peer_phone.py` (which also runs `tests/peer_phone/*.test.mjs` under node; by hand `node --test tests/peer_phone/*.test.mjs`), `devices/conversation.test.ts`, `devices/messagebox.test.tsx`. See ADR 0017 "Remote composer and the phone page".

## Set up with Athena

The bottom of the Devices level has one button. It opens a conversation in her window that speaks first, says what it found (is Tailscale installed and signed in, this computer's address, the other devices), explains what Tailscale is before it proposes installing it, and walks the steps. Every step that changes this computer (install Tailscale, sign in to it, the firewall rule for the peer port, opening a pairing window) is a card you sign; nothing runs before. While the conversation is open the peer listener stays up for 30 minutes so the other computer finds Athena, and `GET /peer/hello` reports `setup_phase`. The conversation has its own history under the space id `setup` and no project, memory or page context. Tests: `tests/test_peer_setup.py`, `lib/setup.test.ts`, `athena/setup.test.tsx`, `devices/setup.test.tsx`. See ADR 0017 "Setup conversation".

## Apps

A fourth permission, **use the apps this computer offers** (`apps`), lets a paired computer use the programs this one offers in Settings > Devices > Apps this computer offers; a phone never asks for it. A computer paired before it existed is paired again to give it. See [Apps](apps.md) and ADR 0026.
