# 0009 - One send rule for every twin draft

Status: accepted
Date: 2026-10-29

## Context

A twin drafts messages and, once live, may send them without the person ([ADR 0008](0008-twins-speak-through-connected-accounts.md)). v1 sends real email to any recipient. The owner chose to have all three levels live in v1: Review, Assist and Auto.

The standard read (registry `speed-to-lead-and-assisted-reply` and `risks-gate-not-confidence`) gives three autonomy levels per channel, with Assist as the default. A draft sends alone only when four things hold: the channel is enabled, the channel is on Auto, the draft is at least as sure as the channel's bar, and its risk list is empty. One gate function decides this, and a disabled channel never sends.

The scout (2026-10-29) found what exists to build on. In personas, approving a reply only logs it, and nothing is really sent. In this repository, the gate files a card and resolves it exactly once, and `CardView` has no editable text.

A draft's confidence is the model's own estimate, so it cannot be the only thing that lets a draft out.

## Decision

1. **One pure function decides.** `athena.twins.decide.decide(channel, draft, *, twin_live) -> Ruling(decision, reason)`. It reads the channel (`TwinChannel`), the draft's facts (the kind of message, its confidence and its risk list) and whether the twin is live. It has no clock, no store and no I/O.
2. **A draft is sent alone only when all of these hold:**
   - the channel is connected and the twin is live;
   - the level is `auto`, where the level is the channel's `split` level for this kind of message (`first_message` or `reply`) when it has a split, else its `autonomy`;
   - `confidence >= bar`;
   - `risks` is empty.
3. **Everything else waits, with one reason.** The reason is the first of these that holds:
   - `paused`: the twin is not live or the channel is not connected;
   - the level: `first_message` when a split channel holds first messages below Auto, else `review` or `assist`;
   - `risk`: the risk list is not empty;
   - `below_bar`: the draft is less sure than the bar.

   A paused twin or channel never sends.
4. **The bar and the list.** The bar is whole percent, `BAR_MIN` to `BAR_MAX`, `BAR_DEFAULT` unless set. It is kept on every level and only matters where a level is Auto. A risk list holds at most `RISKS_MAX` lines in plain words.
5. **One path.** The interactive path, the poller and the dress rehearsal all call `decide`, and nothing else sends. In the rehearsal the ruling is shown and played on the practice page, never sent to a person.
6. **A waiting draft is a signature card whose text the person may edit.** The card's action is `twin_send` (one Gmail message, in-thread when replying) or `twin_note` (one Notion append or create), both gated. `POST /decisions/{card_id} {verdict, edited?: {text}}` signs it, with the person's words when they changed it. The executor runs off the event loop. A failed executor returns the card to `waiting` with a problem line, so it never sends twice and never silently drops.
7. **Every send leaves a trace.** A draft sent alone writes a ledger row (surface `twin`) and a mission turn that carries its confidence, its risk list, the bar it met and the decision. A held draft shows how sure it was against the bar, plus its risk list.

## Consequences

- Real sends hang on one small function, so it gets a table test over every level, split, bar edge and risk case (WP4).
- The person can always see why a draft waited: the reason is on the wire, not in prose.
- Auto with an empty risk list is the only way out alone. A confident draft that touches a restriction still waits.
- The gate gains edited text, and `CardView` gains an editable body for twin cards. Other cards are unchanged.
