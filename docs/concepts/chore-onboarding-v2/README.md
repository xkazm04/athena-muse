# Chore onboarding v2 - describe a need, watch it drawn, test it, keep it

Status: **building** (2026-10-28): the contest is running; WP0 (contract, stubs, [ADR 0007](../../adr/0007-a-chore-is-written-in-conversation-and-tested-against-the-users-expectations.md)) is committed. The owner chose to start the daemon packages (WP0-WP2) while the UI/UX contest runs; the desktop (WP3) waits for the winner.

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

## Tomorrow's order

1. **Install /contest** into this repo: add `.claude/contest/config.md` (`.contest/` is already git-ignored). The skill comes from the organisation's registry (`skills/contest`, v1.13.1).
2. **Stage the contest material** (described below) and write `BRIEF.md`.
3. **Run the contest** (`/contest "<idea>"`, UI roster, `--review owner`, 3 variants each, 90 min ceiling). The owner reviews the six variants blind and picks a winner, or a shortlist to fuse.
4. **Write the port contract.** The winner's composition, motion and states are written into the UX/UI spec below, replacing its placeholders.
5. **Build:** the Director commits the contract and stubs, then the work packages run.
6. **Rehearse end to end** on the built app with the staged need, record it, and update this document's status.

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

Order: the Director commits WP0, then WP1 and WP3 run in parallel against the stubs, and WP2 follows WP1, since it shares `drafts.py`.

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

**WP3: the stage (desktop), a port of the contest winner.**
- Files:
  - new `apps/desktop/src/main/stage/*` (route view, store slice, frame, sketch renderer, ask, preview, rehearsal, verdict)
  - `main/route.ts` (`stage` and `stage-new`)
  - `lib/api.ts` (the routes below)
  - `main/onboarding/FirstRun.tsx` (`ready` gains "Describe a need")
  - `projects/*` and `chores/*` (the "Describe a need" doors)
  - `preview/Preview.tsx` (the staged conversation drives every state with no daemon)
  - CSS beside each component
- Acceptance:
  1. No frame scrolls at 1280x800 or 1024x700, checked by a test on the layout constants plus a manual pass.
  2. The staged conversation fixture drives every state in the preview.
  3. Her window shows the draft's history live, because the draft is the active space.
  4. Places in the sketch never move when a node is added; only the new node animates in.
  5. CSS tests pass (12 px floor, tokens, reduced motion).
  6. Typecheck, lint and test are green.
- Doc surface: owns this document's UX/UI spec, filled in from the winner.

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

### UX/UI spec (placeholders until the contest verdict)

- **The stage** is the main window route `#stage/<draft_id>`, plus `#stage/new` for the describe step. It is one frame, with no page scroll at any step. The current frame owns the window, and the previous frame leaves as the next arrives.
- **Each frame** shows:
  - her line
  - the sketch (dominant)
  - the ask with its suggestion chips
  - the composer
  - the coverage meter
  - the "That's enough, write it" exit, once `need` is covered
- **States per step:**
  - describe: empty, then sending.
  - shape: thinking; a slow-engine plate after 8 s; a failed reply with a retry; a proposal awaiting confirmation; agreed.
  - author: writing; repairing; failed, with the problems in plain words and a path back to shape.
  - preview: expected cards; marked; a missing-card line.
  - rehearse: phase progress across her practice apps, with cards arriving.
  - verdict: the score in plain words; this-is-it or not-quite.
  - saved: a hand-off to the Project.
- **Shared primitives:** `CardView` (expected cards and rehearsal cards), `ProjectPill`, `Seal` (her state), `Backdrop`. New primitives stay local to `main/stage/` until a second caller appears.
- **Her window:** unchanged code. It shows the draft Project's conversation because the draft is the active space.
- **Contest-owned (to fill in):**
  - the sketch's visual language and layout algorithm
  - frame transitions
  - where the ask sits
  - how confirmation feels
  - the preview and verdict compositions
  - narrow-window behaviour

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

## Open for tomorrow (owner)

- Confirm the staged need, or swap it for one of the owner's own.
- Confirm or adjust the seven rubric slots and the agreed rule.
- After the contest: winner or fusion, and anything the winner does that the app should not.
