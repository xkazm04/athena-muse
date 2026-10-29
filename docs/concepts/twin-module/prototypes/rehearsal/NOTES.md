# Rehearsal

## Philosophy

Onboarding is a script. From the first frame the person sees the conversation the twin will have
to handle as six beats, still unwritten: its first message, their question about what they get and
exclusivity, its answer, their yes, its thanks, filing the outcome. Each beat says what the twin
needs to play it ("needs your voice", "needs to know your offer", "must not agree to exclusivity",
"may it send this alone?"). Setup runs in its own order (who, channels, voice, ...), and every
answer visibly moves the script. A need turns to her pencil (dashed violet) or your ink (solid
pink), a beat lights up once it has everything, and the twin's line for it appears in pencil. Blanks
like _creator_ and _track_ wait for the mission to name them. The parts gather in **the wings** at
the right edge, by place. The **prop** for the current frame (connect, samples, dials, pages,
chores, autonomy, memory) stands between the script and the wings, so the script is never hidden.
Athena's panel runs along the bottom.

## Both pages

- **Overview (`#overview`).** A stat strip (unmeasured shows "-") and a real ledger: rows, state
  badges, channel autonomy chips, a totals line. Each open mission is a script in progress: a beat
  strip and "beat 4 of 5: waits for your signature". A row opens in place. Its missions show as named
  beats. Drafts waiting show how sure the twin was against the bar and its risk list, with sign, edit
  or decline. Below the ledger, "Waiting for you" gathers the held draft, the under-the-bar draft and
  the Pine & Co hand-back as three cards.
- **Setup (`#setup`).** Script, prop and wings, with Athena's panel below it. The panel holds her one
  line, the question, three suggestions (keys 1-3), your own words, and what she still needs. "That's
  enough, rehearse it" is live from frame 9. The dress rehearsal plays the same script for real on
  the practice page: beats become turns. The first message waits and you mark it. The answer is held
  (77 against a bar of 80, plus one risk); you edit it, and what it learned lands in the wings in your
  ink. The thanks is sent alone (91, no risks), then the Notion row is filed and it goes live. "What
  if they ask for money?" shows the hand-back.

## The wow moment

You answer one question about your voice ("the four you marked"). The three twin lines of the
future conversation then write themselves, word by word, in your voice, still in pencil, with blanks
where the creator and track will go. The next answer ("a little more formal at first contact")
rewrites the first one in place.

## How it holds (scale, 1024x700)

- Columns are fixed: the script is flexible, the prop is 372 px (300 at 1024), and the wings are 220
  px (184 at 1024). Nothing already placed moves; new needs, pieces and lines arrive with a settle.
- Lines a frame did not touch fold to one or two lines. The beats an answer moved are kept in view,
  and a fade shows when the script runs past its column.
- The wings open only the places the current frame touched, and the others show as pencil or ink
  dots. With 28 pieces it still fits.
- At 1024x700, when an answer writes three lines at once, each shows two lines. Beat 6 can sit just
  under the fade at frame 3 and frame 9; the script column scrolls on its own, and the page never
  does.

## Known limits

- One staged path: any suggestion or own words plays the next staged frame, with a quiet note when
  you leave the path. Your own edit to the held answer is kept; the "learned" line is the staged
  one.
- Thinking, slow and failed play about three times faster and show the real seconds. "Slow" and
  "failed" are reached from the States menu: the staged replies are all under 8 s.
- Picks in the panels (samples, pages, chores, dials, autonomy, memory) are real toggles, but the
  next frame follows the staged data, whatever you picked.
- Her window lists the past of the setup only, not the rehearsal.
- Standing rules for missions are only mentioned ("Later: a standing rule for discounts").

## Variant data

[`variant-data.js`](variant-data.js) is invented and consistent with
[the shared example](../shared/SCHEMA.md). It holds:

- the six beats and what each needs;
- the twin's pencil line per beat, with the frame each version starts at (the final versions equal
  `rehearsal.turns` t1, t3 and t5);
- the Notion row cells and when each becomes known;
- the describe question and the frame 11 question;
- the cast, never and mission cards for frames with no named panel;
- the preset dial values;
- Athena's line and question for each step of the rehearsal;
- each overview mission as a script of named beats.
