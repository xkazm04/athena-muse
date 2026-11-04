---
product: "Athena on Muse"
stack: "Python daemon (uv, Starlette, SQLite) + Tauri 2 / React / TS desktop"
vault: ["./.spark"]
vault_subdir: Spark
base_branch: main
locale_count: 1
---

## Gates
always: `node scripts/check.mjs`; `uv run ruff check src tests`; `uv run ruff format --check src tests`; `uv run mypy`; `uv run pytest -q`; `pnpm -C apps/desktop typecheck`; `pnpm -C apps/desktop lint`; `pnpm -C apps/desktop test`
when src-tauri changed: `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`
builder: the `always` set for the side it touched (Python or desktop); when a gate's output is piped (`| tail`), run it under `set -o pipefail` - a piped failure once reached a commit

## Rituals
none

## Repo law
Read AGENTS.md first. Built core: ADRs 0002-0007; built features: docs/features/ (a concept moves there once built, its design history stays in git); the stage's two views share one store and parts under apps/desktop/src/main/stage/, and each view's CSS is scoped under its own `[data-stage-view]` root. The wire contract types every response envelope, not just items (parity test). The Director commits the wire contract and compilable stubs before any parallel package. No secrets, no machine paths. Meta API facts are tagged measured / press / unverified.

A stream route's contract names its protocol, not just its event types: event order, where the stream ends, and what a follow-up call (a mark, a retry) does to it. A parallel UI built against types alone guessed it wrong (twin-module WP5: rehearsal assumed to pause per draft).

A live run that holds ports and writes for hours checks first: its ports free (a foreign process held 8791; a crashed daemon held 8795 after the disk filled) and free disk (a full disk surfaced in the app as "Her answer stopped before the end"). Seen 2026-10-29 and 2026-11-02.

