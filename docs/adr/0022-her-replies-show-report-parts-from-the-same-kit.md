# 0022 - Her replies show report parts from the same kit

Status: accepted
Date: 2026-11-03

## Context

A project that keeps records has a report composed from a closed kit of blocks ([ADR 0018](0018-projects-keep-records-and-her-report-is-composed-from-a-closed-kit.md)). The kit renders only on the project page. In her window, a question like "how are the tracks doing?" got prose: the model read `record_list` and counted in words, which is the very thing ADR 0018 forbids on the report. The registry's answer-form routing puts comparative and quantitative answers in a structured form and facts, how-tos and single numbers in prose. A2 of the AI-UX plumbing (2026-11-03) asked for the kit in the chat.

## Decision

- **One chat tool, `show_blocks`.** It shows 1 to 3 parts (`CHAT_BLOCKS_MAX`) of the report's own kit inside the reply. It is a catalog action (`auto`). It reads and changes nothing (`WRITES` is false), and it never files a card.
- **The same kit, binding and door.** A part is bound to records exactly as a report block is. Each part passes the report's validation door (`report.validate.check`) on its own. A part the door refuses is dropped with its plain reason, and a digit in a title or label is refused. Every figure is computed by `report.compute.value`; the model never writes a number.
- **The chat shows only parts that read.** The chat kinds are `stat`, `trend`, `pipeline`, `list` and `thread`.
  - `queue` stays on the report: it asks for a verdict on each track, and a card in a message holds at most two actions.
  - `cards` stays on the report: what waits for a signature already stands in the reply as its own card.
  - `callout` stays on the report: her reply is the words.
  - A part of any of these kinds is dropped with that reason.
- **The daemon owns the layout.** Each part gets a daemon id (`part-1`...) and the full width (`span` 12), whatever the model asked for. The window is 400 px wide, so one part per row is all that fits.
- **Drops are disclosed, and nothing shown is still a row.** The turn streams one `blocks` event in emitted order among the parts: `{type: "blocks", shown: {blocks, values, dropped, reasons}}`. It is streamed even when every part was dropped, so the person reads "1 part could not be shown" and why. The model is told what was shown, fenced as record data, and told not to repeat the figures. When nothing was shown, it is told to answer in words.
- **When to use it is taught in the tool's description,** generated from the kit (`vocab.parts_docs`) and the kinds the project keeps, after fixed routing rules: comparative or quantitative answers about the records (three or more things side by side, counts across stages, a reading over time, the latest entries of a kind), and never a fact, a how-to, a yes or no, or one number.
- **Where it is offered.** Only to a chat turn in a project that keeps records, the rule `record_list` follows (`report.chat.offered`, in `turn._stream` and `mcp.chat_tools`). A Claude Code turn reaches it through its own lease. An outside client's lease never lists it, because an agent host has `show_report` ([ADR 0021](0021-the-project-report-is-also-a-view-inside-agent-hosts.md)).
- **A settled turn keeps the parts with the figures they showed then** (`BlocksPart` in `Turn.parts`). The transcript is a record of what she said, so a reload redraws the same parts with the same numbers. It does not recompute them.
- **The window draws them with the report's own `Block` components** (`athena/ReplyBlocks.tsx`). The pin is absent there (`BlockContext.onPin` is optional). There is no grid and no scroller of their own.

## Consequences

- A comparative answer in her window is counted by the daemon, as the report is, and a new block kind reaches the chat by one entry in `CHAT_KINDS`.
- A part in an old turn shows the figures of the moment it was shown. The project page is where the numbers are current.
- **Known gaps:**
  - Nothing measures whether she chooses this form at the right times. There is no labelled set of intents for `view-choice-evaluation` yet, so the routing rules are taught but not scored.
  - The simulated engine has no rule for `show_blocks`. It is offered there and never called.
  - A part is not checked against the routing rules in code. A single `stat` alone (one number) passes the door; the description is the only guard.
