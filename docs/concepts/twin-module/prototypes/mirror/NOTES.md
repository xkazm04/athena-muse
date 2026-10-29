# Mirror

## Philosophy

Setting up a twin means watching your reflection learn you. A real message from a creator (Wren Atlas) is on
screen from the first minute, and the twin's reply to it sits in a mirror beside you: your own sent mail
on the left, the twin's draft on the right. Each answer you give Athena rewrites the draft. Stock phrasing
is grey (a stranger's voice), her proposals are dashed violet pencil, and anything settled is ink with a
thin pink line (your colour). The likeness plaque on the mirror's frame (from `frames[i].readiness`) climbs
from 14% to 100% as the draft stops sounding like a stranger and starts sounding like Alex.

## Both pages

- **Overview (`#overview`).** A stat strip (an unmeasured value shows "-"), then the ledger of twins with
  a totals line. Below it, "Waiting for you" shows each held draft or hand-back as a small mirror (their
  message beside its draft) with its risk list and how sure it was against the bar. A row opens in place
  to show its latest exchange as a small mirror, the drafts waiting (sign, edit or decline, with the bar
  marked on how sure it was) and its missions (the Pine & Co hand-back with what you can do). Family admin's
  sign-in is one press, either on the row or in the queue. After go-live, the strip shows what moved (+1
  live, +$0.25 est.).
- **Setup (`#setup`).** The mirror fills the page, with Athena's panel at the bottom: her line, the one
  question, three suggestions (keys 1-3), your own words, the "That's enough, rehearse it" exit from frame
  9 on, and what she still needs. The twin's nine parts sit in the right margin. Each part points a leader
  at the words it shapes, and a voice part also points back at the phrase in your mail it learned from.
  Click a part to see its pieces and ink them one by one, or use "Ink all her pencil". When a frame names
  a panel (connect, samples, dials, pages, chores, sending, memory), it opens on the "you" side and the
  reflection stays in view. Move a dial and the reply rewrites in your colour. **Rehearsal:** the mirror
  turns into the practice page, with Lumen Vale (played by Athena) on one side and your twin on the
  other. The edit on t3 shows its draft (struck in pencil) beside your edit (in ink), plus what it learned.

## The wow moment

At frame 3 the stiff "Dear Wren Atlas, ... Kind regards, The Partnerships Team" turns, piece by piece,
into "Hi Wren, 'Paper Lanterns' has been on repeat here since this morning ... cheers, Alex", and each new
phrase draws a leader to the part of the twin that wrote it. "Replay" on the likeness plaque runs every
version of the reply up to now in about three seconds, so a stranger becomes Alex in one glance.

## How it holds (scale, 1024x700)

- Fixed territories: you | seam | twin | margin. Nothing already placed moves. Changed words get a wash
  and a leader; removed words show struck through for one frame only.
- The margin holds nine places at any count of pieces: each row shows its newest piece, a count, and a
  pencil badge. The full list opens in a popover. At 700 px tall, empty places drop to one line.
- Panels, the ledger and the thread scroll inside their own area; the page never scrolls. At 1024 the
  "you" side narrows to 282 px. Captions show up to four changed parts and then "and n more".
- Leaders show only for the last answer's changes or for whatever you point at, never all at once.

## Known limits

- One staged path: any suggestion or typed answer plays the staged frames, with a quiet note.
- Dials rewrite the reply with a few hand-written rules (formality, warmth, humour, energy, length,
  directness, expressiveness, detail), not a live engine.
- Leaders are drawn for the visible layout. When a scrolling area moves they redraw on hover, not on
  scroll.
- The excerpt of "Weekly notes" (s6) is not shown, because its shared text contains a word the plain-words
  check bans. Its reason ("written to your team") is shown instead.
- "Not me" in the rehearsal is noted, but the staged conversation carries on.

## Variant data

`js/variant-data.js` is invented and consistent with `../shared/twin-data.js`:
- one inbound mail from Wren Atlas ('Paper Lanterns'), and the twin's reply to it after each of the 12
  frames, tagged by the piece that shaped each phrase;
- full text for the four kept samples (s1-s4). s1-s3 contain their shared excerpts word for word. s2 also
  carries the $50 offer that memory f4 cites. s4 adds the closing question that p_v3's evidence implies,
  so its excerpt is no longer one unbroken run of text;
- the latest exchange for each ledger row, the describe step's question, and Athena's line and question
  at each rehearsal step.
