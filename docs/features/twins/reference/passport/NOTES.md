# Passport

## Philosophy

The twin is a document being issued. Setting it up fills in its pages: identity (a monogram portrait in her seal's dome language, name, signature, purpose), visas for Gmail and Notion that stamp themselves when the sign-in or key succeeds, its voice (a specimen of your own mail and eight particulars), permits (ready-made chores), restrictions (never), clearance (Review / Assist / Auto per channel, with the bar), endorsements (memory you kept) and its first entry (the mission). Her proposals are pencilled in (dashed violet, an "Ink" button beside each); your own words are ink with a pink rule. Each section is a fixed place on the spread, so a new entry writes itself into its place and nothing already written moves. The question never lives on the document: it lives in Athena's bottom panel, and the section she is asking about is lit, with "Your answer lands here".

## Both pages

- **Overview (`#overview`)**: the stat strip (unmeasured shows "-"), then the wallet: each twin as a closed document with its portrait, state, visa marks, clearance and readiness. Beside it, "Waiting for you" lists the drafts and hand-backs across twins, plus the paused twin's one-press sign-in. Underneath is the ledger (rows, status badges, totals line). Opening a twin, from its document, its ledger row or a waiting item, opens it as a spread in place: missions on the left page, drafts waiting for your signature on the right. A held draft shows its risk list and how sure it was against the bar, with sign, edit and decline.
- **Setup (`#setup`)**: the open spread (left: identity, visas, voice; right: reads from, permits, restrictions, clearance, endorsements, first entry). Beside it is one working slip for the frame's panel: sign in, samples, particulars, Notion key, pages, permits, clearance, endorsements, or her pencil to ink. Athena's bottom panel holds her line, the one question, three suggestions (keys 1-3), your own words, "Ink all her pencil", what she still needs and, from frame 9, "That's enough, rehearse it". The past lives in "Her window".
- **Rehearsal**: the spread folds to its trip page (clearance, restrictions, entries) beside the Notion practice page. Every twin turn gets a stamp: waits for your signature, held (77 of 80, one risk, with the restriction it touches lit on the document), you edited (with what it learned), sent on its own. The resolved row shows as filed to Notion. "Try it another way" plays the hand-back.

## The wow moment

Go live presses the issue seal onto the document: a ring reading "ISSUED · 29 OCT 2026 · LOW TIDE VISUALS" around the twin's portrait lands in the corner of the right page, every pencil mark is now ink, and the status turns "Issued". Back on the overview, the Partnerships document carries a fresh "Issued today" stamp, the Live tile says "was 1", and its ledger row glows once.

## How it holds (scale, 1024x700)

- Sections that are not being asked about read at a glance: optional details (page kinds, chore descriptions, mission kind, evidence counts) show only in the lit section, and on hover elsewhere. The specimen clamps to one line. The particulars are a two-column grid that names only values not learned from your mail ("you", "preset").
- At 1024 wide, "reads from" and "permits" pair up side by side, the slip narrows to 286 px, and the section subtitles show only on the lit section. At 700 tall, paddings and the header tighten and the practice page, the opened document and the queue scroll inside themselves, never the page.
- An empty document still shows its printed form (blank portrait, dotted fields, empty visas, unset particulars) rather than a void.
- Dark is the default. Light works through the toggle (top right), using the same tokens.

## Known limits

- One staged path. Any suggestion, typed words or panel choice plays the example's next frame; a quiet note says so when your choice differs. "Show me where to find it" (Notion) is the one suggestion that stays put and opens the steps.
- Timed states play faster than real (about 4x) and show real seconds. States picked from the menu tick at real speed. Slow and failed are reached from the menu, or from Stop and Try again while she thinks.
- The seal covers the ends of a few lines on the right page at go-live, as ink would.
- Panel choices (marks, dials, clearance) change the slip and the particulars but not the staged pieces that arrive next.
- Standing rules (how much it may ever give) are one line, as asked.

## Variant data

`js/variant-data.js` is invented copy consistent with the shared data: the passport names for each place, the describe step's line and three suggestions, the dial values for the three style presets, the specimen line, the bottom panel's line and question for each rehearsal step (frame 11 has no question of its own), the issue date and name on the seal, and the staged-path notes.

Files: [index.html](index.html), `css/` (shell, overview, document, work), `js/` (util, document, slip, rehearsal, athena, shell, overview, app). The shared material is in [../shared/SCHEMA.md](../shared/SCHEMA.md).
