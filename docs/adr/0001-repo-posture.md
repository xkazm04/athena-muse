# 0001 - Repo posture: fresh repository, built from scratch

Status: accepted
Date: 2026-10-20 (proposed), 2026-10-26 (accepted at T0)

## Context

This repository was prepared before the hackathon opened: structure, standards, the design and a
reference demo, with no product code and no git history. Athena on Muse follows athena-portable,
which predates the event. The proposal left room for one disclosed import commit of its code.

## Decision

- History starts at T0 with the first commit (`chore: scaffold (prepared pre-event)`), so every
  product commit is inside the event window.
- **No import.** The owner decided at T0 to rebuild from scratch: no athena-portable code is copied
  or used as a reference. Its design documents (the Blue Hour plan, the projects decision, the Loop
  Tide theme) are the inputs, and their concepts are re-implemented here.
- The submission names athena-portable as prior art for the concepts, not for the code.

## Consequences

The submission text states plainly that the concepts are prior work and the code is new. Concepts
carried over (walled projects, the gate's single-use cards, the Loop Tide theme) are each re-decided
in their own ADR here.
