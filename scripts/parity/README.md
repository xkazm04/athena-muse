# Onboarding parity runner

Drives the real chore-onboarding stage (the built main window in Chrome, against a real daemon)
through the 10 use cases in `cases.py`, one lane per engine in parallel, with a persona model
answering. Each run writes hard metrics and a blind transcript; the Director grades the transcripts
without knowing the engine, then `report.py` reveals the engines and evaluates the bar.

Design: `.spark/Spark/ideas/onboarding-engine-parity.md` (the vault). The successor of
`scripts/stage_seam.py`, which stays for the single staged walk.

## Run it

Use the system `python` (Playwright for Python and Chrome live there, not in uv's environment).

```bash
# the comparison (spends plan time on both engines; ~10 cases x up to ~15 min per lane)
python scripts/parity/run.py --engines claude_code,muse_code --cases 1-10 \
    --out runs/parity/<stamp> --model muse_code=muse-spark-1.3 --model claude_code=sonnet

# some cases only
python scripts/parity/run.py --engines claude_code,muse_code --cases 1,3,7 --out runs/parity/<stamp>

# a dry run on the scripted engine (free; stops at authoring, which a simulated Athena cannot do)
python scripts/parity/run.py --engines scripted --cases 1 --out runs/parity/dry

python scripts/parity/blind.py --self-test        # the blind check fails a transcript naming an engine
python scripts/parity/blind.py runs/parity/<stamp> # every transcript is blind
python scripts/parity/report.py runs/parity/<stamp> [--reference claude_code] [--allow-ungraded]
python scripts/parity/report.py runs/parity/<stamp> --against runs/parity/<earlier>  # per-case deltas
python scripts/parity/persona.py --self-test      # the persona's review JSON parse, no network
python scripts/parity/persona.py --live           # one review and one answer from the live persona
```

Options: `--view drawing|orbit` (default drawing), `--persona off` (first suggestion, yes to every
card, ink every pencil mark: no persona calls), `--no-build` (serve the app already in `apps/desktop/dist`; otherwise it is
built once), `--lanes-serial` (one lane after the other; parallel is the default).

Every case gets a fresh daemon and data folder (`uv run athena-daemon --data <run>/data --port P
--no-peer` with `ATHENA_ENGINE`, `ATHENA_MODEL` when given, `ATHENA_TOKEN`, `ATHENA_EXTRA_ORIGINS`,
`ATHENA_TWIN_POLL=0`), so no case sees another's kept chore. The lane aborts the case when
`GET /engine` does not name the requested engine and model. Every process tree it starts ends with
`taskkill /T /F`.

## Ports

| lane | daemon | app (vite preview) |
|---|---|---|
| first engine | 8790 | 1440 |
| second engine | 8795 | 1445 |
| scripted (dry runs) | 8792 | 1442 |

A taken port stops the run before anything starts. The daemon only answers the app's origin because
`ATHENA_EXTRA_ORIGINS=http://localhost:<app port>` is set.

## The cases

| # | name | what it does differently (default: the persona answers, a suggestion when one matches its truth, else own words; reviews each pencil mark after each turn; when agreed, answers a question still open once, then exits, or after 9 turns; marks from its truth; keep; skip every site) |
|---|---|---|
| 1 | baseline | the staged need; always her first suggestion; "Ink them all" after each turn; yes to every card |
| 2 | new-domain | a landlord's repair requests from email and a portal |
| 3 | vague-need | "Help me with my emails."; the persona reveals its truth only when asked |
| 4 | over-specified | everything said up front; counts asks about slots already given |
| 5 | own-words | never a suggestion |
| 6 | early-exit | exit right after the first frame |
| 7 | correction | the persona rubs out wrong pencil pieces (as every case's review); on turn 3 it takes back an earlier answer |
| 8 | not-quite | "Not quite" at the first verdict with the persona's note naming one gap, then write, check, test, keep |
| 9 | marks | yes/no per card from the truth, and one "she must never" line |
| 10 | real-site-failure | the persona names a real website and inks her pencil site when it is the right one, so the access step lists it; one injected engine failure on the 2nd reply, recovered with Try again; every site skipped |

**The pencil review (every case but 1).** After each turn the runner reads every piece the person
can ink from `GET /drafts/{id}` (the app's `needsInk`: her pencil piece, or an agreed app piece whose
website is still her guess) and gives them to the persona with its truth, as `- <label> [<slot>] -
website: <site>`. The persona answers `{"ink": [labels], "drop": [labels]}`; a label not among the
pencil marks it was shown is ignored and counted (`extra.review_unknown`), a label in both lists is rubbed out, a label
in neither stays in pencil (`extra.review_left`). Each is acted on through its own card: the piece
opens its card, then `[data-role=ink]` (waited until the daemon has it) or `[data-role=drop]` (waited
out its five-second undo until the piece is gone). The transcript says per turn `Person reviews her
pencil marks: inks: ...; rubs out: ...`; `extra.inked` / `extra.dropped` count them, `extra.reviews`
has one row per turn. Case 1 keeps "Ink them all", the reference walk: that button covers only her
pencil pieces, never a pencil site on an agreed piece. A pencil site on an agreed piece cannot be
rubbed out from its card (the app's drop takes only pencil pieces, though the daemon would remove the
site): such a rub-out is recorded in `extra.drop_noop` and the site stays pencil.

**Leaving.** When `GET /drafts/{id}` says agreed and a question is still on screen, the persona answers
it once (the same policy as any turn, `extra.answered_after_agreed`), the runner reviews the next
frame and then exits; at most one extra turn.

**Try again once.** A failed write, preview or test run (the strip's `[data-role=retry]`, or a failed
notice's) is clicked once and counted in `ui.failures` and `ui.retries`; only the same step failing a
second time is the run's blocker (`<step> failed again after Try again: ...`).

The fault in case 10 is Playwright's `page.route("**/drafts/*/say")` serving one
`{"type":"error","error":"engine_unavailable",...}` reply, then unrouting: no product test hook.

## Outputs (`runs/` is gitignored)

```
<out>/blind.json                 {blind_id: {engine, model, case}}   - the key; do not open before grading
<out>/grades.json                {blind_id: {logic, no_repeats, clarity, progress, fidelity, note}}
<out>/<case>-<blind_id>/run.json  metrics (below)
<out>/<case>-<blind_id>/transcript.md   her lines, asks and suggestions, the persona's answers, the
                                  sketch per turn, steps with elapsed seconds, cards, score, kept chore
<out>/<case>-<blind_id>/NN-<name>.png   a screenshot per step, and `blocked` where it stopped
<out>/<case>-<blind_id>/daemon.log, data/
<out>/report.md                   written by report.py, after grading
<out>/against-<earlier>.md        written by report.py --against: per (case, engine), this run's grade
                                  mean, turns to agreed, test, calls p50 / max and blocker against the
                                  earlier run's (blind ids differ; each run's blind.json maps them)
```

`run.json`: `case, blind_id, engine, model, end{step, expected, ok}, blocker, turns{to_agreed, total},
asks[{slot, text, suggestions}], repeated_asks, repairs, author_failed, test{found, of, verdict}|null,
calls{n, latency_ms_p50, latency_ms_max, over_60s, tokens_in, tokens_out, cost_usd|null, failed},
ui{slow_notices, failures, retries, scroll_problems, console_errors, banned_words}, wall_s`, plus
`extra` (draft id, persona fallbacks, redactions, marks, never line, `sites` the access step listed
with how each ended, `access_step` whether there was one, `site_on_app` whether an app piece carried a
site and `site_pencil_left` how many were still her guess at the end, the review counts `inked`,
`dropped`, `review_left`, `review_unknown`, `drop_noop`, `reviews`, `answered_after_agreed`, whether
the fault fired, HTTP errors, steps with times). Not reached or not applicable
is `null`, never 0. `report.check_run` is the schema check; the runner applies it to every record.

- `turns.total`: /say replies that came back without an error (the describe's first frame counts).
  `turns.to_agreed`: that count when `GET /drafts/{id}` first says `agreed` (null if never).
- `repeated_asks`: an ask near-identical (difflib ratio >= 0.8 after normalising) to an earlier one,
  or the 3rd+ ask on the same slot.
- `repairs` / `author_failed`: from the `/write` stream's `repair` and `author_failed` events.
- `calls`: the case daemon's whole ledger (one daemon per case, so every row is this case's).
- `ui.banned_words`: the words of `scripts/twin_fixture.py`'s BANNED regex found in her lines on screen.

**Blind.** The transcript never names an engine or model (`claude`, `sonnet`, `muse`, `haiku`, `meta`,
`opus`, and the run's own engine and model, case-insensitive). Product text that names one (the
scripted engine says "Connect Muse ...") is written as `[redacted]` and counted in `extra.redacted`.
Anything left fails the run loudly and no transcript is written.

## The bar (per case, each engine against the reference, default `claude_code`)

| clause | passes when |
|---|---|
| end | the expected end state (`saved`) and no blocker |
| grade | overall grade (mean of the five) within 1 of the reference's |
| turns | turns to agreed <= the reference's + 2 |
| test | found / of >= 0.8, where a test ran |
| calls | no model call over 60 s |

A missing grade reads `ungraded`, never a pass. The reference engine's own grade and turns read `n/a`.

## Grading rubric (1-5 each; overall = the mean)

Read `transcript.md` against the persona's truth at its top; look at screenshots where a line is unclear.

**logic** - her questions follow from what is known and narrow the need.
- 5 every question is the next sensible one; nothing asked out of order
- 4 one question slightly out of order or broader than needed
- 3 a few detours, but the shape gets there
- 2 several questions that ignore what was just said
- 1 the questions do not lead to the chore

**no_repeats** - she does not ask what she already knows.
- 5 nothing asked twice; nothing asked that the person already said
- 4 one near-repeat, quickly moved past
- 3 two repeats, or one ask about something stated in the need
- 2 several repeats; the person has to say things again
- 1 stuck asking the same thing

**clarity** - her lines, questions and suggestions are plain and understandable.
- 5 plain words, short, every suggestion a real answer to the question
- 4 one awkward line or a weak suggestion
- 3 a few unclear lines or suggestions that do not fit the question
- 2 jargon or confusing lines more than once
- 1 hard to follow throughout

**progress** - the flow moves forward without friction or blockers.
- 5 smooth from describe to saved; no failures, no waits that feel stuck
- 4 one small hitch (a slow reply, a retry) that resolves itself
- 3 a repair or a retry the person had to act on, but it got there
- 2 a long stall or a step that needed several tries
- 1 blocked; the chore was not saved

**fidelity** - the sketch, the cards and the kept chore match the persona's truth.
- 5 every part of the truth that matters is in the sketch and the cards; nothing invented
- 4 one detail missing or slightly off
- 3 the core is right, but a slot (apps, hand-off, output, never) is wrong or missing
- 2 several parts wrong; the chore would not do the job
- 1 the chore is about something else
