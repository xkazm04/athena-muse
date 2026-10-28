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

- **Starting.** `POST /drafts {need}` checks the need (1 to `NEED_MAX` characters), creates the Project named after the need (cut to `NAME_MAX` at a word boundary), makes it active, and stores the draft at `describe`. Nothing runs yet. The first `POST /drafts/{id}/say` with empty text runs the first stage turn with the need as the person's words. Later turns take what the person typed (`text`) or the suggestion they picked (`choice`, kept as their words), one or the other. The step becomes `shape`. Once the sketch has a `need` node, the Project takes that node's label, unless the person has already renamed it.
- **A design turn** is an ordinary turn in the draft's Project with the ledger surface `design`. It offers `recall`, `sketch` and `ask` only. Its frame carries the rubric, the sketch (ids, kind, slot, label, origin, confirmed), coverage, the questions asked per slot, and three rules: at most one question per reply, 2 to 4 short suggested answers, and never claim the sketch is complete. Tool parameters are strings, so a CLI engine can call them as OP lines. `sketch` takes `op, id, kind, slot, label, detail, link_from, link_to, quote`. `ask` takes `slot, text, suggestions`, with the suggestions joined by `" | "`. Outside a design turn both do nothing.
- **Sketch ops apply at once.** Each call is checked whole: a known kind and slot, a label of 1 to `LABEL_MAX` characters, at most `SKETCH_NODES_MAX` nodes, no duplicate ids, no dangling or duplicate links, and no node linked to itself. A bad call changes nothing, and the tool result tells the model why in plain words. Applied ops stream as `sketch{ops}`, each carrying the whole node after the change. Removing a node also removes its links, and each removed link is streamed as its own op. Nodes keep their insertion order, so a place never moves.
- **Origin is computed, not claimed.** A node the model adds is Athena's proposal (`origin: "athena"`, unconfirmed). There is one exception: the call carries a `quote` of 3 or more words that appears verbatim (case-insensitive, spaces collapsed) in one of the person's own messages in the draft, meaning the need, a typed line or a picked answer. Such a node is the person's (`origin: "you"`, confirmed). The person confirms proposals with `POST /drafts/{id}/confirm`, which keeps `origin: "athena"` and sets `confirmed: true`. The model may add a `detail` to the person's node but may not reword, re-slot or remove it; rewording a confirmed proposal makes it unconfirmed again, because the person agreed to the old words. Known limit: a quote proves the person said those words, not that the label means what they meant; the stage shows the person's nodes as theirs, so a wrong one is visible and the person can say so.
- **Questions are capped.** The first `ask` in a reply streams `ask{ask}` with `follow_up` set to the questions already asked on that slot. A second `ask` in the same reply is refused. So is one past `FOLLOW_UPS_MAX` follow-ups on a slot, with "you have asked enough about <slot>; move on or let the person write it".
- **Nothing is stored until the reply counts.** A reply counts when it has words, an applied op or a kept question. Only then are the sketch, the question counts and the step stored, followed by one `coverage{coverage, agreed}` event and `done`. An engine error ends with `error`, and so does a reply with no words, no op and no question (`engine_unavailable`, "She did not answer; try again."). In both cases the draft is left exactly as it was. Any `sketch` or `ask` events already streamed in that reply are void, and the stage reads the draft again. The person's line stays in the conversation, as it does on `/run`.
- **Skipping.** "That's enough, write it" moves every slot still at 0 or 0.5 to `skipped` (`Drafts.skip_open`). A skipped slot that later gains a node is no longer skipped, and a confirmed node always counts as 1.
- **One turn at a time.** `say`, `confirm` and `DELETE` answer 409 `space_busy` while a turn runs in the draft's Project, so a confirmation can never be overwritten by a reply that started before it. `DELETE /drafts/{id}` removes the draft's row and its folder, and the Project stays. Erasing the Project erases its drafts, rows and folders alike.
- **No key means a simulated stage.** The scripted engine first draws the need in the person's first words, then proposes one node for the next empty slot on each turn and asks about it. Every line it writes is labelled "(Simulated)". With the person's confirmations, a draft reaches agreed with no model.

## Authoring and the test run

To be completed with authoring, the preview, the key and the test run.

## Consequences

- A need no library chore covers becomes a chore the person has tested against their own expectations, without a developer.
- A chore's score now depends on the key its owner gave. Two people with the same need can hold different keys, and both are right.
- `PUT` joins the daemon's allowed CORS methods for the key route.
