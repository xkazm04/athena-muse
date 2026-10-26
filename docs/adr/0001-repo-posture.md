# 0001 - Repo posture: fresh repository, prior art disclosed

Status: proposed (confirm against the hackathon rules at T0)
Date: 2026-10-20

## Context

This repository is prepared before the hackathon opens: structure, standards, the design and a reference demo, with no product code and no git history. Athena on Muse builds on athena-portable, which predates the event.

## Decision

- History starts at T0 with the first commit, so every product commit is inside the event window.
- Product code is written in this repository during the event. Anything carried over from athena-portable is imported at T0 as one named commit ("import: athena-portable at <sha>") and listed in `docs/hackathon/submission-checklist.md` as prior work.
- If the rules forbid carried-over code, the import commit is dropped and the packages rebuild what they need; the wire contract in the plan does not change.

## Consequences

The submission text states plainly what is prior art and what is new. The T0 runbook owns the order of operations.
