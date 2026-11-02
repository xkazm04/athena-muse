# Chore onboarding - describe a need, watch it drawn, test it, keep it

Built 2026-10-29. Decisions: [ADR 0007](../adr/0007-a-chore-is-written-in-conversation-and-tested-against-the-users-expectations.md) (and its amendment: `drop`, two views, comparison counts); the access step and a project's sites: [ADR 0014](../adr/0014-a-chores-onboarding-signs-in-to-its-real-sites-and-only-onboarding-grants-trust.md). Design history: `docs/concepts/chore-onboarding-v2/` in git history before the commit that added this page.

## What it does

A person opens the stage, says in their own words what they want handed off, and answers a few of
Athena's questions while a sketch of the process (apps, steps, what waits for their signature, what
they get) draws itself in the main window. Once the sketch is agreed, Athena writes a real chore with
invented practice apps, previews the cards she expects to file, and the person's yes and no answers
become the chore's answer key. A live test run on the practice apps is scored against that key; the
person accepts it, signs in to each real site the chore needs in her browser (so next time she gets
in on her own), and the chore is saved as theirs, with a Project ready to use. "Not quite" returns to
the sketch with the gaps named.

Doors: the first run's `ready` step, and "Describe a need" on Projects and on Chores. The main window
shows one frame at a time with no page scroll; the history lives in her small window, because a draft
is a Project and every stage reply is an ordinary turn in it.

## How it works

**Flow** (`DraftStep`, owned by the flow, not the model): `describe -> shape -> author -> preview -> rehearse -> verdict -> access -> saved`. `shape` is re-entered from `author` (unrepairable), `preview` and `verdict` ("not quite").

| Step | What happens | Done when |
|---|---|---|
| describe | The person types the need; Athena proposes a project name. | The first stage turn returns. |
| shape | Frames: her line + sketch ops + at most one `ask`; one line per frame (only the first model round with words is shown and kept, and the turn ends once her question is asked). | Coverage gate, or "That's enough, write it". |
| author | Athena writes `playbook.json` and `world.json` from the sketch, using the nearest library chore as an example; `load_chore` validates, up to 2 repairs. | The validator. |
| preview | One call lists the cards she would file (`ExpectedCard`); the person marks each yes/no and may add "she must never" lines. | Every card marked. |
| rehearse | `truth.json` is written from the marks; the bench runner plays the phases on a throwaway daemon and scores against the key. | The run ends. |
| verdict | Score in plain words, her cards beside the marks. "This is it" or "Not quite". | The person. |
| access | At the keep the chore is copied to `<data_dir>/chores/<id>/` and the Project's brief is set; each real site the person confirmed on the sketch becomes one of the Project's sites (the only way her browser comes to trust one). Per site: "Sign in" opens it in her browser and hands the person the wheel; when the page moves on, and every 4 s while the person signs in (or on "I have signed in"), she looks; a look that ends on another site that is not a sign-in offers "Use X instead"; "Skip for now" keeps it as signed out, a blocker on the overview. Skipped when the chore needs no real site. | Every site signed in or skipped, and every signed-in site still signed in on one last look. |
| saved | The hand-off card: the Project with the chore in it. | - |

