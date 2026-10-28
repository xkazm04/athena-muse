# 0007 - A chore is written in conversation and tested against the user's own expectations

Status: accepted
Date: 2026-10-28

## Context

The four chores in `playbooks/` were written by hand ([ADR 0005](0005-chores-are-data-rehearsed-on-a-bench.md)). A person with a need none of them covers had no way in. [Chore onboarding v2](../concepts/chore-onboarding-v2/README.md) designs the way in: the person describes the need in the main window, Athena asks one question at a time while a sketch of the process draws itself, then writes a real chore, previews the cards she expects to file, and runs a test that the person judges. Two things must not happen. A model must not decide that the conversation is complete, and Athena must not write her own answer key.

## Decision

1. **A draft is a Project from its first frame.** `POST /drafts` creates the Project and the draft, and makes the Project active. Every stage reply is an ordinary turn in that Project's conversation (surface `design`), so her small window shows the history with no new code. A draft walks `describe -> shape -> author -> preview -> rehearse -> verdict -> saved`. `shape` is re-entered from `author` (a failure that cannot be repaired), from `preview` and from a `revise` verdict.
2. **The sketch is the person's picture of the process, not the chore's source.** Shaping changes only the sketch, through two AUTO actions, `sketch` and `ask`, which are offered only on a design turn. Called anywhere else they do nothing. Athena writes the chore files in one step after the sketch is agreed.
3. **The flow owns completion.** The seven slots are `need`, `apps`, `inputs`, `steps`, `hand`, `output` and `never`. Coverage is computed from the sketch: 1 when a slot holds a confirmed node, 0.5 when it holds only Athena's proposals, 0 when empty, or `skipped` with a stated default. The draft is agreed when `need`, `apps`, `hand` and `output` are at 1 and the rest are at least 0.5 or skipped. A slot gets at most `FOLLOW_UPS_MAX` follow-up questions, and "That's enough, write it" is offered at any coverage.
4. **The person's marks are the answer key.** The preview lists the cards Athena expects to file. The person's `yes` makes a card eligible, `no` makes it a trap, and a "she must never..." line makes it forbidden. A card the person says she missed is placed on a practice-app tool and key when Athena can; one she cannot place is kept and shown, not scored. `truth.json` is written from the key alone.
5. **The test run is the bench, in process.** The bench runner plays the written chore's phases on a throwaway daemon, streams phases and cards, writes ledger rows with surface `rehearsal`, approves nothing, and is never retried automatically.
6. **Personal chores never reach the repository.** Drafts live in `<data_dir>/drafts/<draft_id>/`. A kept chore moves to `<data_dir>/chores/<chore_id>/` and is listed beside the library with `origin: "yours"`. Erasing a Project erases its draft.

The wire contract (`contracts.py` and `contract.ts`, held equal by the parity test) names every draft route, type, stream event and cap.

## Shaping

To be completed with the drafts and stage turns.

## Authoring and the test run

To be completed with authoring, the preview, the key and the test run.

## Consequences

- A need no library chore covers becomes a chore the person has tested against their own expectations, without a developer.
- A chore's score now depends on the key its owner gave. Two people with the same need can hold different keys, and both are right.
- `PUT` joins the daemon's allowed CORS methods for the key route.
