# Her window - the transcript

Built 2026-11-03. Layout and look: [ADR 0016](../adr/0016-the-app-wears-the-variants-layout.md) (the transcript as a timeline with "You" and "Athena" eyebrows).

## What it does

- **Her words read as rich text.** Her replies, settled or still streaming, and a chore's brief in the main window all come through one door, `ui/Prose.tsx` over `ui/markup.ts`: a dependency-free reader of a markdown subset (paragraphs, line breaks, bold, italic, inline code, fenced code with a Copy button that copies the source exactly, bulleted and numbered lists, links). Everything else stays literal text, and every string reaches the page as a React text node, so HTML or script in a reply is shown as characters and never runs. A link is not clickable: its words are shown with the true address beside them, because both are model-authored.
- **A reply streams in the order it was written.** Text runs, tool lines and cards stand in the order the stream delivered them (`LivePart[]` in `athena/store.ts`); a sentence written after a tool line comes after it. Her name is said once per turn, the cost follows her last words, and the dots show while she is writing and no words are arriving.
- **A streaming prefix renders stably.** An open code fence is already a code block, an unclosed `**` or `*` or backtick is styled as if closed at the tail, and a marker the next delta has yet to decide is held back; only the last block is re-read as words arrive. Settled text has no provisional reading: an unmatched marker there is literal.
- **New words fade in.** While she writes, each delta's words fade in once (opacity, `--dur-fast`), snapped to whole words; earlier words are never animated again, and nothing animates under calm motion, under reduced motion, or once the turn is done.

## Verified

`ui/markup.test.ts` (each construct, literal fallbacks, streaming prefixes, re-reading only the last block giving the same blocks as a full read), `ui/Prose.test.tsx` (elements, inert HTML, links, copy, stable prefixes, the reveal and its calm rule), `athena/App.test.tsx` (parts in streamed order, rich text and inert HTML settled and live), `main/chores/chores.test.tsx` (the brief through the same door).

## Limits

- Settled turns reload as `{text, card_id}`: tool lines and the order of text and card are shown while a turn streams, not after a reload.
- Not in the subset: headings, tables, quotes, nested lists (an item indented up to three spaces joins the list above; deeper, it is a line of the item above), images. They show as their characters.
- The reveal snaps to spaces, so a script written without spaces fades in by delta, not by word.
