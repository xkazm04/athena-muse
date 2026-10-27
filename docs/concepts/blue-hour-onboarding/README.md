# Blue Hour onboarding - design and implementation plan

Status: **designed, parked** (2026-10-20; restated in this repository's own architecture 2026-10-27). Not built. Its look, interview, map, rail and rehearse steps are superseded by [Chore onboarding v2](../chore-onboarding-v2/README.md) (2026-10-27); the key paste and probe stand. Produced by a /spark session (4 rounds, 14 questions) after the owner chose **Blue Hour** as the visual direction for Athena on Muse, the Meta Global AI Developer Hackathon Startup-track entry.

Areas: the main window's first run (`apps/desktop/src/main/onboarding/`), the engine seam (`src/athena/engine/`), the gate and the ledger (`src/athena/gate.py`, `src/athena/ledger.py`) (primary); the daemon routes, the main window's routes (`apps/desktop/src/main/route.ts`), chores (`playbooks/`, `src/athena/chores/`, `src/athena/bench/`) (touched).

Reference design: [`reference/`](reference/) - the winning Blue Hour variant as judged (`index.html` landing, `app.html` roof, `fixtures.js`, `NOTES.md`). Opens from disk; all data fictional and labelled simulated.

## Spark

Owner, 2026-10-20, after choosing Blue Hour as the winner (paraphrased):

> Prepare a design and implementation plan for an onboarding built around a strong demo use case, for non-developers: anyone can onboard Meta's products, is guided to define their use cases while the project rail is drawn in front of their eyes, and can do a test run inside the onboarding.

Context: Meta Global AI Developer Hackathon, Startup track (technical execution, holds up in production). Product: Athena on Muse. Winning art direction: Blue Hour - cinematic blue-hour railway; landing = film frame with the Muse Spark train held at a red signal, a lever to pull; roof = lit mimic panel with six sections (Yard, Interlocking, Line, Timetable, Train Register, Test Track).

## Targeting

Primary: the first run in the main window (today `FirstRun.tsx` + `probe.tsx`: key paste and live probe), the engine seam (Muse and, later, Llama behind the `Engine` protocol), the gate (the test run files a real card that resolves once).
Touched: the main window's hash routes (a new `#rail` view), the daemon (new onboarding and sandbox routes), chores (the use cases the interview maps to), the bench (its throwaway-daemon pattern).
Excluded: a new window for onboarding (the main window already hosts the first run; a third Tauri window costs more than a view); a hosted web onboarding (a separate service, not the desktop path) - unless wave 1 picks it.

## What the plan builds on

**First run today.** The main window opens on `FirstRun` when no key is known: paste a Meta key (`POST /engine/key`, the daemon writes owner-only `meta-key.json`), then a live probe (`POST /engine/probe`) shows how fast Muse answered; no key means the `scripted` engine, labelled simulated ([ADR 0004](../../adr/0004-muse-engine-key-custody-and-the-gate.md)). Views are hash routes in `main/route.ts` (`#projects`, `#projects/<id>`, `#projects/core`, `#projects/<id>/memory`, `#athena`).
**Engines.** One seam: the `Engine` protocol (`complete(messages, tools)` streaming text, tool calls and usage; `probe()`), built per request by `build_engine`. `muse` speaks OpenAI-compatible Chat Completions; prices live in `engine/prices.py` and an unlisted model is unpriced. Native tool calls are proposals the turn classes against the action catalog. Engine ids are typed in the wire contract and held equal across Python and TypeScript by the parity test.
**Gate.** A closed action catalog in `turn.py`, each action `auto` or `gated`. A gated call files a card (`Gate` in `gate.py`); `POST /decisions/<card_id>` resolves it exactly once (one conditional UPDATE) and the daemon executes the approved action itself, once. Portal tools from a chore's world are `portal_read` (auto) or `portal_act` (gated) ([ADR 0005](../../adr/0005-chores-are-data-rehearsed-on-a-bench.md)).
**Ledger.** One row per model call with surface, space, engine, model, tokens, estimated cost and latency; surfaces today are `turn` and `probe`.
**Test-run machinery.** The bench opens a throwaway daemon, walks a chore's phases with the chosen engine, approves nothing and scores the cards against `truth.json`. There is no rehearsal route in the daemon yet, and the shell captures no screenshots.
**Use-case definition.** Chores are data under `playbooks/<id>/` (`playbook.json`, `world.json`, `truth.json`, `senses/`), loaded and validated by `athena.chores`. No user-authored chore record exists.
**Blue Hour.** The reference is vanilla JS, no deps, system fonts: roof.js lays six sections on a 2400x1350 world with a camera (fit, fly, zoom) and a 12-px semantic tier. Port to React: camera math as hooks, string builders as JSX. Its tokens (brass, enamel, cream, red, green, amber, Muse blue) are new beside the Loop Tide theme (`apps/desktop/src/theme/`), whose CSS tests guard sizes, ink and reduced motion.
**Hero demo and people.** The plan assumes one hero chore from `playbooks/`, filmed end to end, and two readers: a first-time non-technical person and a five-minute evaluator.
**Registry standards read:** wizard-flows (step-state-model, ai-driven-elicitation: generator proposes content, flow owns structure/coverage; frontier-batched-elicitation with recommended answers; commit-boundary: review and apply from one assembly), hitl-approval (consent flow), demo-data-plane (fake-surface-honesty-contract).

## Design decisions

Wave 1 (2026-10-20):
- Home -> **Desktop first act** (rebuild the first run as Blue Hour; real local daemon + gate; filmed for the video). Rejected: hosted web onboarding (hosting, shared key, not the real first run); both-one-codebase (1.5x work).
- Test run engine -> **Live Muse, scripted fallback**: one phase of the chosen chore; >20 s or unreachable -> replay a recorded run labelled "recorded". Implies the `muse` engine behind the seam (built, ADR 0004). Rejected: scripted only (Meta does no work in the beat); live on the user's real app (needs connection first, touches real data).
- Use case -> **Muse interview -> chore**: rounds with recommended answers, coverage scored by the flow against a fixed rubric, mapped to one of the chores in `playbooks/`, personalised by editing a copy of its world and re-validating it. The interview runs on Muse. Rejected: catalogue pick (weaker reveal); Muse-authored world (must pass the chore validator -> fragile).
- Meta scope in onboarding -> **all four**: SAM witness on the card, Llama diversion drill, Muse reads a screenshot to pre-fill, real tokens + est. $ on the register.
Wave 2 (2026-10-20):
- Muse access -> **Guided key paste**: step opens Meta's developer page, plain-words copy guide, live probe ("Muse answered in 0.8 s"), the user owns the bill. Rejected: trial relay (our money, breaks "no provider is mandatory"); judge-build env key (as the product path).
- Rail build-up -> owner answered **"Prototype all three approaches"** (doctrine, not a pick): ghost panel fills in / track laid as you go / ghost panel + one laying beat are all built against ONE rail model, switchable, owner chooses after seeing them. Implies: rail model derived from onboarding state is renderer-agnostic; three renderers.
- Test target -> **Rendered sandbox page**: the chosen chore's world.json rendered as a real page in a sandboxed webview; Muse reads its DOM/tools; card screenshot = real pixels; SAM segments it. Works for every chore. Rejected: the person's real apps (connection first, real data); simulated portals + SAM sim (contradicts a real SAM witness).
- After -> **Rail becomes a view**: a new `#rail` route in the main window (Blue Hour roof on live data); Projects stays home. Rejected: rail as home (re-skins the first impression); onboarding-only (drawn rail thrown away).

Wave 3 (2026-10-20):
- Llama -> **same Meta key, Llama API** (verify day 1; if absent, Baseten is the fallback - a second key).
- SAM -> **Meta API if offered, else our Modal endpoint** labelled "hosted by Athena"; product path without it shows "one witness".
- Recorded fallback -> **real Muse runs of each chore**, shipped as transcripts; replay the mapped chore if recorded, else the hero chore; always labelled "recorded on <date>". Rejected: hero only; no fallback.
- Prototypes -> **in-app behind a toggle** (preview.html + first act, one recorded onboarding session drives all three; winner stays, two deleted before ship). Rejected: contest round first; a separate prototype app.

Wave 4 (2026-10-20):
- Run in -> **real daemon, sandbox origin**: the daemon serves the sandbox page on loopback, the desktop opens it in a webview, the page exposes tools generated from world.json, a screenshot of it feeds SAM, and the card goes through the real gate and ledger tagged `surface="rehearsal"`; execute mutates only the page's in-memory data. Rejected: a throwaway headless daemon like the bench's (the page and the screenshot never exercised).
- Key store -> **owner-only `meta-key.json` in the data dir, held by the daemon** and never returned to a window (built, ADR 0004). Rejected: OS keychain.

Director decisions (convention or judgement, overridable):
- Hero demo: one chore from `playbooks/`, chosen when the fallback runs are recorded. The video films this path; any user may define any chore.
- Rubric (5 slots, flow-owned): `apps` (which web apps), `chore` (the job), `hand` (what must never happen without you), `worth` (time or money per period), `never` (people/data she must not touch). Coverage per slot 0 / 0.5 / 1; gate to Map = apps, chore, hand at 1 and the rest >= 0.5 or explicitly skipped-with-default; max 2 follow-ups per slot; visible "that's enough" exit at any coverage.
- Voice and Face stay off the critical path: optional "Later" plates after the signed test run. The first steps are the Muse key, then look (a screenshot or an open page).
- Every Muse/Llama/SAM call in onboarding writes a ledger row (ADR 0004): `surface="onboarding"` for look/interview/map, `surface="rehearsal"` for the test run.
- Screenshot to Muse is consent-gated by a plain line before upload ("this picture goes to Meta's Muse").
- Map with no good fit (top score below threshold): show the 3 closest with "not a perfect fit" and the catalogue as an escape - never invent a chore.
- Strings inline per repo convention (the desktop has no i18n layer; locale_count 1).
- Blue Hour tokens arrive as a scoped skin `[data-skin="blue-hour"]` in a new `apps/desktop/src/theme/blue-hour.css`, used by the first act and the rail view only; the existing CSS tests apply to it.

## Design brief

### Summary
A non-developer installs Athena and, in one sitting, connects Meta's Muse with a guided key paste, shows Athena one of their apps and answers a few rounds of suggested questions while their Blue Hour rail draws itself in front of them. Athena maps the answers to one of the validated chores, opens a sandbox copy of that app, and runs one live Muse turn that stops at the red signal with a decision card carrying two witnesses (DOM and SAM) and its real cost. The user signs it, the train leaves, the action runs once on sandbox data, and the drawn rail stays as a live "Rail" view.

### Flow (first act, one state model)
`key` (guided Meta key paste + live probe) -> `look` (drop a screenshot or use an open page; Muse vision pre-fills apps and chore guesses; consent line) -> `interview` (frontier rounds, each question with a recommended answer; coverage meter over the 5 slots) -> `map` (ranked chore candidates with economics; pick) -> `review` (commit boundary: what the test run will do, on which sandbox, which actions are gated, est. cost - rendered from the same assembly the run uses) -> `rehearse` (sandbox page opens; live Muse turn, or recorded fallback after 20 s; card with witnesses; optional "pull the plug" Llama drill) -> `signed` (lever pulled; execute on sandbox; ledger row; train leaves) -> `later` (Voice, Face, connect a real app; finish -> `onboarded` setting true, land on `#rail`).
The rail (Yard, Interlocking, Line, Timetable, Train Register, Test Track) is visible beside every step and fills from the same state.

### Work packages
Order: the Director first commits the wire contract (`contracts.py` + `contract.ts`, held equal by the parity test, for every identifier below) and compilable stubs (`RailModel`, `deriveRail`, a stub renderer, stub routes returning 501). Then WP1, WP2 and WP4 run in parallel; WP3 builds against the stubs and integrates as WP2/WP4 land.

**WP1 - Meta engines (engine seam).** Files: `src/athena/engine/meta.py` (a Llama configuration beside Muse on the same OpenAI-compatible client), `src/athena/engine/prices.py` (Llama est. prices, `cost_estimated`), new `src/athena/engine/divert.py` (`DivertingEngine(primary, fallback, Breaker(failures=2, window_s=60))`, itself an `Engine`), new `src/athena/witness.py` (`Witness.check(png, box, label) -> {iou, agree, source, ms}`; sources `meta`, `modal`, `none`), `contracts.py` + `contract.ts` (`EngineId` gains `llama`), `routes_turn.py` (`GET /engine` reports each engine found/not_found by key presence; probe). Day-1 task inside the package: probe the real Meta API and fill `docs/hackathon/meta-api-facts.md` (endpoint shape, model ids, Llama on the same key?, SAM on the API?, prices), every fact tagged measured/press/unverified.
Acceptance: (1) `uv run pytest tests/test_engine_meta.py` covers a Llama turn via a fake transport, unpriced vs estimated cost, and a breaker that diverts after 2 failures and records `diverted_from` on the ledger row; (2) the contract parity test holds with the new engine id; (3) `GET /engine` shows `llama` found/not_found by key presence and a live probe on request; (4) the key is never returned to a window or logged (test); (5) mypy strict + ruff clean. Doc surface: owns a new ADR (next free number) for diversion and the witness, and `docs/hackathon/meta-api-facts.md`.

**WP2 - Onboarding and sandbox service (Python daemon).** Files: new package `src/athena/onboarding/` - `rubric.py` (slots, coverage, gate predicate), `interview.py` (Muse structured-output turn proposing questions + recommended answers + slot assessments; the flow scores and owns completion), `look.py` (screenshot -> `{apps[], chores[]}` guesses), `mapper.py` (rubric -> ranked chore id candidates over the library summary; ids validated against the `athena.chores` loader), `sandbox.py` (a copy of the chore's world shaped by the answers -> `Sandbox{id, origin, url, playbook_id}`; renders the world's tables as an HTML app page and exposes its tools with their read/act class from world.json; in-memory execute), `recorded.py` (a replay `Engine` for transcripts under `playbooks/<id>/muse-run.ndjson`); new `src/athena/routes_onboarding.py` mounted by `server.py`; `scripts/record_muse_runs.py`. Cross-cutting property owned here: a run with `surface="rehearsal"` may only target an origin in the live sandbox registry (refused otherwise), and onboarding/rehearsal calls write ledger rows with their surface tag.
Acceptance: (1) a daemon test modelled on `tests/test_turn_flow.py`: create a sandbox for the hero chore -> `POST /run` on its origin with a scripted transcript -> card filed -> `POST /decisions/<id>` approve -> executed once -> ledger row `surface="rehearsal"`; (2) interview coverage is computed by the flow - a test where the model claims "done" with a slot empty does not open the gate; (3) the mapper never returns an id outside the library; (4) replay after a 20 s timeout yields `recorded: {date}` on the run events; (5) a rehearsal run against a non-sandbox origin is refused. Doc surface: owns a new ADR (next free number) for rehearsal on a sandbox origin.

**WP3 - The first act (desktop).** Files: new `apps/desktop/src/main/onboarding/model.ts` (reducer: `OnboardingState`, `OnboardingEvent`, step validity predicates, snapshot in the daemon setting `onboarding.v1` with schema version, resume offer), `apps/desktop/src/lib/api.ts` (the routes below), `main/onboarding/` rebuilt as the Blue Hour first act (keeps the key paste and probe, no fork), `theme/blue-hour.css`, steps UI (key paste with Meta page link + probe result; look drop zone + "use the page I have open"; interview rounds with accept/correct per question; map cards with annual value; review; rehearse with the sandbox page in a webview, card with witness lamps and a "Pull the plug" drill; lever sign via `POST /decisions/<id>`), `main/route.ts` (finish lands on `#rail`), a recorded onboarding transcript + test.
Acceptance: (1) killing the app mid-interview and reopening offers resume with answers intact; (2) the review screen and the rehearsal request are built from one `assembleRehearsal(state)` function; (3) the test signs a card and sees the ledger row; (4) every text >= 12 px at 1280x800 and 390 wide; (5) typecheck, lint, test green. Doc surface: owns the README onboarding section.

**WP4 - The rail (model, three build-up renderers, Rail view).** Files: `apps/desktop/src/main/rail/model.ts` (`RailModel` + `deriveRail(onboarding, live)`; contract committed by the Director), `main/rail/camera.ts` (port of roof.js fit/fly/zoomAt/navFromCam, 12-px semantic tier), `main/rail/` views (L0/L1/L2 of the six sections; Escape/Home/arrows/find), renderers `main/rail/build/{ghost,laid,beat}.tsx` selected by the `railBuild` setting, a toggle in `preview/Preview.tsx`, the `#rail` route in `main/route.ts`.
Acceptance: (1) one recorded onboarding session (a fixture of `OnboardingState` snapshots) drives all three renderers in preview; (2) places never move: a test asserts section rects are identical before and after a state change for `ghost` and `beat`; (3) the Rail view renders live data (engine, ledger, cards) after onboarding; (4) every Muse figure is tagged est. and art labelled stylised; (5) typecheck, lint, test green.

### Data & API
Routes (daemon, all behind the bearer token):
- `POST /onboarding/look` body `{png_b64, consent: true}` -> `{apps: [{name, url?, confidence}], chores: [{text, confidence}]}`
- `POST /onboarding/interview` body `{answers: Answer[], round: n}` -> `{questions: [{id, slot, text, recommended, options?}], coverage: {apps, chore, hand, worth, never}, gate_open: bool}`
- `POST /onboarding/map` body `{answers}` -> `{candidates: [{playbook_id, title, fit, annual_value_usd, gates: [{action, label}]}]}`
- `POST /onboarding/sandbox` body `{playbook_id, answers}` -> `{sandbox_id, origin, url}`; `GET /sandbox/<sandbox_id>/` serves the page; `DELETE /onboarding/sandbox/<sandbox_id>`
- `POST /witness` body `{card_id, png_b64, box: [x,y,w,h], label}` -> `{iou, agree, source: "meta"|"modal"|"none", ms}`
- existing `POST /run` gains optional `surface: "rehearsal"` and `replay_after_s: 20`; run events gain `recorded: {date}` when replayed and `diverted: {from, to}` on a breaker trip.
- existing `POST /decisions/<card_id>` is unchanged (the lever).
Types: `Answer {question_id, slot, value, source: "recommended"|"edited"|"skipped"}`; `Slot = "apps"|"chore"|"hand"|"worth"|"never"`; `OnboardingStep = "key"|"look"|"interview"|"map"|"review"|"rehearse"|"signed"|"later"`; `RailBuild = "ghost"|"laid"|"beat"`; `RailSection = "yard"|"interlocking"|"line"|"timetable"|"register"|"test"`.
Persistence: daemon setting `onboarding.v1` = `{v: 1, step, answers, coverage, playbook_id?, sandbox_id?, card_id?, signed_at?}`; on finish the snapshot is reaped and the chosen chore is kept as a Project with its brief and apps. `railBuild` setting while prototyping. The key stays in `meta-key.json`, held by the daemon (ADR 0004).
Ledger: schema unchanged; `Surface` gains `onboarding` and `rehearsal`; `cost_estimated` for Meta prices.
Absent values: omit the key when unknown; `cost_usd` omitted means unpriced; witness unavailable is `source: "none"` with no `iou` key, rendered "one witness".

### UX/UI spec
- First act: Blue Hour skin; the rail (selected renderer) on the left 60%, the step plate on the right 40%; at 390 wide the step plate stacks over a compact rail strip. The intro hands over control in <= 4 s; reduced motion = no train travel, lamps switch.
- States per step: key (empty / probing / ok with latency / invalid with Meta-page remedy / network down), look (empty / consent / reading / guesses / skipped), interview (round n, open count, coverage meter; Muse slow -> "still thinking" after 3 s; error -> retry or answer without suggestions), map (candidates / no good fit -> 3 closest + catalogue), review (assembled payload; gated actions in plain words), rehearse (sandbox opening / Muse turn streaming / recorded-fallback plate / card waiting with witness lamps / diverted to Llama), signed (stamp "signed, ran once on sandbox data"; train leaves).
- Primitives from `apps/desktop/src/ui/` (the card view, the project pill); new primitives stay local until a second caller.
- Rail view: L0 six brass plates, L1 section, L2 item dossier; key plan, breadcrumb, Escape, `/` find; 12 px floor; places never move.

### Strings
Inline English per repo convention; plain words for non-developers (no "token", "OP", "manifest" on screen). No translation ritual.

### Non-goals
Hosted web onboarding; a trial relay or shipped demo key as the product path; Muse-authored worlds; the rail as home; the OS keychain; Voice/Face in the critical path; running the test run against a user's real app; an adversarial test run inside onboarding (the Test Track shows a baseline and a planned Muse re-run).

### Risks
- Meta API shape unknown (OpenAI-compatible? Llama under the same key? SAM offered?) -> WP1 day-1 probe; adapters behind the `Engine` seam and `Witness`; Baseten and Modal fallbacks named.
- A non-developer may not have a Meta developer account -> the key step's remedy copy; the demo film uses a prepared account.
- Screenshots of the sandbox page are new to the shell and may differ per OS -> where one cannot be taken, show "one witness" honestly.
- Interview latency stacks per round -> frontier batching keeps it to 2-3 rounds; "still thinking" plate at 3 s.
- Serving a sandbox page on loopback and opening it in a webview is new -> the WP2/WP3 seam is smoke-tested on the built app before ship.
- Blue Hour tokens vs the theme's CSS tests (sizes as tokens, reduced motion) -> scoped skin, tests run in WP3.
- Recording a Muse run per chore costs money and time -> record after WP1 lands; hero chore first.
