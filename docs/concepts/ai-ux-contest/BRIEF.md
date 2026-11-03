# Contest brief - how Athena looks when she takes the screen

Input for `/contest` (copy this file as the contest's `BRIEF.md`). It frames one blind design
contest; it does not choose a direction. The standard every entry is judged against is the
registry's AI-driven experience golden path - `model-composed-workspace` (inside the app) and
`agent-host-experience` (inside other assistants) in `ai-registry`, subcategory
`llm-agent/experience`.

## 1. The idea

Athena is a private desktop companion: a person talks to her, and she does the heavy lifting
across their projects - remembering, reading their apps and pages, drawing a chore as she
learns it, composing a project's report from its records - and asks for a signature before
anything changes. The contest asks what her experience looks like at its best: the
conversation and the screen she conducts, as one thing, for a person who is not a developer.

## 2. The material (real, at real scale)

- **Two windows.** A main window (1280 x 800) with the projects, their reports, chores,
  twins, devices and settings; and *her* window (400 x 620, always on top, transparent) where
  the conversation lives. Both stay in step over one event stream.
- **A turn streams** as ordered parts: her words (a safe markdown subset - paragraphs, bold,
  italic, inline code, code blocks, lists, links shown but not clickable), short tool lines
  ("Looked through memory"), cards that need a signature, and up to three report blocks bound
  to the project's records; it ends with an estimated cost ("est. $0.0042"). Turns run from
  one second to several minutes; a long one is mostly silent tool work.
- **The block kit** is closed: eight kinds (stat, trend, queue, pipeline, list, thread, cards,
  callout) on a twelve-column grid, at most twelve blocks per report, pins that survive every
  recomposition. Every number is computed from records; the model never writes one, and a
  digit in a title is refused.
- **Her seal** has four states: rest, working, waiting (a card needs the person), signed.
- **The sketch stage** draws a chore live while she asks questions: nodes of six kinds in
  seven slots, added, changed, removed and linked as the conversation goes.
- **Her report also renders inside other assistants** as a small read-only view (at most two
  actions, about five figures per block, no nested scroll), with a full text fallback.
- Use the fixtures staged under `data/` (a project with records and a report, a conversation
  with every part kind, a chore mid-sketch, a card waiting for a signature). Nothing outside
  them is real.

## 3. The wow, and what must never break

In the first three seconds a stranger should feel that she is *working for them* and that the
screen is *calmer because of it*, not busier. What must never break: the person can always
tell what she did, what she is doing, and what is waiting for their signature; nothing that
changes their world happens without the card; and the screen they arranged stays where they
put it.

## 4. Freedoms

Everything visual and spatial: layout of both windows, how the conversation and the screen
relate, typography, palette (the current "Loop Tide" tokens are a starting point, not a
requirement), motion, how her presence reads, how a composed view arrives. Any framework or
none.

## 5. Hard constraints

- Opens from disk, offline, no build step required to view.
- Honesty: fixtures say they are fixtures; costs are estimates and say "est."; a simulated
  engine is labelled on screen; designed imagery is labelled as stylised.
- Calm and reduced motion are honoured: every motion has a still form that carries the same
  content.
- Text never placed in a way a person cannot select and read; every action reachable by
  keyboard.
