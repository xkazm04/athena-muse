# 0010 - One shaping conversation, two rubrics

Status: accepted
Date: 2026-10-29

## Context

A twin is set up in conversation with Athena: one question at a time, her proposals in pencil, the person's words in ink, and a document that fills in without moving what is already placed ([Twin module](../concepts/twin-module/README.md), Passport). That is the conversation [ADR 0007](0007-a-chore-is-written-in-conversation-and-tested-against-the-users-expectations.md) built for chores, and its rules took a design contest and a build to settle:
- the flow computes coverage and the model never claims it;
- origin is proved by a verbatim quote;
- one question per reply, with capped follow-ups;
- nothing is stored until a reply counts;
- the person can confirm and erase.

The scout (2026-10-29) found the parts. The bottom panel already exists in `stage/parts`: her line, the question, suggestions, the composer, thinking, slow and failed, and the "enough" exit. But `StillNeeds` and `EnoughButton` are typed to the chore's coverage, and the drafts code hardcodes the seven chore slots.

Copying the machinery for twins would fork those rules.

## Decision

1. **The drafts machinery carries a rubric.** A rubric holds:
   - its places, in order;
   - the coverage each place requires (1, 0.5 or 0);
   - each place's meaning in plain words, for her frame and the screen;
   - the kinds a part may be;
   - the rule for when the conversation is done.

   Chore drafts and twin setup are two rubrics on the same code. The shaping rules of ADR 0007 hold for both, unchanged.
2. **The twin rubric.**
   - Its places are `who`, `channels`, `voice`, `knowledge`, `chores`, `never`, `autonomy`, `memory` and `mission`.
   - The required coverage is 1 for who, channels, voice, never and autonomy; 0.5 for knowledge and chores; and 0 for memory and mission.
   - A place's coverage is computed from its pieces, as a slot's is from its nodes.
   - `ready` holds when every place is at its required coverage or above; then "That's enough, rehearse it" is offered.
   - `readiness` is the mean coverage over the places with a requirement, as a whole percent.
3. **Pieces are the twin's nodes.** A `Piece` carries a `place` where a node carries a `slot`. A piece has no links and keeps its `evidence`: the ids of the samples it was learned from. A style dial changes through the same op stream (`dial`, carrying the whole dial after the change).
4. **The twin's lines on the wire.** The setup stream (`POST /twins/{id}/say`) is a turn stream. It carries the twin's own `sketch{ops}`, `ask{ask}` and `coverage{coverage, ready, readiness}` lines, with the same names as a draft's stage turn and twin payloads. They form a separate union, `TwinSetupEvent`, so the chore's types stay as they are. A twin's question also names the working slip it needs (`panel`).
5. **Ledger surfaces.** Chore drafts' turns are design turns (surface `design`). Every call a twin causes writes surface `twin`: its setup turns, its panels' calls, its drafts on missions and the dress rehearsal (amended 2026-10-30 when WP3 built it, so a twin's whole cost is one surface).
6. **The screen shares its parts.** Athena's bottom panel for a twin is built from `stage/parts`. `StillNeeds` and `EnoughButton` work on a generic coverage.

## Consequences

- A fix to shaping fixes both conversations. Every drafts and stage test must keep its meaning when the rubric is lifted out (WP1), and a toy second rubric must run a scripted turn.
- A third conversation, such as a twin's standing rules, is a rubric and a design, not a new machine.
- The scripted engine plays a twin's setup with no key, labelled simulated, as it plays a chore's.
