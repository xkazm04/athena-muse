# Twins - a clone that speaks for you, set up with Athena

Built 2026-10-30 (Passport). Decisions: [ADR 0008](../../adr/0008-twins-speak-through-connected-accounts.md) (connected accounts), [ADR 0009](../../adr/0009-one-send-rule-for-every-twin-draft.md) (the send rule), [ADR 0010](../../adr/0010-one-shaping-conversation-two-rubrics.md) (one shaping conversation, two rubrics). Design history, including the Mirror and Rehearsal prototypes that were not picked: `docs/concepts/twin-module/` in git history before the commit that added this page.

**Open:** the run on the owner's real Google and Notion accounts ([below](#open-the-real-account-run-owner-present)).

## What it does

A twin drafts the next message in a conversation in the person's voice and, when its channel allows,
sends it. It is set up in conversation with Athena on one page, a passport being issued:

1. Who it speaks as. 2. Gmail sign-in. 3. Voice from your sent mail. 4. Style dials. 5. Notion key and
the pages it may know. 6. Chore presets (permits). 7. What it must never do. 8. Autonomy per channel.
9. Memory. 10. The first mission, a dress rehearsal on a Notion practice page (Athena plays the other
side; each draft marked "that's me" / "not me", edits teach the voice), then go live.

Her proposals are pencil, the person's words ink, nothing already placed moves, no page scroll at
1280x800 and the layout holds at 1024x700. Plain words only: never "token", "connector", "OAuth",
"API", "prompt" or "node".

Once live, a twin takes **missions**: a goal on one Gmail conversation (or a new one, given an
address), from its document ("Give it a mission") or from a Notion **task inbox** page (one
`<who or thread>: <goal>` line each). It drafts each turn toward the goal, hands the conversation back
when unsure, and files the outcome to Notion when resolved.

## How it works

**The send rule (ADR 0009).** `decide(channel, draft)` is one pure function used by the interactive
path, the poller and the rehearsal. A draft sends alone only when the channel is connected and the
twin live, the level is `auto` (or the `split` level for that kind of message is), `confidence >= bar`,
and `risks` is empty. Everything else waits as a `twin_send` signature card with a reason; the person
may edit its text, and a sent edit becomes a voice example. A paused twin or channel never sends.
Autonomy levels: `review`, `assist` (default), `auto`. Answering a thread the other side started is a
reply, so the first-message split applies only to cold outreach.

**Connectors (ADR 0008).** athena-portable's vault, seal, Google sign-in (the person's own Google
client, loopback with PKCE), Gmail and Notion are ported under `src/athena/connectors/`. Credentials
live under the daemon's data dir, sealed by DPAPI or the keyring, probed before they are kept. Twin
sends may go to any recipient (`send_for_twin`); every other write keeps the writes switch and the
allow-list.

**The poller.** Started by the app's lifespan; it polls Gmail threads with an open mission and the
task inbox every 5 minutes while the daemon runs. Off with `ATHENA_TWIN_POLL=0` and in tests.

**Setup** runs on the drafts machinery with `TWIN_RUBRIC` (ADR 0010); readiness is derived from data.
Played as staged on the scripted engine, readiness runs 14 -> 100 and is ready at frame 9.

**Code.** Daemon: `src/athena/twins/` (store, rubric, setup, voice compiler, `decide`, rehearsal,
missions, poller), `src/athena/connectors/`. Page: `apps/desktop/src/main/twins/` at `#twins`,
`#twin/<id>`, `#twin/<id>/voice`, `#twin/<id>/entry`, `#twin/<id>/mission/<mid>`,
`#twin/<id>/draft/<did>`. `StatStrip` and `Ledger` live in `src/ui/`. One twin per Project; its tables
are erased with the Project.

**Wire.** Enums `Place`, `ChannelKind`, `Autonomy`, `TwinState`, `ChannelStatus`, `ChannelHealth`,
`MissionState`, `SendDecision`, `WaitReason`, `TwinMark`, `MissionSource`; `Surface` gains `twin`;
`ActionName` gains `twin_send` and `twin_note` (gated). Field names follow
[`reference/shared/SCHEMA.md`](reference/shared/SCHEMA.md); the daemon owns every derived number.

| purpose | routes |
|---|---|
| Overview | `GET /twins` -> `TwinPage` |
| Create / one twin | `POST /twins {space_id}` (`""` makes its own Project); `GET /twins/{id}`; `GET /twins/{id}/preview` |
| Setup | `POST /twins/{id}/say` (NDJSON), `/confirm`, `/drop`, `/samples`, `/dials`, `/pages`, `/chores`, `/autonomy`, `/memory` |
| Rehearsal | `POST /twins/{id}/rehearse {goal}` (one stream for the whole conversation), `/rehearse/mark` |
| Live | `POST /twins/{id}/golive`, `/pause` |
| Missions | `POST /twins/{id}/missions`, `GET /twins/{id}/missions/{mid}`, `GET /twins/{id}/threads`, `POST /twins/{id}/goals` |
| Connectors | `GET /connectors`; `POST /connectors/{kind}/connect`, `/disconnect`, `/probe`; `GET /connectors/{kind}/flow` |
| Decisions | `POST /decisions/{id} {verdict, edited?}`; the executor runs off the event loop, a failure returns the card to waiting |

## Verified

- `scripts/twin_seam.py` drives the built page end to end against a throwaway daemon on the scripted
  engine, with Gmail and Notion faked in the daemon's own process (simulated, labelled): setup,
  rehearsal, go live, a mission from the page and one from the task inbox. Screenshots: [`shots/`](shots/).
- `scripts/twin_fixture.py` generates the invented example through the daemon's own rules
  (byte-identical); `tests/test_twin_fixture.py` fails when it is stale.
- Fidelity against the Passport prototype: 0 deviations on 15 roles in four states ([`fidelity/`](fidelity/)).
- In the rehearsal, t3 is held (77 against a bar of 80, plus one risk) and t5 is sent alone (91).

Reference: the picked prototype [`reference/passport/`](reference/passport/index.html) (opens from
disk) and its shared data, schema and states in [`reference/shared/`](reference/shared/). The tests read
`reference/shared/twin-data.json`; do not move it without updating `tests/twins_kit.py`.

## Known limits (v1)

- One account per service per daemon: connector routes are keyed by kind, so twins share one Gmail and one Notion account.
- The voice preview is kept in `twin_previews` and rewritten only when the compiled voice changes.

## Open: the real-account run (owner present)

Not run yet: it needs the owner's own Google client and Notion key, and it sends one real email.

1. Start the app on Claude Code (`ATHENA_ENGINE=claude_code`) with a fresh `--data` dir.
2. Twins -> New twin -> say what it is for.
   - Gmail: make your own Google client (the guide on screen walks through it) and sign in.
   - Notion: paste a key from an integration that can read one test page and a "Twin inbox" page.
3. Finish the setup and rehearse on the Notion practice page. Mark one draft "not me" and edit it.
4. Go live with Gmail first messages on Assist.
5. Give it a mission to **your own second address**, sign the first message, reply from that
   address, and watch the poller's next round (5 min) answer under the send rule.
6. Record here what was sent, what waited and why, the est. cost from the ledger, and anything that broke.