**Rubric** (seven slots: `need`, `apps`, `inputs`, `steps`, `hand`, `output`, `never`). Coverage per
slot is 0 / 0.5 / 1, computed from the sketch, never claimed by the model: 1 holds a node the person
confirmed, 0.5 only Athena's proposals. Agreed when `need`, `apps`, `hand`, `output` are 1 and the rest
0.5 or skipped with a stated default. At most 2 follow-ups per slot; the exit is visible from frame one. Her new guesses (pieces not in the person's words) are capped at 2 per reply; a third is refused in plain words and she asks instead (`PROPOSALS_MAX`, the chore's design only; a twin's is not capped).
Since [ADR 0010](../adr/0010-one-shaping-conversation-two-rubrics.md) this is `CHORE_RUBRIC`, one of two rubrics on the same drafts machinery.

**Real sites** ([ADR 0014](../adr/0014-a-chores-onboarding-signs-in-to-its-real-sites-and-only-onboarding-grants-trust.md)). An `app` node may carry a real website (`site`): Athena proposes it in pencil with the `sketch` tool, even on the person's own node; inking the node inks the site, rubbing out an agreed node's site removes only the site. Her practice apps stay invented and never reach access. The look that says "signed in" opens the site's address in a hidden tab and reads where it ended and whether a password field shows; the step never asks for or keeps a password. After onboarding, the Project's overview shows a lapsed site as a blocker with "Sign in again".

**The key.** yes -> eligible, no -> trap, a never line -> forbidden. Athena never writes her own key.
A no is also told to her: putting the key ends each acting phase's message in `world.json` (the last
phase when none can act) with one plain block, each no card's label and the person's note or the
card's why, replaced on every re-put, so the test run and the kept chore know what the person turned down.
The sketch is an abstraction for the person's understanding, not the chore's source; the preview runs
on the written files, so what the person confirms is the real chore.

**Two views behind one switch.** The contest verdict (2026-10-28) kept both winners: **Drawing**
(lanes, a never-fence, the question pinned as a note) and **Orbit** (the question card at the centre,
six zones, coverage arcs). One store and one set of shared parts under `apps/desktop/src/main/stage/`,
each view's CSS scoped under its own `[data-stage-view]` root. The choice is kept per device
(`athena.stage.view`, default Drawing); `Draft.views` counts turns per view as the evidence for which
proves better. Pencil (dashed violet) is her guess, ink is agreed, a pink edge is the person's words.

**Wire** (`src/athena/contracts.py` / `apps/desktop/src/lib/contract.ts`): `POST /drafts {need}`,
`GET /drafts/{id}`, `POST /drafts/{id}/say` (NDJSON `TurnEvent` + `sketch` / `ask` / `coverage`),
`/confirm`, `/drop`, `/write` (`AuthorEvent`), `/preview`, `PUT /drafts/{id}/key`, `/rehearse`
(`RehearsalEvent`), `/verdict`, `/access` (`AccessBody`: `sign_in`, `check`, `skip`), `DELETE /drafts/{id}`; a
Project's sites at `GET /spaces/{id}/sites`, `POST /spaces/{id}/sites/check` and `/sites/sign_in`, with
the `site` app event. Table `drafts`, erased with its space. `Surface`
gains `design` and `rehearsal`; `ActionName` gains `sketch` and `ask` (auto). User chores carry
`origin: "yours"` and never reach `playbooks/`.

**Authoring rule found live.** A world must read first and act last; a world whose last phase cannot
act goes back for repair (the first live run scored 1 of 5 without it, 5 of 5 with it).

## Measured

On the built app against a real daemon, Claude Code (Sonnet), the staged need from describe to keep
(`scripts/stage_seam.py`, one run each, est. cost from the ledger):

| view | turns to agreed | expected cards | test run | cost |
|---|---|---|---|---|
| Drawing (before the phase fix) | 6 | 5 | `short`, 1 of 5 | $0.80 est. |
| Orbit | 5 | 5 | `exceeds`, 5 of 5 | $0.48 est. |
| Drawing (after the phase fix) | 6 | 5 | `exceeds`, 5 of 5 | $0.51 est. |

Every run: no page scroll, no console error, her window showed the draft's history, the kept chore
listed as `yours`. Fidelity against both winners' captured contracts: 0 deviations (Drawing 11 roles,
Orbit 9). On the scripted engine the stage walks to agreed and then says plainly that a simulated
Athena cannot write a chore.

**Engine parity, 2026-11-02** (`scripts/parity/`, Drawing view, a Claude Haiku persona answering,
10 use cases per engine: staged need, a new domain, a vague need, an over-specified need, own words,
early exit, a correction, "Not quite", "no" marks and a never line, a real site plus an injected
engine failure). Claude Code on Sonnet against Muse Code on muse-spark-1.3, one run each. Grades
are the Director's, given blind (engine names removed from the transcripts), the mean of five 1-5
scores: question logic, no repeats, clarity, progress, fidelity to the persona's truth.

