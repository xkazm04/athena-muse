# The Spread - the conversation as a book

Built 2026-11-03. Decision: [ADR 0024](../adr/0024-the-conversation-is-a-book-of-spreads.md). Plan, element map and
what was not ported: [the migration plan](../concepts/the-spread/MIGRATION.md). The owner chose it in the blind
contest on how Athena looks when she takes the screen ([brief](../concepts/ai-ux-contest/BRIEF.md)).

## What it does

- **Every exchange is a two-page spread.** The left page says what you asked and the date, then "What she
  did": one receipt per step in plain words ("Looked through the songs", "Filed a card for your
  signature", "Showed parts of the report"), each with its moment ("after 26 s"), then "Took 1 min 52 s"
  and the est. cost. The right page is her answer at a reading measure, a short one set large, with her
  cards and report parts in place, drawn by the app's own `Prose`, `CardView` and report blocks.
- **Pages turn one at a time.** The arrows and Page Up/Down turn a page, Home opens the first and End the
  page being written (`spread/keymap.ts`, the book's one keymap); a key typed into a field is the field's.
  A leaf sweeps across as the page turns; under calm motion or reduced motion the page is simply there.
- **The ribbon is the history.** A tab per page with her question and its cost, "stopped" in red on a try
  that stopped, a pink dot where a card waits, a pulsing dot on the page she is writing; after a rule, the
  back pages. Folded, a compact bar (previous, a page list, next) does the same.
- **A page writes itself.** "Write a new page" holds the composer. Once sent, receipts land on the left
  with this window's own count, a still-working clock says how long in words, her words fade in on the
  right, and Stop ends it. When she is done the conversation reloads and the window turns to the page it
  became, drawn from the stored parts exactly as it was written.
- **A stopped try is a page.** The daemon keeps it with what streamed and why it stopped; the page says
  so and offers Try again, and the same words asked next are marked as her second try, each page linking
  the other. A question with no answer kept says so; one the person stopped says that they did.
- **The bookmark.** While a card waits for a signature anywhere, a pink ribbon hangs from the gutter ("1
  waits for your signature - Open its page"); it opens the page holding the card and puts the focus on
  Sign. A card on no page of this book (another project's, a routine's) has a page of its own.
- **Two windows, one book.** Her window (400 x 620) shows it folded: one page at a time, the left above
  the right, the head carrying her seal, the project pill and Hide. The main window's Athena place
  (`#athena`, `#athena/<page>`) shows it open under the shell's bar with no dock, with back pages: the
  project's report (her title, when she arranged it, her one sentence, each pin as a standing rule the
  person can remove, what could not be shown and why, Arrange again, and the report's grid), a chore
  being drawn (the need, what she still needs, the sketch place by place in ink and pencil with Ink it
  and Not this, the open question), the report as another assistant sees it (stylised; the view and its
  text fallback from GET `/spaces/{id}/report/elsewhere`), and what it cost (the ledger).
- **The look's two switches** in the head ("Calm motion", "Dark") write Settings' look, so both windows
  follow.

## Verified

`spread/model.test.ts` (exchanges, stopped and second tries, legacy turns, receipts with and without
moments, formats, the bookmark's target, the keymap, the page-being-written table), `spread/spread.css.test.ts`
(tokens only, 12 px floor, no colour of its own, a reduced-motion block, every rule under `[data-spread]`),
`athena/App.test.tsx` (her window: a page written live then settled, cards and the bookmark, a card waiting
elsewhere, project switches, the look's switches, the stopped page, Stop, settled equals live, report parts,
legacy turns, inert HTML, keys and the still leaf), `main/App.test.tsx` (the open book, its back pages only when
their data exists, pins as rules, the elsewhere page as view and text, ink on a chore), `tests/test_turn_moments.py`
(moments and length from a pinned clock, the stopped turn kept and left out of the model's history, older rows
unchanged, plain tool lines, the elsewhere route). The preview harness (`/preview.html?spread=open|shell|folded`,
fixture from `scripts/spread_fixture.py`) was measured against the prototype with the contest's style contract:
at 1280 x 800 and 1920 x 1080, 25 roles, the only deviations are the ribbon tabs' widths (one more tab, "What it
cost"); folded at 400 x 620, 14 roles, the only deviations are widths 14 px narrower inside her window's coat.

## Limits

- A person's Stop is not stored: the daemon cannot write the row in time when the window aborts the stream.
- Moments are kept from this build on; older turns show no moments and no length.
- The report's arrangement history and first layout, and a chore's frames, have no source and are not drawn.
- The back pages are the main window's; her window carries the conversation and the waiting page.
- The report as other assistants see it has no "Open in Athena": there is no URL scheme yet (ADR 0021).
