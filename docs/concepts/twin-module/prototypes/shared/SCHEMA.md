# Twin prototypes - the shared invented example

Everything here is **invented**: the owner Alex Moreno, the studio, the creators, the tracks, the
addresses and the amounts. Every prototype says so on screen (a small "Invented example" label).

## Files

- `twin-data.js` sets `window.TWIN_DATA`; `twin-data.json` holds the same. Load the `.js` with a
  `<script>` tag so a page opens from disk. Both are **generated** by `src/build.mjs` from
  `src/twin.src.mjs`; never edit them by hand. `node src/build.mjs` is byte-stable.
- `states.md` lists every state a prototype must be able to show.
- `loop-tide/` is the app's design system, verbatim: `tokens.css` (colour roles, `--fs-*`, `--sp-*`,
  `--r-*`, `--dur-*`, `--ease-settle`, `--font-sans`), `base.css` (`.btn`, `.btn-primary`,
  `.btn-quiet`, `.plane`, `.badge[data-tone]`, `.field`, `.backdrop`), `coat.css` (her window's glass)
  and `fonts.css` + `fonts/` (Outfit 400/500/600). Load `fonts.css`, then `tokens.css`, then `base.css`.

## `TWIN_DATA`

| key | meaning |
|---|---|
| `invented` | the honesty line |
| `owner` | `{name, first, studio}` |
| `now` | the prototype's "now", ISO local time; every relative time is computed against it |
| `places[]` | what a twin is made of, in setup order: `{id, label, required}`. `required` is the coverage setup needs (1, 0.5 or 0). Ids: `who, channels, voice, knowledge, chores, never, autonomy, memory, mission` |
| `channelKinds` | `{gmail: {label, by, connect: "sign_in"}, notion: {label, by, connect: "key"}}` |
| `autonomyLevels[]` | `review`, `assist`, `auto`, each `{id, label, says}` |
| `overview` | the twins page today: `{rows[], stats}` |
| `overview_after_golive` | the same page after Partnerships goes live (2 live twins) |
| `setup` | the onboarding of the Partnerships twin |

### `overview.rows[]` - one twin, one ledger row

`{id, name, purpose, state, since, channels[], filled, week, missions[], waiting[], readiness, open_missions, waiting_count, paused_because?}`

- `state`: `live | paused | setting_up`.
- `channels[]`: `{kind: "gmail"|"notion", account, status: "connected"|"needs_sign_in", autonomy: "review"|"assist"|"auto", bar: number|null, health: "active"|"quiet"|"stale", last_at, split?, scope?}`. `split` is `{first_message, replies}` when a channel has two levels. `bar` is how sure it must be (0-100) to send alone; `null` when the channel is not on Auto.
- `filled`: coverage per place id (0, 0.5, 1). `readiness`: whole percent, the mean over the places with `required > 0`. Computed, never declared.
- `week`: `{sent, sent_alone, held_by_risk, median_reply_min, cost_usd}`. `null` = not measured and renders "-", never 0. `cost_usd` is an estimate; label it "est."
- `missions[]`: `{id, title, with, channel, state: "open"|"resolved"|"handed_back", turns, last_at, note}`. `handed_back` = it stopped and needs you.
- `waiting[]`: drafts waiting for your signature: `{id, mission, channel, to, subject, excerpt, confidence, risks[], why: "held"|"below_bar"}`. `held` = its risk list is not empty; `below_bar` = it was not sure enough.

### `overview.stats` - the stat strip (derived, see `src/build.mjs`)

| key | formula |
|---|---|
| `live` | count of rows with `state == "live"` |
| `waiting_for_you` | sum of `waiting.length` + missions `handed_back` |
| `missions_open` | sum of missions `open` or `handed_back` |
| `sent_week` / `sent_alone_week` / `held_by_risk_week` | sums of `week.*`, nulls skipped |
| `cost_usd_week` | sum of `week.cost_usd`, est. |

### `setup` - onboarding Partnerships

| key | meaning |
|---|---|
| `twin_id`, `need` | the twin being set up; what the person typed first |
| `first_ready_frame` | the first frame where `ready` is true (9). From then on "That's enough, rehearse it" is available |
| `frames[]` | one per reply from Athena (12) |
| `connect` | `gmail` and `notion` connection material and their state words |
| `samples[]` | sent mail she found: `{id, to, subject, date, words, mark, excerpt, why_not?}`. `mark: true` = she suggests keeping it |
| `style` | `{presets[], dials[]}`, dial = `{id, label, low, high, value 1-5, source: "learned"|"preset"|"you"}` |
| `pages[]` | Notion pages it can see: `{id, title, kind, suggest, why_not?}` |
| `chorePresets[]` | ready-made chores: `{id, tool, name, does, kind: "outcome"|"inbox"|"test"|"channel", suggest, later?, coming?}`. `coming` = a tool not connected in this app yet; show it, cannot pick |
| `autonomy` | `{bar_default, rule, channels[]}` |
| `memory[]` | facts she noticed: `{id, fact, from, suggest: "keep"|"drop", reason?}` |
| `rehearsal` | the dress rehearsal (below) |
| `golive` | `{line, stays[]}` |

### `setup.frames[i]`

| field | meaning |
|---|---|
| `index` | 0-based |
| `user` | how the person got here. `{text}` typed (frame 0: the need); `{text: "", choice: n}` = picked suggestion n of the **previous** frame's ask |
| `elapsed_s` | how long her reply took (illustrative, 3-8 s) |
| `line` | Athena's one line |
| `ops[]` | changes in this frame: `{op: "add", piece}`, `{op: "change", piece: {id, ...fields}}`, `{op: "dial", dial, value, source}` |
| `confirm[]` | piece ids the person accepted in this frame (her pencil becomes ink) |
| `panel` | the interactive part for this frame, or `null`: `{kind: "connect", channel}`, `{kind: "samples"}`, `{kind: "style"}`, `{kind: "pages"}`, `{kind: "chores"}`, `{kind: "autonomy"}`, `{kind: "memory"}`, `{kind: "rehearsal"}` |
| `ask` | the one question: `{place, text, suggestions[3]}`; `null` on the last frame (the rehearsal starts) |
| `pieces[]` | the whole twin **after** this frame (computed) |
| `dials[]` | the style dials after this frame (computed) |
| `coverage` | per place 0 / 0.5 / 1 (computed) |
| `ready`, `readiness` | computed |

A **piece**: `{id, place, label, detail?, origin: "you"|"athena", confirmed, evidence?[]}`. `origin: "you"`
is confirmed when added (ink). `origin: "athena"` is her proposal (pencil) until a later frame's
`confirm` inks it. `evidence` names sample ids it came from.

### `setup.rehearsal`

`{where, played_by, turns[], outcome, stuck_alternative, slow_after_s}`.

- `turns[]`: `side: "twin"` turns carry `{kind: "first_message"|"reply", elapsed_s, confidence, risks[], decision: "waits"|"sent_alone", decision_why, text, mark: "me"|"edited", edited_text?, learned?}`; `side: "creator"` turns carry `text` (Athena playing the creator). `at_s` is seconds since start (illustrative; play faster, show the real seconds).
- The staged path: t1 waits (first message) and is marked "that's me"; t3 is held (77 < 80 and one risk) and the person edits it, which teaches it; t5 is sent alone (91, no risks).
- `outcome`: `resolved`, and the `file-outcome` chore adds `row` to Notion: Partnerships.
- `stuck_alternative`: the creator asks for money instead; it hands the conversation back to you.

## Words on screen

Plain words for people who are not developers. Never: "token", "connector", "OAuth", "API", "LLM",
"model", "prompt", "node", "slot", "op", "fixture", "confidence score". Say: "sign in with Google",
"your Notion key", "her proposal" / "her pencil", "in your words", "waits for your signature",
"sends on its own", "how sure it is", "its risk list", "practice page", "mission", "handed back to you".
Pink is the person (`--role-human`); violet is Athena's proposal (`--role-agent`); green, amber and
red mean status and nothing else.
