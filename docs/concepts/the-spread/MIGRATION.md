# The Spread - migration plan

The owner chose **The Spread** from the blind contest on how Athena looks when she takes the screen
(brief: [ai-ux-contest/BRIEF.md](../ai-ux-contest/BRIEF.md); the winning prototype is the contest's
`entries/claude-claude-opus-5-5_xhigh/variant-3`, kept outside git under `.contest/`). This file
maps the prototype onto the real app, decides what changes, and orders the work. The architectural
decision is [ADR 0024](../../adr/0024-the-conversation-is-a-book-of-spreads.md).

**The concept.** Every exchange is a two-page spread, read one at a time like a book. The left page
says what you asked, then "What she did" (her steps with their moments), the time it took and the
est. cost. The right page holds her answer, large and comfortable. A ribbon of pages below is the
history; a pink bookmark from the gutter says what waits for your signature and opens its page.
Arrow keys turn pages. At her window's width the book folds to one page.

**The bar it is held to.** The brief's hard limits (Loop Tide at app quality; one frame, no page
scroll; 12 px floor; a still form for every motion; plain words; selectable text; every action on the
keyboard; nothing changes the person's world without a card; their arrangement stays). The registry's
`model-composed-workspace` and `agent-host-experience` golden paths. The port must look like the
prototype, not a reinterpretation: the prototype's own CSS is ported as a stylesheet over the app's
tokens, measured against the prototype with the contest skill's style contract.

## 1. Every element, and what fills it

**Liveness rule:** a field exists on screen only if a query the window actually calls fills it. "Today"
names the store, route or event that fills it on `main` before this work; "Added" names the producer
and its first consumer when nothing does.

### The head