| run | engine | mean grade | end state reached | cases on the bar | call p50 / slowest |
|---|---|---|---|---|---|
| baseline | Sonnet | 3.64 | 9 of 10 (writing failed 3 times, case 6) | 7 | ~6.7 s / 68 s |
| baseline | Muse 1.3 | 3.34 | 9 of 10 (second preview named no card, case 8) | 5 | ~4.7 s / 18 s |
| after the guess cap and the "no" marks | Sonnet | 3.20 | 10 of 10 | 7 | ~6.0 s / 86 s |
| after the guess cap and the "no" marks | Muse 1.3 | 3.24 | 10 of 10 | 7 | ~5.4 s / 20 s |

The second run's persona is stricter (it reviews each pencil mark and answers an open question
before leaving), so its grades are not directly comparable with the baseline's; the end states,
the case-level scores (case 2 on Muse 0 of 1 -> 8 of 8, case 5 short -> exceeds on both) and the
bar are. Muse reaches parity with Sonnet on this suite and is faster; Muse Code sends about 5x the
input tokens (its own instructions). The bar: the expected end state with no blocker, grade within 1
of Sonnet's, turns to agreed within Sonnet + 2, test run at least 4 of 5, no call over 60 s
(Sonnet's slow writing calls fail it in three cases).

## Run it

```bash
ATHENA_ENGINE=claude_code pnpm -C apps/desktop app   # then "Describe a need"
SEAM_PORT=8767 python scripts/stage_seam.py drawing claude_code runs/seam-drawing   # the live seam; or orbit / scripted
uv run python scripts/access_seam.py   # the access step and the overview's blocker on the built shell, simulated sites
python scripts/parity/run.py --engines claude_code,muse_code --cases 1-10 --model muse_code=muse-spark-1.3 --out runs/parity/<stamp>   # then grade blind, then scripts/parity/report.py
```

## Known gaps (none blocks use)

- She proposes again what the person rubbed out (both engines, parity run 2): the frame shows the sketch but not what was rubbed out.
- A reply may ask in words without the question card (seen once), so the person has nothing to pick.
- The verdict reads "She found everything you expected" on a 0 of 0 run, when the person said no to every card.
- "Ink them all" skips a pencil website on an inked piece, and "Rub out" on that website does nothing (`drop` accepts pencil pieces only); inking the piece in its card works.
- Orbit at 1024x700: a long "she must never" line wraps into a narrow column beside its badge.
- The verdict's reason line repeats the bench's wording ("found 1 of 5 items, expected 80%") beside a green dot that reads as success.
- The undo toast is drawn by the shell, so neither view can skin it.
- Two `data-role="note"` meanings (Drawing's pinned question, the check card's why-not field): rename the latter to `mark-note`.
- The preview harness's `.pv h2` style leaks into stage headings there (harness only).
- Not ported from the winners: the typewriter on her line, the echo flying to its piece, the fade of a rubbed-out piece, and "Stop" on a slow reply (the daemon has no cancel route).
- `Draft.views` counts exist but no screen compares them across kept chores yet.
- Not in v1: senses in authored chores, running against the person's real apps, voice.

## Later, on the Muse API

- **Describe with media:** a photo of the paper pile, a screenshot of the app, or a voice note pre-fills `apps`, `inputs` and `need` (Blue Hour's `look` step, reborn).
- **Senses in authored chores:** the person's own sample (a scanned letter, a recorded call, a walk-through video) becomes the chore's sense fixtures, so the test run reads what they actually have.
- **Witnesses:** a screenshot of the practice app on each card, and SAM where offered.
- **Voice on the stage:** Athena speaks her line and the person answers by voice; her window stays the record.
- **Engine swap:** `ATHENA_ENGINE=muse`. The stage, drafts and rehearsal are engine-agnostic by construction (ADR 0006).

## Owner's calls still open

- The view names (Drawing, Orbit) and the default view.
- Whether the per-view counts are enough evidence, or a short note after each kept chore should join them.
- The staged need stays the after-school club's invoice unless swapped for one of the owner's own.
