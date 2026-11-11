# 0028 - A quote proves only the words it holds, and a picked answer is agreement, not the person's words

Status: accepted; narrows the "origin is computed, not claimed" bullet of [ADR 0007](0007-a-chore-is-written-in-conversation-and-tested-against-the-users-expectations.md) (and [ADR 0010](0010-one-shaping-conversation-two-rubrics.md), which shares it)
Date: 2026-11-11

## Context

ADR 0007 made a sketch node the person's (`origin: "you"`, confirmed) when the model's `sketch` call carried a quote of 3 or more words found verbatim in the person's messages. A read-only review (personas defects, operator verdict 2026-11-11) found four ways that rule let her words pass as theirs:

- The quote inked the whole node. Her own label, detail, kind and slot rode in under any true quote: `label: "Pay every invoice"` with `quote: "the school portal has"` was drawn as the person's, confirmed.
- A later `detail` rewrite on the person's node was allowed and the node stayed theirs and confirmed.
- `sketch.apply` took `origin` and `confirmed` from whatever node its caller passed, so the rule lived in one caller and every other caller could claim ink.
- "The person's messages" included an answer they picked from her suggestions. That text is hers: she wrote the option, the person agreed to it.

ADR 0007 called this a known limit ("a quote proves the person said those words, not that the label means what they meant"). The stage draws the person's nodes as theirs and counts them toward coverage, so the limit decided what a chore was agreed on.

## Decision

1. **The sketch decides whose a node is, never its caller.** `sketch.apply` ignores `origin`, `confirmed` and `quote` on an added node. A new node is her proposal unless the quote proves it. The person's own acts (a twin's slips, a connected account) still ink the nodes they own after the sketch applies them, as `sync` already did.
2. **A quote proves only the words it holds.** A node is drawn from a quote when its label, and its detail if it has one, each run word for word inside the quote (case and punctuation ignored, words in order). Kind and slot say where a node goes; they are never anyone's words. A true quote under her own label or detail leaves the node her proposal, and her tool result tells her why.
3. **Typed words are the person's; a picked answer is their agreement.** A person's turn is kept as `picked` when it came from her suggestions (`say` with `choice`). A node whose words come from a typed line or the need is the person's (`origin: "you"`, confirmed, `quote` kept). A node whose words come only from a picked answer is hers and confirmed (`origin: "athena"`, `confirmed: true`, no quote): the person agreed to those exact words. If the person also typed them, they are theirs.
4. **Rewriting a node's words takes back what was agreed.** `detail` joins label, kind and slot. On the person's node it is refused (ask them first); on her confirmed node it makes the node unconfirmed again.
5. **A setting still takes a picked answer.** A twin's dial and the gate on a voice piece ask whether the person said so, typed or picked; whose words a node holds is decided by point 2 and 3 alone.

## Consequences

- Coverage counts confirmed nodes, as before, so a picked answer drawn in its own words still fills its place at once. A paraphrase of the person's words now arrives in pencil and the person inks it; models are told in the tool description that the label and detail must be in the quoted words.
- The staged stage fixture follows the rule: its model labels are the person's words where the fixture inks them, and the paraphrases it kept are inked by the person (`confirm`) in the frame that already confirms. `scripts/stage_fixture.py` refuses a source node that claims ink the daemon would not draw. The scripted twin's purpose quotes the whole need; its "Signs as ..." piece, written from a picked answer, is pencil until inked.
- `turns.picked` is a new column. Turns stored before it read as typed, so a pick from before this change still counts as the person's words.
- Matching is by words, not characters: a quote that cuts a word in half no longer matches.