A fake of an external app or page is built from a captured real answer (its tools/list, its page text), never hand-written: a stand-in fed what the real thing does not return let every test pass twice (business-phase-2: page_read with no links; app-kinds: Gravitone's top-level oneOf, which engines refuse). Seen 2026-11-01 and 2026-11-04.

Status lines in a shared design doc belong to the Director: builders put theirs in the final report, and the Director writes the line at commit. Three parallel packages writing "done" lines into one README conflicted at every rebase (twin-module).

## Wave defaults
default

## Question taste
- Concepts the owner calls consistent with earlier work: ask for the design record before wave 1 and offer it as the recommended option.
- Taste forks the owner will not settle in the abstract: build behind a switch and let them choose (blue-hour-onboarding rail build-up, "prototype all three").

- A visual the design proposes as a source of truth: offer "a sketch for understanding, the real artefact written once after agreement" as an option; the owner chose it via Other on chore-onboarding-v2.

- A first target for a new mechanism: the owner picks the real app (Gravitone) over a bundled demo, and builds the future half now (devices) rather than designing it only (app-kinds). Recommend the real target, with its setup cost named.
- Reaching another app (YouTube, mail, Gravitone): the owner wants it reached through the app's own surface (the internal browser, the peer's MCP), not a connector or wrapper, even at higher engineering cost; lead with that option (business-channel, three overrides in one direction).
- A capability the owner names that lives only in a sibling repo ("the app's connectors" = athena-portable's Gmail/Notion): ask where it lives in wave 1, and include a repo-native mechanism (chores, ADR 0005) as an option for any new tool use; the owner chose "preset chores, catalogue grows" via Other on twin-module.
- The owner leans toward full scope and real behaviour when a tested rule holds the risk: Auto in v1 over "Auto locked", any recipient over a recipients list, "Everything, in order" over a foundation-only fire (twin-module). Recommend the bolder option when its safety is a tested rule, and name that rule in the option.

## Skill improvement log
- 2026-10-26 (athena-core): the brief named list answers as `{spaces: ...}` in prose but the contract typed only the items; a parallel package guessed bare arrays and both sides' tests passed. Put every response envelope in contracts.py + contract.ts with a parity test, not in the brief's prose.
- 2026-10-26: the Bash tool mis-parses long heredocs containing apostrophes; write files with Write and keep shell scripts short.
- 2026-10-27 (chore-onboarding-v2): plan-only spark; scouting the parked plan of record first turned the supersede question into one click.
- 2026-10-28 (business-channel): athena-portable (sibling, built browser + gate + MCP client) was missed by targeting and surfaced only via the owner's doctrine; scout `../athena-*` sibling repos for prior art in Phase 2 of any spark touching hands, engines or apps.
- 2026-10-29 (onboarding-v2 build): a generated fixture in exact wire shape, produced through the daemon's own rules and used as the store's oracle, caught three contract gaps before any view was built (an extra event field, the open question not stored, the quote not kept). Generate fixtures through the real code, never by hand.
- 2026-10-29: parallel UI builders need distinct dev-server ports written into each brief, and `pnpm -C <dir> dev -- --port N` passes a literal `--` to Vite: use `pnpm -C <dir> exec vite --port N --strictPort`.
- 2026-10-29: `uv run <daemon>` starts the daemon as a child; terminating the wrapper leaves it serving its port, and a later run silently talked to the stale one. End the process tree (`taskkill /T`) and assert the engine you asked for answered.
- 2026-10-29: the live seam on the built app found the one defect no unit test could (an authored world whose last phase could not act: 1 of 5). Measure the fix live before and after; it scored 5 of 5.
- 2026-10-29 (twin-module): one Director-written verifier (Playwright on the installed Chrome, every state x 2 sizes: page scroll, 12 px floor, banned words, console errors) handed to three parallel UI builders made their "0 failures" comparable and caught a banned word in the Director's own fixture; run the banned-word check over generated fixtures at build time too.
- 2026-10-30 (twin-module build): the 2026-10-26 lesson (the contract types the shape, prose carries the rest) recurred one level up: WP5 built the rehearsal UI against event types and guessed the stream's protocol wrong; promoted to Repo law. README "done" lines from parallel builders conflicted at three rebases; promoted to Repo law. Re-running a builder's changed rule with the fix reverted (fail) and restored (pass) caught that no existing test covered the first-message rule.
- 2026-11-01 (youtube-live-e2e -> business-phases-plan): a live-run spark was asked harness questions before checking which steps of the business case are built; the owner stopped it to plan the unbuilt half. For a live/e2e spark, list built vs unbuilt per step of the case before wave 1.
- 2026-11-01 (business-phase-1): a daemon string that reaches the screen (drop reasons) is UI copy; WP1.2's brief did not say so and the banned-word rule caught it only in WP1.3. Name such strings in the producing package's brief. Also: grep a new wire name against both contract files before choosing it (VerdictBody and TS Record collided).
- 2026-11-01 (business-phase-2): a stand-in shell fed text with link addresses let every unit test pass while the real page_read returns none; the built-shell seam found it (3/9 -> 9/9). Feed stand-ins what the real hand returns, and run the built-artifact seam before merge on any routine or recipe that reads pages.
- 2026-11-02 (onboarding-engine-parity): a measuring harness's own policies (ink all, exit when agreed) hid one engine's over-proposal and skipped the persona's never answer; found only by reading the baseline transcripts. The persona's review policy is a wave-1 question, not a builder default.
- 2026-11-02: a fix in a shared base (SketchDesign) broke 41 twin tests the first cut never ran; the scout had named `twins/setup.py` as a consumer. Scope a behaviour change in a shared base with a class-level switch, and run the consumer's tests before the commit.
- 2026-11-02: when the operator names a model version and the repo's default differs (1.2 vs 1.3), ask which in plain words; recommending the operator's stale version was corrected via Other.
- 2026-11-02: blind grading (engine names stripped, key in a separate file) reversed the Director's prior (Muse expected to degrade; it was faster and level) and caught a Sonnet blocker that would have been pinned on Muse.
- 2026-11-02 (onboarding-jobs): keeping every unusable model answer on disk turned an "unreproducible" writing failure (seen twice) into a one-line parser fix on the first smoke run. Keep the raw artefact of any model failure by default; a re-run is not a diagnosis.
- 2026-11-02: drafts store each optional field in its own column; a new Draft field vanished on put until the column was added. For a new persisted field, the scout names the writer that serialises it.
- 2026-11-02: on Windows a killed daemon's port is freed a moment after taskkill returns; the parity runner lost six cases to a 1 s gap. A runner that reuses ports waits for them to free.
- 2026-11-04 (app-kinds): wave 1 recommended replacing `spaces.apps` with a table before counting its consumers (17 py + 8 ts); the Director re-cut it at build. Before recommending "replace X", the scout's consumer count goes into the option text.
- 2026-11-04: three contract gaps came back from builders, all missing lifecycle or failure verbs (no update/detach for a created resource; a call that could not tell "unreachable" from "the app said error"; a listener reply that could not stream). The contract names, for every resource it creates, its read/update/delete verbs and each call's failure split.
