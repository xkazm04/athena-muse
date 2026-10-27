# 0005 - Chores are data, rehearsed on a bench against invented portals

Status: accepted
Date: 2026-10-27

## Context

Athena's first chores are four errands a family runs into: a parent's pile of medical mail, an
insurer's denial to appeal, a home remodel to keep honest, and a parent's care shared by the
family. Each needs Meta's senses (reading paper, hearing a call, counting what a camera saw), each
needs a believable world to act in, and each must prove it works before the app calls it featured.
Real portals and real mail are out of reach in the event window, and a chore's worth has to be
measured, not claimed.

## Decision

1. **A chore is a folder of data** under `playbooks/<id>/`: `playbook.json` (what it is, who it
   serves, its bar in `expectation`), `world.json` (invented apps, each with tools and tables, and
   the phases a person walks through), `truth.json` (the answer key: per gated tool, which keys are
   eligible and what they are worth, which are traps, and tools that must never be proposed) and
   `senses/` (the media index, recorded fixtures, the sense answer key, and the built `sensed.json`
   and `proofs.json`). Athena never sees `truth.json` or the sense answer key.
2. **A sense is a build step.** It turns the recorded media into tables whose every row cites its
   media item (and the frame, second or box when known). The loader merges those tables into the
   world, so the bench reads them through ordinary READ tools. A sensed table never shadows a world
   table.
3. **Portals are turn tools.** The turn is handed the current app's tools, named `<app>__<tool>`. A
   READ tool answers at once (`portal_read`, auto). Any other tool files a card (`portal_act`,
   gated) and, unlike the core actions, does not end the round loop, so one reply can file a pile.
4. **The bench rehearses headless.** It opens a throwaway daemon, walks the phases with the chosen
   engine (nudging "keep going" while Athena is still calling tools, up to each phase's allowance),
   approves nothing, and scores the cards against `truth.json`: found and exact, value found, false
   claims (traps, forbidden tools, keys the answer key does not name), duplicates. The verdict is
   `exceeds`, `meets` or `short` against the chore's own `expectation`. `bench.json` is the latest
   run's view.
5. **Featured is earned.** `playbook.json` `featured` names the senses and the spike; the status
   is computed from `proofs.json`: `proven` only when every proof passed with a sense role on one
   of Meta's models (`meta` for the API, `muse_code` for Muse Code on the plan), `rehearsed` when
   they passed on fixtures, `failing`, or `unproven`.
6. **Engines are chosen per run.** `ATHENA_ENGINE` picks `muse` (the API, the submission's engine),
   `muse_code` (Muse Code on the plan, the pre-submission check), `claude_code` (development) or
   `scripted`. A Muse Code run sends Contributor mode off, every time.

## Consequences

- A chore runs end to end with no key: fixtures for the senses, Claude Code or the scripted engine
  for Athena. The switch to Muse is an engine flag and a sense flag, not a rewrite.
- A number on a chore always names the engine and model that produced it.
- Running a chore live inside a Project, with Athena in her window, is the next slice; this one is
  the bench and the Chores scene.

## Amendment 2026-10-27 - what a page answered reaches the next turn

A turn's history keeps Athena's words, not what her tools answered. On care-circle she read the
bottles' med ids and the members' ids in the Circle app, reached the pharmacy and the clinic two
phases later without them, and refused to guess: 0 of 6 found, every card missing its key. So
every portal READ answer is kept per space (`page_reads`, erased with the project) and a portal
turn's frame lists the newest one per tool and arguments, within a 16,000-character budget, still
fenced as page data. Beside it, the frame lists the space's unsigned portal cards so a nudge does
not file one twice.
