# 0018 - Projects keep records, and her report is composed from a closed kit

Status: accepted
Date: 2026-11-01

## Context

The business channel ([concept](../concepts/business-channel/README.md)) needs typed state for each project: creators, tracks, agreements, files, renders, releases and stats. It also needs a front page that shows where the business stands. Before this ADR a project held a name, brief, apps and sites, and nothing it could count ([ADR 0003](0003-projects-are-walled-spaces.md)). The design of record (2026-10-28) chose records and a composed report. The plan of record (2026-11-01) settled the open forks with the owner.

## Decision

- **Records are one append-only table.** A change is a new revision of the same `(space, kind, key)`, and an unchanged body appends nothing.
- **Kinds are a catalog in code**, not declared per project.
  - Each kind is a body validator, a key rule and a description.
  - A project lists the kinds it keeps (`spaces.kinds`). The stage's business branch (Phase 4) picks them from the catalog.
  - v1 has the music channel's eight kinds.
  - Rejected: per-project field schemas, and a mix of both.
- **The class is the floor for `record_put`.**
  - Athena keeps finds (creator, track) at once.
  - Any other kind files a card, and the signed card writes it.
  - `record_list` is fenced as data, not instructions.
- **The rights rule is a function.** `may_render` answers whether a track may become a video and, in plain words, what is missing: kept, an agreement that is agreed with a thread as evidence, a known plan tier that is not free, and a file present.
- **The report is composed from a closed kit of eight blocks.**
  - The block registry is the one authority. The composer's instructions are generated from it and from the kind catalog.
  - One validation door checks a spec when it is composed and again when it is shown. It keeps what survives and says why each block was dropped.
- **The model never writes a number.**
  - Every figure is computed from records.
  - A digit in a model-written title or callout is refused.
- **When a spec is composed and stored:**
  - A failed composition keeps the last good spec.
  - Before the first composition, the project gets a fixed default layout.
  - Pins live apart from the spec. They reach the composer as constraints, and a pinned block comes back by id.
- **When the report is recomposed:**
  - On request.
  - When a kept kind goes from none to some or from some to none, at most once an hour.
  - A verdict alone never recomposes.
- **Only projects that keep records show a report.** Every other project's front page is unchanged.
- **The ledger answers per project** (`GET /ledger?space=`), so a report can show what the business costs to run.

## Consequences

- **What it costs:** a new kind of business adds kinds in code, with tests. The vocabulary version (`VOCAB`) and the generated composer instructions move with the catalog.
- **What builds on it:** Phase 2's routines write records through the same door (watch, inbox, stats), and Phase 3's render reads `may_render` before it calls Gravitone.
- **Known gaps:**
  - The drop reasons from a composition are returned but not stored, so a later read shows only the drops found at render time.
  - The simulated engine cannot compose a report; the default layout stands in.
  - `RecordPutBody` has no `key` for a thread, which the action carries in its arguments; add the field when a put route lands.
