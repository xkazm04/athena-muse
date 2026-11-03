# 0024 - The conversation is a book of spreads

Status: accepted
Date: 2026-11-03

## Context

Her window drew the conversation as a chat scroll: "You" and "Athena" lines, tool lines and cards in
the order they streamed (ADR 0016's ledger idiom), the composer at the foot. The main window's Athena
place was a dashboard: four figures, the cards in two columns, the core line and the costs table. The
owner ran a blind contest on how Athena looks when she takes the screen
([brief](../concepts/ai-ux-contest/BRIEF.md)) and chose **The Spread**: each exchange is a two-page
spread read one at a time, what you asked and what she did on the left, her answer on the right, a
ribbon of pages for the history and a bookmark for what waits on the person.

Two facts the design needs were not kept. A stored part had no moment, so "after 4 s" and "took
1 min 52 s" had no source; and a turn the engine stopped stored nothing of hers, so after a reload the
person's question stood alone and the reason was gone.

## Decision

- **The conversation is a book.** One set of components under `apps/desktop/src/spread/`, used by
  both windows: an exchange is a spread (the person's turn and the Athena turn that answers it), the
  page being written is the last spread, and the window decides which back pages follow it. Her
  window shows the book folded to one page; the main window's `#athena` shows it open, under the
  shell's bar with no dock, with the back pages (the project's report, a chore being drawn, the report
  as other assistants see it, what waits for a signature elsewhere, what it cost). The book's CSS is
  scoped under `[data-spread]`; what it adds to Loop Tide (page, gutter, leaf, ribbon, bookmark) is
  added to the theme's tokens once.
- **One store, one instance per window.** Both windows read the conversation through
  `athena/store.ts`; a turn streams in the window where it was written and the other follows
  `turn_done`.
- **A part keeps its moment, a turn its length.** Each stored part carries `at_ms` from the turn's
  start, and the Athena turn `duration_ms`, timed once by the daemon on a monotonic clock. Older parts
  have neither, and the window shows no figure for them.
- **A stopped turn is kept.** When the engine fails mid-turn, the daemon stores the Athena turn with
  the parts that streamed, `stopped` (the reason) and `duration_ms`, and announces `turn_done`. The
  model's history leaves it out.
- **Plain words at the source.** The daemon says record tool lines in plain words, and a keep that
  files a card streams its line as `gated`, so the card says it once.
- **The report as other assistants see it** is served to the app by GET
  `/spaces/{id}/report/elsewhere`, the same projection and text the `show_report` tool returns.

The element-by-element map, the data behind each field, and what was not ported are in
[the migration plan](../concepts/the-spread/MIGRATION.md).

## Consequences

- Supersedes ADR 0016's rows for her window (the ledger timeline) and the Athena place (the mind
  page). The surface stays the landing.
- The wire grows: `TurnPart.at_ms`, `Turn.duration_ms`, `Turn.stopped`, `HostReport`. Old rows read
  back unchanged; an older window ignores the new fields.
- A person's Stop is still not stored: the window aborts the stream and the daemon cannot write the
  row in time. Such a question reads "No answer was kept for this question".
- The arrangement history and the first layout of a report, and a chore's frames, have no source and
  are not drawn.
