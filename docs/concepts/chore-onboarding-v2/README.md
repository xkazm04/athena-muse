# Chore onboarding v2 - describe a need, watch it drawn, test it, keep it

Status: **built** (2026-10-29). The daemon (WP0-WP2) and the stage in two views (WP3-0 to WP3-4) are on main; [ADR 0007](../../adr/0007-a-chore-is-written-in-conversation-and-tested-against-the-users-expectations.md) records the decisions. Measured on the built app against a real daemon, Claude Code (Sonnet), the staged need from describe to keep (`scripts/stage_seam.py`, one run each, est. cost from the ledger):

| view | turns to agreed | expected cards | test run | cost |
|---|---|---|---|---|
| Drawing (before the phase fix) | 6 | 5 | `short`, 1 of 5 | $0.80 |
| Orbit | 5 | 5 | `exceeds`, 5 of 5 | $0.48 |
| Drawing (after the phase fix) | 6 | 5 | `exceeds`, 5 of 5 | $0.51 |

Every run: no page scroll, no console error, her window showed the draft's history, the kept chore listed as `yours`. Fidelity against both winners' captured contracts: 0 deviations (Drawing 11 roles, Orbit 9) on the merged main.

Engine: v1 runs on Athena's engine wrapper with Claude Code (`ATHENA_ENGINE=claude_code`, [ADR 0006](../../adr/0006-one-engine-interface-over-four-engines.md)). Muse Code is used for pre-submission checks. The Muse API is the submission's engine and adds the multimedia path ([Later, on the Muse API](#later-on-the-muse-api)).

Supersedes: the middle of [Blue Hour onboarding](../blue-hour-onboarding/README.md), meaning its look, interview, map, rail and rehearse steps. Blue Hour's key paste and probe stay as built. Its railway art and Rail view are parked, and its sandbox page and SAM witness move to the Muse API era.

## Spark

Owner, 2026-10-27:

> Chore onboarding v2. I would like to use current main app chat interface so user can describe its need, Athena responds and build up a diagram with solution in app's UI quality right in front of eyes, trying to understand the need and asking questions, ends up with test at the end to verify with user this really is the approach and output user expects. Chat history can be accessible via Athena small window, main window will be focused on one response at time, one UI dynamic experience without scrolling. Add into the plan to /contest the UI/UX first to exercise multiple variants on top of current app design before moving to code. [...] v1 will use again llm wrapper with claude, future versions with Muse API may leverage more of multimedia use cases and capabilities.

## What it builds on (scouted 2026-10-27)

- **The main window has no chat.** "Talk to Athena" only toggles her window (`apps/desktop/src/main/App.tsx`). The `#athena` view shows cards, the Core line and the ledger, with no transcript. Conversation lives in her 400x620 window: `Transcript.tsx` scrolls and sticks to the bottom, `Composer.tsx` sends, and `useHer.send` posts `/run` and reads NDJSON `TurnEvent`s (`start | text | tool | card | done | error`). The two windows share only the daemon's SSE `/events`; each has its own zustand store.
- **A turn** offers a closed action catalog (`recall`, `remember`, `forget`, `propose_brief`, `add_app`, plus portal tools in the bench). It runs up to 6 model calls. Tool parameters are strings only. CLI engines return a reply whole, with no word streaming. Measured on one turn with two calls (n=1): Claude Code took 7.8 s, about 3-5 s per model call.
- **Chores are read-only data** under `playbooks/<id>/`, covering `playbook.json`, `world.json`, `truth.json` and `senses/` ([ADR 0005](../../adr/0005-chores-are-data-rehearsed-on-a-bench.md)). `load_chore` validates every file and reports every problem at once. Nothing writes a chore. The bench runs only from the CLI, on a throwaway daemon, and approves nothing. Bench cost on Claude Code (Sonnet, one run each) was 2.3-4.7 min and $0.41-1.01 per chore. Without targets in `truth.json`, recall scores 1.0, so a chore with no answer key always passes.
- **There is no draft table.** `settings` is a key/value store. Projects are walled spaces ([ADR 0003](../../adr/0003-projects-are-walled-spaces.md)); erasing one erases its memory, turns, cards and page reads.
- **Design system: Loop Tide.** Tokens live in `apps/desktop/src/theme/tokens.css`, primitives in `base.css`, and the shared catalog in `src/ui/`: `CardView`, `ProjectPill`, `Seal`, `Backdrop`. CSS tests enforce a 12 px floor, sizes as tokens only and a reduced-motion block per file. There is no diagram library; the SVG precedents are `projects/Field.tsx` (orbits, `animateMotion`, a reduced branch) and `theme/Seal.tsx`. The preview harness is `src/preview/Preview.tsx`.
- **First run** (`main/onboarding/FirstRun.tsx`) goes `welcome -> connect -> ready`. Its centred grid scrolls.
- **Standard read** (registry `wizard-flows` / `ai-driven-elicitation`):
  - The generator proposes content; the flow owns the rubric, coverage and completion.
  - Answers are promoted into typed state, which here is the sketch. The raw transcript never reaches the commit boundary.
  - A failed generation is never shown as "done".
  - Follow-ups are capped, and the user always has a visible exit.

## Design decisions

Wave 1:
- **Outcome: Athena writes a new chore.** The conversation ends in a real chore folder (`playbook.json`, `world.json`, `truth.json`) that passes `load_chore`.
  - Rejected: mapping to one of the library chores and tailoring a copy (safe, but limited to four needs).
  - Rejected: the diagram as the only product (nothing would run).
- **Test: both, a preview then a run.** First a quick preview of the cards she would file, which the user confirms or corrects; then a live rehearsal on the chore's invented apps. Rejected: either step alone.
- **Blue Hour: v2 replaces its middle** in the current Loop Tide design. The key and probe stay.
  - Rejected: Blue Hour art for the diagram (clashes with "on top of current app design").
  - Rejected: keeping two onboarding flows.
- **Entry: one view, two doors.** Doors: right after the first run's `ready` step, and a "Describe a need" action on Projects and on Chores. It ends in a Project with its chore attached.
  - Rejected: first run only.
  - Rejected: the stage as the home screen.

Wave 2:
- **Answer key: the preview becomes the key.** Each expected card the user marks becomes a key entry: "yes" is eligible, "no" is a trap, and a "she must never..." line is forbidden. The live run is then scored against what the user just said.
  - Rejected: the user judging the run with no key (not re-runnable).
  - Rejected: Athena writing her own key (she would grade herself).
- **The diagram is an abstraction (doctrine, owner's words: "Diagram is only abstraction of the process for user's understanding of the steps ... it is just a sketch").** The sketch is the user's picture of the process, not the chore's source. Athena writes the chore files in one step after the sketch is agreed.
  - Rejected: compiling the files from sketch edits.
  - Consequence: the preview is where sketch and files meet. It runs on the written files, so what the user confirms is the real chore.
- **Storage: the user's data folder.** Folders go under `<data_dir>/chores/<id>/` in the library's format. The loader reads both, labelled `yours`. Personal needs never reach the repo. Rejected: saving to `playbooks/`.
- **Contest: UI roster, owner judges.** Seats are `claude-sonnet-5-5@max` and `claude-opus-5-5@xhigh`, three variants each, owner review with no panel. Rejected: adding a blind panel; a wider field of Codex, Grok and agy seats.

Director decisions (convention or judgement, overridable tomorrow):
- **Rubric (flow-owned, seven slots):**
  - Slots: `need` (the job, in the user's words), `apps` (where it happens), `inputs` (what she reads: pages, mail, calls), `steps` (the order), `hand` (what waits for your signature), `output` (what you get at the end), `never` (what she must never do or touch).
  - Coverage per slot is 0, 0.5 or 1.
  - Coverage is computed from the sketch, never claimed by the model. A slot is 1 when it holds a node the user confirmed, 0.5 when it holds only Athena's proposals, and 0 when empty.
  - The sketch is "agreed" when `need`, `apps`, `hand` and `output` are at 1 and the rest are at 0.5 or skipped with a stated default.
  - At most 2 follow-ups per slot. A visible "That's enough, write it" exit is available at any coverage; open slots are shown as open, and their defaults are labelled.
- **One stage frame per reply.** Each frame holds her line, the sketch as it now stands, and at most one question with suggested answers. The CLI engine answers whole anyway, so a reply is a frame.
- **History lives in her window.** A draft is a Project from its first frame, made the active space. Every stage reply is an ordinary turn in that project's conversation, so her small window shows the whole history with no new code there. The main window shows only the current frame.
- **The sketch sends nothing to the gate.** Sketching and asking are `auto` actions. The only gated acts in this flow happen inside the rehearsal, through the real gate on the invented apps.
- **Ledger:** `Surface` gains `design` (stage turns, authoring, preview) and `rehearsal`.
- **Strings:** inline English, plain words. The screen never shows "token", "OP", "world.json", "truth" or "bench"; it says "test run", "her practice apps", "what you expect".

## Order, as run (2026-10-28)

1. **Done.** /contest installed (`.claude/contest/config.md`, v1.13.1 from the registry).
2. **Done.** Material staged (`.contest/stage/chore-stage/`, git-ignored): the invented conversation generated from sketch ops, screenshots of the real app, the Loop Tide files.
3. **Done.** Contest run, UI roster, 3 variants each, owner review. The seats reported $17.41 (32 min) and $24.69 (78 min). Verdict: A/1 and A/3 combined, both kept behind a switch.
4. **Done.** Port contract written (WP3 and the UX/UI spec below).
5. **Done for the daemon** (WP0-WP2, built while the contest ran, at the owner's call). **Done 2026-10-29:** WP3-0 (drop, the view switch's contract and counts, the generated fixture, the stage's stubs), then WP3-1 (the store over wire events, the routes, the shell and switcher, the shared parts, the keymap, the doors, the preview harness on the fixture; the views are still stubs). Then WP3-2 and WP3-3 in parallel, and WP3-4.
6. **Done 2026-10-29.** Rehearsed end to end on the built app in both views (the table at the top). The first Drawing run found a real defect in authoring, not in the stage: the written world read the invoice in the app that could act and then the attendance in a read-only app, so after reading what mattered she could file nothing. Authoring now requires "read first, act last" (a world whose last phase cannot act goes back for repair); the rerun scored 5 of 5. On the scripted engine the stage walks to agreed and then says plainly that a simulated Athena cannot write a chore.

**Known gaps after the build** (none blocks use; each is small and named here so it is not rediscovered):
- Orbit at 1024x700: in the verdict list, a long "she must never" line wraps into a narrow column beside its badge.
- The verdict's reason line repeats the bench's wording ("found 1 of 5 items, expected 80%") beside a green dot that reads as success.
- The undo toast is drawn by the shell, so neither view can skin it.
- Two `data-role="note"` meanings (Drawing's pinned question, the check card's why-not field): rename the check card's to `mark-note`.
- The preview harness's `.pv h2` style leaks into stage headings there (harness only); the stage CSS test splits `:is(a, b)` on its comma.
- Not ported from the winners: the typewriter on her line, the echo flying to its piece, the fade of a rubbed-out piece (no timers), and "Stop" on a slow reply (the daemon has no cancel route). Arrivals replay when switching views and back.
- The comparison between the views has its counts (`Draft.views`) but no screen yet that reads them across kept chores.

## The contest

**Idea for the brief:** the main window of a desktop companion becomes a stage. A person describes a chore they want handed off. Athena answers one frame at a time, asking the next useful question with suggested answers, and the process sketch of the solution draws itself as the conversation fills it in. It ends with a preview of what she expects to produce, which the person confirms or corrects, and a live test run that the person accepts. There is never a scrollbar; the past lives in her small window.

**Material to stage** (`data/`, each as `.js` setting a global plus `.json`, with a `SCHEMA.md` naming every field):
- `conversation`: one complete, invented need. Use a need that none of the four library chores covers, so the "new chore" path is honest. Proposed: *"Each month I check the after-school club's invoice against the days my kids actually went (the school portal has attendance) and dispute the extra days."* For every frame it holds:
  - her line and the question with its suggestions
  - the sketch after the frame (nodes and edges with kind, slot and origin)
  - the coverage per slot
  - the user's reply
- Then the end states:
  - the authoring wait, with a repair round
  - the preview: 6 expected cards, of which the user marks 4 yes, 1 no and 1 missing
  - the rehearsal progress events and the scored result
  - the verdict, then the saved Project
- `loop-tide/`: `tokens.css` and `base.css` verbatim, plus screenshots at 1280x800 of Projects, Chores, a chore detail, FirstRun and her window, so seats build on the current design, as the owner asked.
- `states.md`: the states each surface must show: thinking (3-8 s), a slow engine past 8 s, a failed reply, writing the chore, a repair, a written chore that cannot be fixed, the preview, rehearsal running (2-5 min), a short score, and the verdict.

**Hard constraints only** (no menu of directions, no fixed variant shapes):
- opens from disk
- no build step
- 1280x800 with no page scroll at any frame, and holds at 1024x700
- Loop Tide tokens, a 12 px type floor and reduced motion honoured
- invented data labelled invented
- the sketch must stay legible at 20+ nodes

**Owner's bar** (append to the brief): app-quality, not a mock. The current frame owns the window, the sketch growing in front of the user is the wow, and the user always knows what Athena needs from them right now.

**After the verdict:** the winner's source is kept under `.contest/` and its notes go in the vault. The port must hold the winner's fidelity, written up as the contest skill's port contract.

## Design brief

### Summary

A person opens the stage, says in their own words what they want handed off, and answers a few of Athena's questions while a sketch of the process (apps, steps, what waits for their signature, what they get) draws itself in the main window. When the sketch is agreed, Athena writes a real chore with invented practice apps, previews the cards she expects to file, and the person's yes and no answers become the chore's answer key. A live test run on the practice apps is scored against that key; the person accepts it, and the chore is saved as theirs with a Project ready to use. If they say "not quite", they return to the sketch with the gaps named.

### Flow (one state model, flow-owned)

`DraftStep`: `describe -> shape -> author -> preview -> rehearse -> verdict -> saved`. `shape` is re-entered from `author` (an authoring failure that cannot be repaired), from `preview` ("this isn't what I meant") and from `verdict` ("not quite").

| Step | What happens | Who decides it is done |
|---|---|---|
| `describe` | The user types the need. Athena proposes a project name. | The first stage turn returns. |
| `shape` | Frames: her line + sketch ops + at most one `ask`. The coverage meter follows the sketch. | The flow: the coverage gate, or the user's "That's enough, write it". |
| `author` | Athena writes `playbook.json` and `world.json` (invented apps with tables, READ and act tools, phases) from the sketch plus the conversation, using the nearest library chore as an example. `load_chore` validates; up to 2 silent repair rounds. | The validator. |
| `preview` | One call: Athena reads her practice apps and lists the cards she would file (`ExpectedCard`). The user marks each yes or no and may add a "she must never" line. | The user: every card marked. |
| `rehearse` | `truth.json` is written from the marks. The bench runner plays the phases live on a throwaway daemon. Progress and cards stream to the stage, and the score is computed against the key. | The run ends. |
| `verdict` | The score in plain words, plus her cards beside the user's expectations. The user chooses "This is it" or "Not quite" (with an optional note). | The user. |
| `saved` | The chore is copied to `<data_dir>/chores/<id>/`. The Project's brief and the chore's apps are set, and the stage hands off to the Project. | - |

### Work packages

Order: the Director commits WP0, then WP1 and WP3 run in parallel against the stubs, and WP2 follows WP1, since it shares `drafts.py`. As run on 2026-10-28: WP0, WP1 and WP2 are built and on main; WP3 is re-cut below into four packages after the contest verdict.

**WP0: contract, stubs, ADR (Director).**
- Add every identifier in Data & API to `contracts.py` and `contract.ts`, held equal by the parity test.
- Add stub routes that return 501.
- Add `src/athena/drafts/__init__.py` with final signatures.
- Write ADR 0007, "A chore is written in conversation and tested against the user's own expectations".

**WP1: drafts and shaping (daemon).**
- Files:
  - new `src/athena/drafts/{store.py, sketch.py, rubric.py, shape.py, routes.py}`
  - `store.py` (adds the `drafts` table)
  - `spaces.py` (erase support)
  - `turn.py` (the `sketch` and `ask` auto actions, offered only on a `design` turn)
  - `server.py` (mounts the routes)
- Acceptance:
  1. A scripted-engine test walks describe → shape → agreed, and coverage is computed from confirmed nodes.
  2. A model reply claiming "done" with `hand` empty does not open the gate.
  3. A failed or empty reply renders as `error`, never as progress.
  4. Erasing the project erases the draft.
  5. The stage turns appear in `GET /conversation` for the draft's space.
  6. Ruff, mypy and pytest are green.
- Doc surface: owns ADR 0007's shaping section.

**WP2: authoring, preview, key, rehearsal, save (daemon).**
- Files:
  - new `src/athena/drafts/{author.py, preview.py, key.py, rehearse.py, save.py}`
  - `chores/spec.py` (`user_library_dir()`, `ChoreOrigin`; the loader reads both libraries, and ids never collide)
  - `bench/runner.py` (runnable in-process from a folder, emitting `RehearsalEvent`s)
  - `chores/routes_chores.py` (`origin` on summaries)
- Acceptance:
  1. Authoring from the staged need's sketch yields a folder `load_chore` accepts, or `author_failed` with the validator's problems after 2 repairs.
  2. The marks turn into `truth.json` exactly: yes → eligible, no → traps, never → forbidden.
  3. A rehearsal streams `phase`, `card` and `scored` events and writes ledger rows with `surface="rehearsal"`.
  4. "This is it" copies the folder to the user library, and `GET /chores` lists it with `origin: "yours"`.
  5. A Claude Code end-to-end run on the staged need is recorded under `runs/`.
  6. Gates are green.
- Doc surface: owns ADR 0007's authoring and test section.

**WP3: the stage (desktop), a port of two contest winners behind one switch.**

The contest's verdict (2026-10-28, owner) combined **A/1 "Pencil & Ink"** and **A/3 "Orbit"**: "A/1, A/3 switchable via tab switcher. They will live together for a while, with more real use cases one will prove better, or we will develop both separately for different types of cases." One model and one set of shared parts, two views, switched by a tab, and only one view mounted at a time. The winners' source is kept under `.contest/arena/chore-stage/entries/claude-claude-sonnet-5-5_max/variant-{1,3}/`. Both load byte-identical `engine.js`, `kit.js`, `kit.css` and `base.css`, so the split below follows a line the winners already drew. The Q0 inventory of both (components, placement, motion, tokens, keys, smells, with `file:line`) is kept in the local spark vault (`.spark/Spark/ideas/chore-onboarding-v2-port.md`, not version-controlled); its conclusions are written into this package and the UX/UI spec.

Order: the Director commits WP3-0. Then WP3-1 runs, then WP3-2 and WP3-3 run in parallel, and the Director closes with WP3-4.

**WP3-0: the switch's contract and the person's erase (Director).**
- **`drop`:** the person rubs out one of Athena's pencil guesses. This adds `POST /drafts/{id}/drop {node_ids}` → `Draft`.
  - Only unconfirmed `athena` nodes can be dropped. Their links go with them.
  - It is refused while a turn runs.
  - Undo is a local toast that holds the drop for 5 s before sending it, so nothing comes back from the daemon.
- **`StageView = "drawing" | "orbit"`:**
  - `SayBody.view?` names the view the person answered in.
  - `Draft.views?: Record<StageView, number>` counts the stage turns taken in each view.
  - The counts, with the verdict and the time to agreed, are the evidence for "one will prove better". They are shown on a kept chore's detail as one plain line.
- **Stubs:** the stage store's interface, the view interface `StageViewProps {draft, frame, dispatch, words}` and a no-op view, all committed so WP3-2 and WP3-3 build against them.
- **The fixture, generated:** a script turns the staged conversation into wire shape, under `apps/desktop/src/main/stage/fixture/`: a `Draft` per frame, the `TurnEvent` stream with `sketch` ops (not snapshots), `type` (not `t`), phase `index` from 1, `AuthorEvent` and `RehearsalEvent` streams, and `ExpectedCard`s. It is invented data, labelled invented.
- An amendment to ADR 0007 covers `drop`, the two views and the comparison counts.

**WP3-1: the shared stage (desktop).**
- Files:
  - `main/stage/{route,store,keymap,switcher}.ts(x)`
  - `main/stage/parts/*` (the shared parts below)
  - `lib/api.ts`
  - `main/route.ts` (`#stage/new`, `#stage/<id>`)
  - the doors in `FirstRun.tsx` (`ready`), `projects/*` and `chores/*`
  - `preview/Preview.tsx`
- **The store** is a reducer over wire events, never over snapshots:
  - It folds `sketch` ops, `ask`, `coverage`, `AuthorEvent` and `RehearsalEvent` into the draft, keeps the current frame, and re-reads the draft after any stream that ends in `error`.
  - It holds a per-view placement memo keyed by node id, so switching away and back never moves a piece.
  - From the engine prototype, port only `coverageOf`/`isAgreed`/`missingFor` (as selectors, with `"skipped"` added), the overlay that marks new, changed and just-inked pieces, the mark/note/missing/never guards, and the row and reason logic of the score.
  - Do not port anything fixture-only (listed under Non-goals of the port).
- **Shared parts:** each is one React component, used by both views, with props for data and words:
  - the need sentence with the person's phrases marked
  - the suggestion buttons (keys 1-4) and "say it your own way"
  - the "you said" echo
  - the thinking, slow (after 8 s) and failed notices with retry
  - the "she still needs" line
  - the revisit banner after "Not quite"
  - kind labels
  - the piece card (detail, ink, drop)
  - the toast with undo
  - the step rail, and the seal state derived from the step (one derivation; the two winners disagreed)
  - the practice-app tile and the problems list in plain words
  - progress with a clock, the phase list and the filed cards (shown, never signable)
  - the score, the verdict rows and the saved-Project card
  - the switcher tab
- **One keymap**, scoped to the stage and the mounted view:
  - 1-4 pick a suggestion.
  - Enter sends (with an IME guard).
  - Escape closes a card.
  - `i` inks the focused piece and Delete drops it.
  - Y, N and the arrows mark in the check step, in both views.
- **Acceptance:**
  1. The fixture streams, fed through the store, give the same drafts the daemon stores (a test per step).
  2. Switching views mid-shape keeps the draft, the frame, the open question and every piece's place.
  3. Her window shows the draft's history live.
  4. The preview harness drives every state in `data/states.md` with no daemon, in both views.
  5. CSS tests, typecheck, lint and test are green.

**WP3-2: the Drawing view, a port of A/1 (desktop). Runs in parallel with WP3-3.**
- Files: `main/stage/drawing/*` only, plus the CSS beside them, scoped under `[data-stage-view="drawing"]` with prefixed keyframes.
- **Lanes:** five territories (where it happens, what she reads, the steps, waits for your signature, what you get), a fence for "never", the person's sentence on top, and the question pinned as a note across the bottom.
- **Placement:** a new piece takes the free row nearest the average row of the pieces it links to.
  - Unlike the winner, rows are only appended when a lane fills. Existing pieces keep their place, because the winner re-placed every piece when the 36-piece case grew the grid.
  - Places are memoised by node id in the store.
- **Links** route through the gutters between rows, and pointing at a piece heats its links.
- **Density:** the three tiers (normal, compact, tight); details that do not fit are hidden, never cut mid-word.
- **The later steps** (write, check, test, verdict, keep) sit in the winner's strip and drawer containers, built from the shared parts.
- **Motion:** pieces arrive (0.6 s plus a 0.55 s text wipe, 170 ms stagger), links wipe in (620 ms, 110 ms stagger) and pencil turns to ink (0.8 s). Under reduced motion each is an instant change.
- **Acceptance:**
  1. The fidelity contract reads 0 deviations on the roles below.
  2. Every named interaction is driven.
  3. No scroll at 1280x800 or 1024x700 at 22 and at 36 pieces.
  4. A test asserts that no piece's place changes when a node is added, including when a lane grows.

**WP3-3: the Orbit view, a port of A/3 (desktop). Runs in parallel with WP3-2.**
- Files: `main/stage/orbit/*` only, plus scoped CSS under `[data-stage-view="orbit"]`.
- **The question card** is the centre and the largest thing on screen. The six zones frame it: steps on top, where it happens and what she reads on the left, the signature and what you get on the right, never below.
- **Placement:** a piece takes its zone's next free cell in arrival order, and a dropped piece leaves a hole until the next arrival.
  - Zone capacity is computed from the zone's measured size, not the winner's caps (which were tuned to the example's counts).
  - Past capacity, the zone switches to one-line chips; past that, a "+n more" chip opens the zone's list.
- **Arcs:** seven arcs hugging the card show coverage, read from the store, never computed in the view.
- **Links** route round the card, never through it, and stay faint until a piece is pointed at. Where the winner fell back to a straight line through the card, the port routes round the nearer side.
- **The later steps** live in the card, from the shared parts. The check step deals one card at a time with Y and N, then the "missed" and "never" lines.
- **Motion:** the person's phrases fly to their pieces (720 ms, after highlights at 380 ms plus 460 ms per phrase), pieces land (0.55 s, 110 ms stagger), and pencil turns to ink with a border that draws itself (0.65 s), then settles. Under reduced motion each is an instant change. The winner's stylesheet had no reduced-motion block; the port has one.
- **Acceptance:** the same as WP3-2, with Orbit's roles.

**WP3-4: fidelity, the live seam and the switch (Director).**
- **Roles.** The owner named no single property, so the roles are each winner's defining features from its notes:
  - Drawing:
    - `piece-pencil` (dashed violet), `piece-ink` (solid), `piece-yours` (pink edge)
    - `lane`, `never-fence`, `note` (the pinned question), `ask-text`, `suggestion`, `exit` ("That's enough, write it")
  - Orbit:
    - `hub` (the card), `ask-text`, `suggestion`, `zone`, `chip-pencil`, `chip-ink`, `arc`, `exit`
- **The fidelity check:**
  - `style-contract.py capture` on each winner.
  - A harness in a git-ignored folder, served by the app's own Vite, renders the real stage components with the real stylesheet and the generated fixture.
  - `check` must read 0 deviations. Structural deviations are fixed in the selector and said; a tolerance is never widened.
- **Interactions driven in a browser, asserting what the store and the daemon receive:**
  - pick a suggestion, type an answer
  - ink a pencil piece, drop one and undo it
  - "That's enough, write it"
  - mark yes and no, add a missing line and a never line
  - "Not quite", keep
  - switch views mid-question
- **The live seam:** on the built app against a real daemon, the staged need is walked once on `scripted` (simulated) and once on `claude_code`, from describe to keep, in each view. Recorded under `runs/`.
- **Doc surface:** this document's UX/UI spec, and the ADR 0007 amendment from WP3-0.

### Data & API

Routes (all behind the bearer token):
- `POST /drafts` takes `{need}` and returns `Draft`. It creates the Project, makes it active, and runs the first stage turn.
- `GET /drafts/{draft_id}` returns `Draft`.
- `POST /drafts/{draft_id}/say` takes `{text}`, or `{text: "", choice}` when the user picks a suggestion. It returns an NDJSON stream of `TurnEvent`, which gains:
  - `sketch{ops: SketchOp[]}`
  - `ask{ask: Ask}`
  - `coverage{coverage: Coverage}`
- `POST /drafts/{draft_id}/confirm` takes `{node_ids: string[]}` (the user accepts proposed nodes) and returns `Draft`.
- `POST /drafts/{draft_id}/write` streams `AuthorEvent`: `writing`, `repair{problems}`, `written{chore_id}`, `author_failed{problems}`.
- `POST /drafts/{draft_id}/preview` returns `{expected: ExpectedCard[]}`.
- `PUT /drafts/{draft_id}/key` takes `{marks: KeyMark[], missing: string[], never: string[]}` and returns `Draft`. A missing line is placed on a practice-app tool and key when Athena can, and kept unscored when she cannot (added 2026-10-28 with the contest's staged need).
- `POST /drafts/{draft_id}/rehearse` streams `RehearsalEvent`: `phase{index, app, message}`, `card{card}`, `scored{bench: BenchSummary}`, `error`.
- `POST /drafts/{draft_id}/verdict` takes `{verdict: DraftVerdict, note?}` and returns `Draft`. A `keep` verdict also saves the chore.
- `DELETE /drafts/{draft_id}` abandons the draft. The Project stays, and the user may erase it.

Types:
- `DraftStep = "describe"|"shape"|"author"|"preview"|"rehearse"|"verdict"|"saved"`
- `Slot = "need"|"apps"|"inputs"|"steps"|"hand"|"output"|"never"`
- `SketchKind = "source"|"app"|"step"|"gate"|"output"|"never"`
- `SketchNode {id, kind: SketchKind, slot: Slot, label, detail?, origin: "you"|"athena", confirmed: bool}`
- `SketchEdge {from, to}`
- `Sketch {nodes, edges}`
- `SketchOp {op: "add"|"change"|"remove"|"link", node?, edge?}`
- `Ask {slot, text, suggestions: string[], follow_up: 0|1|2}`
- `Coverage = Record<Slot, 0|0.5|1|"skipped">`, plus `agreed: bool` on `Draft`
- `ExpectedCard {id, app, tool, key, label, why}`
- `KeyMark {expected_id, mark: "yes"|"no", note?}`
- `MissingCard {text, expected?: ExpectedCard}`, `DraftKey {marks, missing: MissingCard[], never}`
- `DraftVerdict = "keep"|"revise"`
- `Draft {id, space_id, step, need, sketch, coverage, agreed, chore_id?, expected?, key?, bench?, verdict?, note?, created, updated}`. The wire contract is committed (ADR 0007); route paths use `{id}`.
- `ChoreOrigin = "library"|"yours"`, added to `ChoreSummary` as `origin`
- `Surface` gains `"design"|"rehearsal"`
- `ActionName` gains `"sketch"|"ask"` (auto). Because tool parameters are strings, `sketch` takes `op, id, kind, slot, label, detail, link_from, link_to, quote`, and `ask` takes `slot, text, suggestions` joined by `" | "` (as built; ADR 0007 Shaping).

Persistence:
- Table `drafts(id, space_id, step, need, sketch, coverage, skipped, asked, chore_id, key, bench, verdict, note, created, updated)` (as built; `skipped` and `asked` hold the skipped slots and the questions asked per slot). The JSON columns are stored as text, and the table is erased with its space.
- The authored folder lives under `<data_dir>/drafts/<draft_id>/` until it is kept, then under `<data_dir>/chores/<chore_id>/`.

Absent values: omit the key when unknown. `bench` is absent until a run finishes, and `cost_usd` absent means unpriced (ADR 0004).

### UX/UI spec (port contract, from the contest verdict 2026-10-28)

- **The stage** is the main window route `#stage/<draft_id>`, plus `#stage/new` for the describe step. It is one frame with no page scroll at any step, at 1280x800 and 1024x700. The current frame owns the window.
- **Two views, one switch.**
  - The switcher tab in the stage's header reads **Drawing** (A/1) and **Orbit** (A/3).
  - The choice is kept per device (local storage, `athena.stage.view`). The default is Drawing, and the last one used wins.
  - Switching is a pure view change: same draft, same frame, same open question, and every piece where it was in that view. A stream in flight keeps streaming into the store.
  - These names and the default are Director decisions; the owner may rename or flip them.
- **What both views show in every shaping frame:**
  - the person's sentence with the phrases she understood marked
  - her line
  - the sketch
  - the one question with its suggestions and "say it your own way"
  - what she still needs
  - "That's enough, write it" (from the first frame, as both winners have it; open slots are labelled with their defaults when it is used)
- **Whose idea is whose:** the person's words have a pink edge, her guesses are dashed violet pencil, and agreed pieces are solid ink. The person inks a guess (confirm) or rubs it out (drop, with undo).
- **States per step** (both views; `data/states.md` is the checklist):
  - describe: empty, then sending.
  - shape: thinking; slow after 8 s; failed, with retry; her guesses waiting; agreed.
  - author: writing; repairing; could not be written (problems in plain words, and back to the sketch).
  - preview: expected cards; marked; "she missed" and "she must never" lines.
  - rehearse: phases across her practice apps, with filed cards arriving (never signable).
  - verdict: the score in items, with her cards beside your marks; "This is it" or "Not quite".
  - saved: hand-off to the Project.
- **As built in the daemon (2026-10-28), binding on the stage:**
  - Test-run cards belong to a throwaway daemon, so the stage shows them and never offers to sign them.
  - "Not quite" (`verdict: revise`) works at `preview`, `rehearse` and `verdict` and returns to the sketch.
  - A "never" line comes back as `{text, tool?}`, and the stage says which act it forbids, or that it was kept as words.
  - After a stream ends in `error`, the stage reads the draft again (`GET /drafts/{id}`).
- **Her window:** unchanged code. It shows the draft Project's conversation because the draft is the active space.
- **Shared primitives:** `Seal` and `Backdrop` from `theme/` (the winners' kit copies are not ported), plus `ProjectPill`. The stage's own shared parts live in `main/stage/parts/` until a second caller appears outside the stage.
- **Non-goals of the port** (fixture replay in the winners, not product behaviour):
  - Rewinding a frame ("Back"): a conversation cannot be unsaid.
  - Landing slots that peek at the staged next frame. The product may show one ghost slot in the territory or zone of the question's own `slot`, which the `ask` carries.
  - Lighting sketch pieces during the test run. The winners matched it by hand to the example, and their two mappings disagreed. The test run dims the sketch and shows phases and filed cards; lighting returns only if a phase can name its pieces.
  - Orbit's month calendar, which parsed day numbers out of the example's card keys.
  - Autoplay of the example, the states menu, the 36-piece stress set and the timeline timers. These belong to the preview harness only.
- **Code rules for the port** (from the Q0 inventory):
  - No string HTML.
  - No globals; one model in the store.
  - Nothing rebuilt on every event that did not change it.
  - No timers standing in for state.
  - Each view's CSS scoped under its `data-stage-view` root, with its keyframes prefixed, because the winners share class names (`.chip`, `.stage`, `.toast`) that mean different things.
  - Literal sizes, colours and z-indexes become tokens or named local variables. The CSS tests (12 px floor, sizes as tokens, a reduced-motion block per file) apply to every file.

### Strings

Inline English per repo convention, in plain words: "practice apps", "test run", "what you expect", "waits for your signature". There is no translation ritual.

### Non-goals

- Compiling the chore from sketch edits (the sketch is a sketch).
- Mapping to a library chore as the outcome.
- Athena writing her own answer key.
- Saving user chores into `playbooks/`.
- Blue Hour art and the Rail view.
- A sandbox web page and a SAM witness.
- Senses in authored chores in v1: inputs are named in the sketch and invented as tables, and no media is read.
- Running against the user's real apps.
- Scrolling transcripts in the main window.
- A third window.
- Voice in v1.

### Risks

- **Authoring reliability.** A valid `world.json` (tools, `returns.table`, `says` slots, phases) is the hardest output.
  - Mitigation: the nearest library chore as an exemplar, the validator's complete problem list fed back, 2 repairs, then an honest `author_failed`.
  - Measure it on the staged need and two more invented needs before polishing UI.
- **Sketch and files drift**, because the sketch is an abstraction. The preview runs on the files, and the verdict shows her cards beside the user's marks, so drift is visible before anything is kept.
- **Latency.** A frame takes 3-8 s on Claude Code, and a rehearsal 2-5 min. The thinking and running states must carry the wait.
  - Each rehearsal costs roughly $0.4-1.0 on Sonnet (bench, n=1 per chore).
  - Use one rehearsal per verdict, and never auto-retry.
- **A key with no money.** User marks carry no `value_usd`, so the value line is 0 unless a row carries an amount. The score uses counts, and the verdict speaks in items, not dollars.
- **Personal needs.** Drafts and user chores live in the data folder, never in git. Muse Code runs keep Contributor mode off, and neither CLI receives an API key.
- **The contest overshoots the app.** The port contract holds the winner to Loop Tide tokens and the CSS tests. Anything the app cannot honour is named at the verdict, not discovered in the port.

## Later, on the Muse API

- **Describe with media:** a photo of the paper pile, a screenshot of the app, or a voice note. Muse reads them to pre-fill `apps`, `inputs` and `need` (Blue Hour's `look` step, reborn).
- **Senses in authored chores:** the user's own sample (a scanned letter, a recorded call, a walk-through video) becomes the chore's sense fixtures. The senses build turns them into sensed tables, so the test run reads what the user actually has.
- **Witnesses:** a screenshot of the practice app on each card, and SAM where offered.
- **Voice on the stage:** Athena speaks her line and the user answers by voice. The history in her window stays the record.
- **Engine swap:** `ATHENA_ENGINE=muse`. The stage, drafts and rehearsal are engine-agnostic by construction (ADR 0006).

## Open (owner)

- The view names (Drawing, Orbit) and the default view.
- Whether the comparison counts (stage turns per view, with the verdict and the time to agreed) are enough evidence, or whether a short note from you after each kept chore should join them.
- The staged need stays the after-school club's invoice unless you swap it for one of your own.