| Prototype | Today | Added |
|---|---|---|
| Her seal and state words (Resting / Thinking... / Waiting on you / Signed) | `athena/store.ts` `sealOf` over the streamed turn and `cards` (GET `/cards?state=waiting` and `resolved`, kept by the `card_filed` / `card_resolved` events) | none |
| Project pill | `ui/ProjectPill` over GET `/spaces`, `/active-space`; PUT `/active-space` | none |
| Bookmark: "1 waits for your signature / Open its page" | the count: `waitingCount` over the same `cards` (every project, the same number as the seal's badge) | the target: `spread/model.ts` `bookmarkTarget`, the first page holding a waiting card, read from the settled turns' card parts (`Turn.parts` `card_id`, or `Turn.card_id` on an old turn). A waiting card on no page of this book opens the "Waiting for your signature" page (below) |
| "Invented example" chip | fixture honesty, not product data | not ported. The product's honest label is the simulated one: the engine status (`EngineStatus.simulated`, the `start` event) puts "Simulated" in the head |
| Calm motion, Dark | Settings > Look (POST `/settings/look`, the `settings` event repaints both windows) | the two toggles write that same setting, so a choice in the book lands in Settings and in the other window |
| "← → turn the page" hint | none | `spread/keymap.ts`, one declaration |

### The left page of an exchange

| Prototype | Today | Added |
|---|---|---|
| "You asked" and her question, as the page's title | the person's `Turn.text` (GET `/spaces/{id}/conversation`) | none |
| The date under it | the person's `Turn.created` | none |
| "What she did": one receipt per step | the Athena turn's `Turn.parts` (commit fe266c5): text runs, tool lines, cards, report parts, in streamed order | none for the steps themselves |
| A receipt's moment, "after 4 s" | **nothing.** Stored parts carry no time; only the turns' `created` (whole seconds) exists | **`at_ms` on every stored part**: milliseconds from the turn's start to the part's first event, from a monotonic clock in `turn._Parts` (`clock.elapsed_ms`, pinnable in tests). Consumer: the receipts. A part stored before this change has none, and its receipt shows no moment rather than a guessed one. While a turn streams, the window times what it sees with its own clock; the reload replaces those with the daemon's |
| "Took 1 min 52 s" | **nothing** (the difference of two whole-second `created` stamps is not a measurement) | **`Turn.duration_ms`** on the Athena turn: from the turn's start to the moment it is stored, same clock. Consumer: the tally. Absent on older turns: the tally omits it |
| "est. $0.0330" | `Turn.cost_usd` (absent means unpriced, which is not free) | none; absent reads "no cost figure" |
| Tool lines in plain words ("Looked through the songs", "Kept the song "Friday Ferries"") | the daemon's labels: "Looked at the project's track records", "Kept track "...", machinery words (contest FAULTS 5) | the daemon says them plainly at the source (`records/actions.py`), so stored parts, both windows and every engine agree; the prototype's client-side regex is not ported |
| A "keep" line that repeats its card is folded into the card | a gated `record_put` streams an `auto` tool line, then its card (FAULTS 2) | the daemon marks that line `gated`, and the existing rule (a gated line shows as its card) folds it |
| "This try stopped" badge, "Stopped: Meta is rate limiting..." | **nothing.** A failed turn stores the person's line and no reply; after a reload the question stands alone twice (FAULTS 4) | **a stopped turn is kept**: on an engine error the daemon stores an Athena turn with the parts that streamed, `stopped` (the reason in her words) and `duration_ms`, and announces `turn_done`. The model's history skips it (no empty assistant line). Consumer: the stopped page. A person's line followed by no reply at all (older data, or the person pressed Stop) says "No answer was kept for this question" |
| "Second try" badge, "She tried again on the next page" | none | derived in `spread/model.ts`: a page that asks the same words right after a stopped page |
| "Replayed: her words were written ahead..." footnote | fixture honesty | not ported (nothing in the app is replayed) |

### The right page of an exchange

| Prototype | Today | Added |
|---|---|---|
| "Her answer", her words at a reading measure; a short answer set large | `ui/Prose.tsx` over `ui/markup.ts` (the one prose door) | none; "short" is one text part under 240 plain characters |
| A card inline | `ui/CardView.tsx` over the gate (`api.decide`) | none |
| Report parts, "1 part could not be shown" | `athena/ReplyBlocks.tsx` (ADR 0022) | none |
| The stopped box and "Try again" | the live error note (`useHer.retry`) | for a settled stopped page, "Try again" sends the same words as a new page |
| Cost after her words | `Turn.cost_usd` | none |
| The simulated band | `EngineStatus.simulated` | none |

### The ribbon, the page being written, and the back pages

| Prototype | Today | Added |
|---|---|---|
| A tab per page: "Page N", her question, cost or "stopped"; a pink dot where a card waits | the same fields as above | none |
| "Write a new page": composer, live receipts, a still-working clock, Stop, "Write another page" | `useHer.send` / `stop` / `retry` over POST `/run` (the turn stream) | the clock is the window's own count from the moment of sending, said in words ("She is still working, 1 min 05 s"); it stops at `done` or `error` |
| Playback pace, "Show the rest now", the recorded-questions list | fixture playback | not ported |
| The project's report: title, "arranged ... ago", callout, the parts on the grid with pins | GET `/spaces/{id}/report` (`useMain.loadReport`), PUT `/spaces/{id}/report/pins`, POST `.../compose` | none |
| "Your standing rules" (each pin as a rule you can remove) | the view's `pinned` and the pins route | none |
| "How she arranged it" (her two arrangements, what each dropped and why) | **nothing serves the history** (ADR 0018: compositions and their reasons are not stored) | not ported; the left page says what the current reading could not show, with its reasons (`ReportView.dropped`, `reasons`) |
| "The first layout, before she arranged it" toggle | **nothing serves the default layout** beside an arranged one | not ported |
| A chore being drawn: place by place, ink and pencil, the open question | `SpaceSummary.draft` names the open draft; GET `/drafts/{id}` gives its sketch, coverage and open question; POST `/drafts/{id}/confirm` and `/drop` ink and rub out; POST `/drafts/{id}/say` answers | none; the page shows only while the active project has an open draft that is still being drawn |
| "How she drew it with you" (frames with their ops) | **nothing stores a frame's ops** | not ported; "Go on drawing it" opens the stage |
| Seen in another assistant: the report as a host shows it, "Read it as text" | the MCP view tool `show_report` (ADR 0021), reachable only behind a lease | **GET `/spaces/{id}/report/elsewhere`**: the same `mcp_views.project` and `as_text` the tool returns, behind the daemon's token. Consumer: this page |

### Pages the prototype did not have, because the real data needs them

- **Waiting for your signature**: every waiting card that sits on no page of this book (another
  project's, a routine's), with where it waits. It shows only when there is one; the bookmark opens it.
  It takes over the old Athena page's "Waiting on you" column.
- **What it cost** (main window only): the ledger of every model call, est., from GET `/ledger`. It takes
  over the old Athena page's costs table, the one place a person sees what running her costs.

## 2. The two windows

The prototype's notes settle it: "At 400 px the book folds to one page, which is her window." So:

- **Her window (400 x 620, always on top)** is the folded book: her head, one page at a time (the
  left page above the right, scrolling inside the book), and a compact bar to turn pages (previous, a
  page list, next). It carries the exchanges, "Write a new page" and, when one exists, the waiting page.
- **The main window's Athena place (`#athena`, 1280 x 800)** is the open book: both pages side by side
  and the ribbon, plus the back pages (report, chore, elsewhere, costs). It sits under the shell's bar
  with no dock, as the stage does (ADR 0016), so the shell's project pill and engine lamp stay in the
  bar and the book's head does not repeat them.
- **One conversation store** (`athena/store.ts`), one instance per window, both following the daemon's
  events. A turn streams in the window where it was written; the other window turns its page when the
  daemon announces `turn_done`. The surface's ask still hands words to her window (ADR 0016).

## 3. Kept, replaced, deleted, not ported

**Kept.** The conversation store and its reducer (`addPart`, `settledParts`), the stream and its
protocol, `ui/Prose`, `ui/CardView`, `ReplyBlocks`, the report's `Block` kit, `ProjectPill`, the
seal, the look, Loop Tide's tokens and coat.

**Replaced.** Her window's transcript (a chat scroll of "You" / "Athena" lines) and its composer bar
by the folded book; the main window's Athena page (four figures, two card columns, the core line, the
costs table) by the open book.

