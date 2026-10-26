# 0003 - Projects are walled spaces

Status: accepted
Date: 2026-10-26

## Context

A person uses Athena for several pieces of work at once (taxes, a garden, a job hunt). If she has
one memory, every turn gets all of them back: a tax fact surfaces on a garden question. The
concept of walled projects comes from athena-portable (its ADR 0225) and is re-implemented here
from scratch.

## Decision

- **Vocabulary.** The person's word is **Project**; the wire's and the code's is **space**
  (`spc_` + 12 hex). The word is kept even though this repo has no clash yet, so a later Chores
  port keeps athena-portable's meaning of `proj_` (a chore's case). **Core** is no space: its one
  spelling is `""` on the wire and in storage, `core` only as a path segment.
- **A project** holds a name (1-60), a brief (at most 1,600), apps (at most 24 distinct origins,
  each normalised to `scheme://host[:port]`) and a hue. At most 100 projects. Caps are refused
  with `bad_request` naming the cap, never cut.
- **The wall.** Every memory is stamped at write with the space of the turn that wrote it. Recall
  sees `visible_spaces(active)`: core sees core; a project sees core and itself. Moving a fact to
  core is an explicit act (`make core`), never a query that happens to span two projects. A stamp
  or setting naming a space that no longer exists fails closed to core.
- **The turn frame.** In a project, every turn is told the project's name, brief, apps and the
  facts kept there. Core turns get none of it.
- **Erase** deletes the project's memory, conversation and cards and then the project; it is
  refused (409 `space_busy`) while a turn runs there, and no turn starts in a project being
  erased. The desktop asks twice and states what will go.
- **The active project** lives in the daemon (`settings.active_space_id`) so both windows agree; a
  switch is refused while a turn runs and the windows hold it until the reply ends.
- **A project never changes what Athena may do.** The action catalog and its classes are the same
  in every project; a project changes what she remembers and is told.

## Consequences

Memory written in core is visible everywhere; nothing written in a project leaks out of it unless
the person moves it. Erase is irreversible. Projects are local to one PC.
