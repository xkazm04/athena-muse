# Twin module - a clone that speaks for you, set up with Athena

Status: **designed; Passport picked** (2026-10-29). Nothing in the app is built yet. Of the three
prototypes (Mirror, Passport, Rehearsal) the owner picked [Passport](#passport---open--notes); the
other two stay as reference. The build plan is at the end.

## Spark

Owner, 2026-10-29:

> start project of creating Twin module, inspired by our implementation [personas], we will need to design ultimate experience to onboard a twin - digital clone serving for communication, setup channels via app's connectors (currently google,notion only) with goal Athena can help onboard the twin, and use twin to handle custom tasks by user to resolve conversation. UI will need one-page experience: 1. Overview page with list of twins via Ledger and stats components 2. Onboarding experience with dynamic UI and bottom chat panel to communicate with athena during the setup. ... Design and prototype three variants covering both pages, look into historical prototypes for onboarding v2, where all variants achieved high quality of designs and creative solution which we will need to get inspired from. Personas on the other hand will have package of features we can pick from to create optimal experience

## What it builds on (scouted 2026-10-29)

**This repository.**
- Routes are a union in `apps/desktop/src/main/route.ts`; a Twins page is two members, a nav link and one content line. The stage shows how a page takes the whole window (`App.tsx` early return).
- The ledger is `LedgerRow` (`contracts.py` / `contract.ts`, parity-tested), served at `GET /ledger` and drawn as the Costs table on the Athena page (`m-totals` line, `m-table`, badge tones). It has no space filter. There is **no stat component** anywhere in the desktop.
- A bottom chat panel already exists: the Drawing view's `Note` pins her line, the question, suggestions, the composer, thinking/slow/failed and the "enough" exit across the bottom, all from store-free `stage/parts`. `StillNeeds` and `EnoughButton` are typed to the chore's coverage and would need a generic coverage.
- There are **no connectors, no twin and no delegated mail**. The gate files a card and resolves it exactly once; `CardView` has no editable text.
- [Business channel](../business-channel/README.md) planned Twins as a tone profile per channel plus your edits as examples, every send a card, and reaching the mailbox through her browser rather than a connector.

**athena-portable** (the earlier sibling):
- Connectors are data: `gmail.json` (sign in with Google through a loopback flow with PKCE, the person's own Google client; read and send) and `notion.json` (a pasted integration key; search, read, append, create). "Google" is Gmail only.
- One vault seals every credential (DPAPI or the keyring), probes it before keeping it, keeps writes off by default and refuses any write outside an allow-list.
- The Connect screen shows idle, waiting for the browser, failed, needs sign-in again and connected states.

**personas** (the feature menu). Built and mounted there:
- create a twin;
- a planned interview whose proposals the person accepts, edits or dismisses;
- tone per channel, learned only from the person's own samples;
- eight style dials with presets and where each value came from;
- readiness derived from data (identity, tone, brain, channels, memories);
- a memory review queue with reasons;
- a reply outbox with steer chips, where approving only logs;
- roster cards and channel health (quiet, stale, never).

**Absent in personas**, which is exactly what this module adds:
- a working channel connect;
- reading incoming messages;
- real sending;
- autonomy levels;
- goal-directed conversations;
- learning from the person's edits.

**The bar.** The [onboarding v2](../chore-onboarding-v2/README.md) contest winners, Pencil & Ink and Orbit, set it, along with the other four entries:
- the one thing the person must do now dominates the screen;
- her guesses are drawn in pencil and the person's words in ink;
- nothing already placed moves;
- no page scroll at 1280x800, and the layout holds at 1024x700.

**Standard read** (registry `speed-to-lead-and-assisted-reply` / `risks-gate-not-confidence`):
- Each channel has three autonomy levels, with Assist as the default.
- A draft sends alone only when all four hold: the channel is enabled, the channel is on Auto, the draft is at least as sure as the channel's bar, and its risk list is empty.
- One gate function decides this, and a disabled channel never sends.

## Design decisions

Wave 1:
- **Channels: port athena-portable's Gmail and Notion connectors and vault into athena-muse.** Twin channels are connected accounts. This changes the business-channel rule "no per-service connectors" for Twins, and needs its own ADR at build time. Rejected: reaching mail through her browser; a connector now with the browser later; building the Twin in athena-portable.
- **Notion: knowledge, outcomes, a channel and a task inbox, all as preset chores.** The owner's words: "Notion tasks should be custom chore - Outcome, Channel for testing, Inbox all possible. But not as hardcoded Athena feature, rather preset chore. User can select in the future more tools to integrate as we will add." A twin's tool uses are chores ([ADR 0005](../../adr/0005-chores-are-data-rehearsed-on-a-bench.md)) picked from a catalogue that grows.
- **Tasks: mission first, standing rules next.**
  - A mission is a goal on one conversation. The twin drafts each turn toward it and reports when the mission is resolved.
  - When it is unsure, it hands the conversation back to the person.
  - Rejected: one-off draft requests only.
- **From personas, all four:**
  - voice only from the person's own samples;
  - an interview with her proposals in pencil;
  - style dials with presets;
  - memory review.

Wave 2:
- **Autonomy: Review, Assist and Auto all live in v1.** The owner chose this over keeping Auto locked. Held drafts show their risk list and how sure the twin was against the bar.
- **Setup ends in a dress rehearsal** on a Notion practice page, with Athena playing the other side. The person marks each draft "that's me" or "not me", and their edits teach the twin; then it goes live. Rejected: going live on a real thread first; treating readiness at 100% as the finish.
- **Three concepts:** Mirror, Passport and Rehearsal. Rejected: Constellation (Orbit lineage).
- **Example:** three twins on the overview (Client desk live, Family admin paused, Partnerships being set up); setup plays Partnerships, the creator outreach from the business channel.

Decided as convention:
- **Ledger and stats.** "Ledger" is the app's row table: rows, badges and a totals line. "Stats" is a stat strip in which an unmeasured value shows "-", never 0. Each row is a twin.
- **One page.** Each prototype's `index.html` holds both pages at `#overview` and `#setup`.
- **Setup order:**
  1. Who it speaks as.
  2. Gmail sign-in.
  3. Voice from your sent mail.
  4. Style dials.
  5. Notion key and the pages it may know.
  6. Chore presets.
  7. What it must never do.
  8. Autonomy per channel.
  9. Memory.
  10. The first mission, then the dress rehearsal, then go live.
- **Words.** Plain words only. Never "token", "connector", "OAuth", "API", "prompt" or "node".

## The prototypes

Open each `index.html` from disk. All three play one invented example, generated from
[`prototypes/shared/src/twin.src.mjs`](prototypes/shared/src/twin.src.mjs) by `node src/build.mjs`.
Its schema is [`prototypes/shared/SCHEMA.md`](prototypes/shared/SCHEMA.md) and the states every
variant shows are in [`prototypes/shared/states.md`](prototypes/shared/states.md).

All three play the same invented example:
- overview stats: 1 live twin, 3 waiting for you, 2 missions open, 23 sent this week (14 on its own), 3 held by the risk list, est. $1.90;
- 12 setup frames, ready to rehearse from frame 9;
- the Lumen Vale rehearsal with a held reply (77 against a bar of 80, one risk) and a reply sent on its own (91, no risks).

Every variant exposes `window.TwinProto` (`states`, `go(id)`) and a States menu. A Playwright pass drove every state at 1280x800 and 1024x700 (2026-10-29, run by the Director). It found no page scroll, no text under 12 px, no banned word and no console error: Mirror 92 checks, Passport 88, Rehearsal 86. Each variant also played its whole staged path by clicks and keys with no errors. `shots/` keeps four screenshots at 1280x800 and `report.json`.

### Mirror - [open](prototypes/mirror/index.html) · [notes](prototypes/mirror/NOTES.md)

![Mirror, setup at frame 3](prototypes/mirror/shots/1280x800-setup-f3.png)

**Idea.** The twin's draft reply to a real-looking creator message (Wren Atlas, variant data) sits in a mirror beside your own sent mail.

**How it reads.** Each answer rewrites the draft:
- stock phrasing is grey;
- her proposals are dashed violet pencil, with the words your last answer changed listed under the draft;
- settled words are ink.

A likeness bar climbs from 14% to 100%. The twin's parts hang as marginalia, with leaders drawn to the words they shape.

**Overview.** The waiting drafts and the hand-back sit as small mirrors, their message beside its draft.

**Strongest at** making "it sounds like you" visible.

**Weakest at** the rehearsal screen, which leaves empty columns.

### Passport - [open](prototypes/passport/index.html) · [notes](prototypes/passport/NOTES.md)

![Passport, setup at frame 3](prototypes/passport/shots/1280x800-setup-f3.png)

**Idea.** The twin is a document being issued, with these sections:
- identity, with a monogram in her seal's language;
- visas that stamp themselves on sign-in;
- voice: a specimen of your mail plus eight particulars;
- permits (preset chores, with "coming" tools as blanks);
- restrictions;
- clearance per channel;
- endorsements (memory);
- the first entry (the mission).

**How it reads.** The section she is asking about is lit with "Your answer lands here", and a working slip beside the spread holds the panel. Go live presses a seal into it.

**Overview.** A wallet of closed documents over the ledger.

**Strongest at** a twin you can read at a glance, and the most distinctive overview.

**Weakest at** density: at 1024x700 a few long items wrap or truncate.

### Rehearsal - [open](prototypes/rehearsal/index.html) · [notes](prototypes/rehearsal/NOTES.md)

![Rehearsal, setup at frame 3](prototypes/rehearsal/shots/1280x800-setup-f3.png)

**Idea.** Mission first. From frame 0 the Lumen Vale conversation shows as six unwritten beats, each naming what it needs ("needs your voice", "must not agree to exclusivity", "may it send this alone?").

**How it reads.** Answers light the beats that depend on them, and one answer about voice writes three of the twin's lines in pencil. The twin's parts gather in the wings with a readiness meter. The dress rehearsal plays the same script for real.

**Overview.** Open missions show as scripts in progress (beat 4 of 5, handed back).

**Strongest at** tying setup to the job the twin will actually do.

**Weakest at** fit: at 1024x700 the last beat sits under a fade on two frames, inside a column that scrolls on its own.

### What carries over whichever is picked

- Athena's bottom panel is the same in all three, and maps onto `stage/parts`. It holds:
  - her line;
  - one question with a chip naming its place;
  - three suggestions on keys 1-3;
  - your own words;
  - "Ink all her pencil";
  - what she still needs;
  - "That's enough, rehearse it".
- A held draft always shows how sure it was against the bar, plus its risk list, with sign, edit and decline.
- The overview is a stat strip, then the ledger, with a "Waiting for you" band (all three builders found that the space under the ledger wanted it).

## Build plan (after a variant is picked)

Contracts first, one commit per feature, ADRs in the same commit.
- **ADR 0008, Twins speak through connected accounts.** The connectors and vault are ported from athena-portable (Gmail and Notion); this amends the business-channel rule for Twins.
- **ADR 0009, the send gate.** It covers the three autonomy levels per channel, the bar and the risk list; one pure function serves both the interactive and the unattended paths, and a paused channel never sends.
- **WP0, the wire contract.**
  - New types in `contracts.py` and `contract.ts`, with a parity test: `Twin`, `TwinChannel`, `Piece`, `StyleDial`, `Sample`, `MemoryFact`, `Mission`, `TwinDraft` (`confidence`, `risks`, `decision`), `TwinStats` and `TwinSetupFrame`.
  - `Surface` gains `twin`, and the ledger gains a space filter (business-channel G23).
- **WP1, the connectors port.** `src/athena/connectors/`: specs, vault, seal, loopback sign-in, probe and the routes.
- **WP2, the twin store and setup turn.**
  - The setup conversation reuses the draft/stage mechanics: one question, suggestions, pieces with `origin` and coverage.
  - Voice comes only from samples, and memory is proposed, then kept or dropped.
- **WP3, missions and the gate.**
  - The mission runner drafts toward the goal.
  - Every decision goes through the one gate function.
  - Every send is a card or an "alone" ledger row.
  - A preset chore files the outcome.
  - The rehearsal runs on a Notion practice page.
- **WP4, the Twins page.**
  - The `twins` and `twin/<id>` routes.
  - A `StatStrip` and a `Ledger` table extracted into `src/ui/` (the Costs table becomes its second caller).
  - The chosen variant's setup page, with Athena's bottom panel built from `stage/parts` on a generic coverage.

## Open (owner)

- Picked 2026-10-29: **Passport** ("Passport is the winner").
- Wave 3, after the pick:
  - The working slip stays beside the spread.
  - The rehearsal keeps its trip page.
  - Three ideas are borrowed from the other prototypes: Mirror's live draft preview, Rehearsal's mission beats and Mirror's waiting cards. The owner's rule for them: "as nested content, in main content represented by stat or smaller component to fit, on click to have standalone page design".
  - Build order: the contract and stubs come first, then the Passport page on a generated fixture is built in parallel with the backend.