**Deleted in the same changes** (no dead code): `athena/Transcript.tsx`, `athena/Composer.tsx` and the
transcript rules of `athena/her.css`; `main/athena/AthenaView.tsx` and its `.m-athena` rules (the
costs columns move to `main/costs.tsx`, which the twins page also reads).

**Not ported, and why.**

- The recorded-question list, playback pace, "Show the rest now" and the replay footnote: fixture
  playback; the app answers new words.
- "Invented example": fixture honesty; the app's honest label is the simulated one.
- "How she arranged it" and the first-layout toggle: no route serves either (ADR 0018); building that
  history is a report decision, not a conversation one.
- "How she drew it with you": a frame's ops are not stored.
- The Athena page's "Decided" column across projects and the core line: a decided card stays on the
  page that filed it; core memory lives under Projects > Core.
- The back pages in her window: the report and the costs need the main window's width and stores; at
  400 px they are a click away in the main window.
- The prototype's own markdown, card and report-part renderers: the app's real ones draw instead
  (one component per visual thing).

## 4. Work packages

Each lands as one commit with its tests, gated green.

1. **Plan** - this file and ADR 0024. Check: `node scripts/check.mjs`.
2. **The daemon keeps a turn's moments and its stop** - `at_ms` on stored parts, `Turn.duration_ms`,
   `Turn.stopped` and the stopped turn kept (history skips it, `turn_done` announced), plain-word
   tool lines, the gated keep line, GET `/spaces/{id}/report/elsewhere` with `HostReport` typed in
   both contracts. Checks: pytest for each (a pinned clock gives exact `at_ms`; an older row reads
   back unchanged; an engine error stores one stopped turn and the next turn's history has no empty
   reply; the elsewhere route answers what `show_report` answers), the parity test.
3. **The book's model** - `spread/model.ts` (exchanges from turns, receipts in plain words, the
   tally, second tries, the bookmark target, the page list), `spread/phase.ts` (the page being
   written, as a transition table), `spread/keymap.ts` (one declaration). Checks: vitest on each, no
   DOM.
4. **The book** - `spread/` components and `spread/spread.css` (the prototype's stylesheet over the
   tokens; the page, gutter, leaf, ribbon and bookmark tokens added once to `theme/tokens.css`), and
   her window cut over to the folded book; the transcript and composer deleted. Checks: her window's
   tests rewritten against the book (pages turn by key and tab, a live page writes and settles into
   the book, a stopped page, a waiting card and the bookmark, calm stills the leaf, the handed words
   land on the new page), the CSS rules (tokens only, 12 px floor, a reduced-motion block).
5. **The open book in the main window** - `#athena` becomes the open book with the back pages; the old
   Athena page deleted. Checks: the main window's tests (route, back pages present only when their
   data is, pins as rules, ink and rub-out, the elsewhere page as view and as text, the costs page).
6. **Preview and fidelity** - a fixture generated through the daemon's own turn loop
   (`scripts/spread_fixture.py`), a full-window harness in the preview page, screenshots at 1280 x 800
   and 400 x 620, and the style contract against the prototype. Check: the screenshots and the
   contract's deviations, reported.
7. **Docs** - `docs/features/the-spread.md` (built), this concept's status left to the Director.

## Decisions

- **The windows (2).** Her window is the folded book and the main window's Athena place is the open
  book; the prototype's note says so, and the main window already has a place for her. Not the
  landing: the prototype models none of the app's other places, so the surface stays the first screen
  (ADR 0016).
- **Timings are stored, not derived.** `created` has whole-second resolution and marks when a row was
  written, not when a step happened; deriving "after 4 s" from it would be a number without its
  measurement. The daemon times each part once, and the window shows nothing where it has no figure.
- **A stopped turn is a turn.** The orphan question (FAULTS 4) and the reason lost on reload are one
  fault: the daemon threw away what it knew. It now keeps it; the model's history is unchanged.
- **The person's Stop is not stored.** When the window aborts the stream the daemon does not learn why
  in time to write a row; the page says "No answer was kept for this question", which is true.
- **Plain words at the source.** Tool labels are fixed in the daemon, not reworded in the window, so
  every surface and the stored record agree.
- **The elsewhere page reads a route, not the MCP tool.** The tool needs a lease meant for other
  assistants; the route returns the same projection behind the app's own token.
- **The back pages are main-window only** (see 3).
- **The bookmark counts every project**, so it always agrees with the seal's badge.
- **"Write a new page" settles into the book.** When a written page is done, the conversation reloads
  and the window turns to the page it became; the settled page is drawn from stored parts exactly as it
  was written.
