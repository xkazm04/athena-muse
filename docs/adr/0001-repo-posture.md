# 0001 - Repo posture: fresh repository, built from scratch

Status: accepted
Date: 2026-10-20 (proposed), 2026-10-26 (accepted at T0)
Amended 2026-10-27: the decision stands on its own; no other codebase is named as a reference.

## Context

This repository was prepared before the hackathon opened: structure, standards, the design and a
reference demo, with no product code and no git history. The product code had to be written inside
the event window.

## Decision

- History starts at T0 with the first commit (`chore: scaffold (prepared pre-event)`), so every
  product commit is inside the event window.
- **Written from scratch.** All product code is new, written in the event window. The design
  documents prepared before the event (the Blue Hour plan, the reference demo) are inputs, and each
  concept they carry is decided here in its own ADR.

## Consequences

The submission states plainly that the code is new, written in the event window. Each concept the
product relies on (walled projects, the gate's single-use cards, the Loop Tide theme) is decided in
its own ADR here.
