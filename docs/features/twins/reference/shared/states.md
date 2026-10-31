# States every Twin prototype must show

Reach each from a small "States" menu (and by playing the example). Timings are what a real run
would take; a prototype may play faster but shows the real seconds.

## Overview (`#overview`)

| State | What shows |
|---|---|
| loading | the stat strip and ledger as quiet placeholders, no fake numbers |
| first run | no twins yet: one invitation to set up a first twin with Athena |
| today | `overview`: 1 live, 1 paused, 1 setting up; stat strip + ledger |
| a row opened | a twin's missions and drafts waiting, in place (no page scroll) |
| a held draft | a draft waiting with its risk list and how sure it was against the bar; sign, edit or decline |
| handed back | the Pine & Co mission that stopped and why |
| needs sign-in | Family admin paused because Google asked to sign in again; one press to fix |
| after go-live | `overview_after_golive`: Partnerships live, the stats moved |
| could not load | a plain problem line with retry; never shown as "no twins" |

## Setup (`#setup`), with Athena's chat panel at the bottom

| State | What shows |
|---|---|
| describe | empty: the person has not said what the twin is for yet |
| thinking | her reply is on its way (3-8 s) |
| slow | still thinking after 8 s |
| failed reply | nothing usable came back; retry, never shown as progress |
| a proposal waiting | her pencil pieces not yet inked |
| Gmail: idle / waiting for the browser / connected / failed | `connect.gmail.states`; waiting can last minutes and times out at 10 min |
| Notion: idle / checking / connected / rejected | `connect.notion.states`, plus "where to find it" |
| samples | six sent mails, four suggested, two with why not |
| style | eight dials with where each value came from; a preset swap |
| pages | five Notion pages, three suggested |
| chores | the presets, with tools not connected yet shown as coming |
| autonomy | Review / Assist / Auto per channel, the bar, the rule in plain words |
| memory | four facts, keep or drop with a reason |
| ready | "That's enough, rehearse it" available (frame 9 on) |
| rehearsal running | turns arriving on the practice page; a draft being written |
| rehearsal: waits | first message waiting for your signature |
| rehearsal: held | t3: below the bar and one risk; the person edits; what it learned |
| rehearsal: sent alone | t5 went on its own, with why |
| rehearsal: resolved | the mission resolved and the row filed to Notion |
| rehearsal: handed back | `stuck_alternative`: asked for money, handed back |
| go live | Partnerships is live; back to the overview |

The page never scrolls at 1280x800 or 1024x700. History of the whole conversation lives in her own
small window; the setup page may point to it.
