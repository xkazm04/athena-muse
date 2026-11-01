"""Routines (business Phase 2): the daemon's only background host.

A routine is a project's recurring job with a cadence, a spend ceiling and a kind. The host
(`host.py`) is the one owner of admission: a routine never overlaps itself or a chat turn in its
space, a refusal is recorded by name, and a run ends cleanly at its ceiling with what it covered.
Each kind (`watch`, `inbox`, `stats`, `outreach`, `twin`) is a function over a `RunContext`
(`context.py`): code reads her browser in a hidden tab, one tool-less model call extracts, and what
it finds goes through the records' own door.
"""
