"""Drafts: a chore written in conversation and tested against the person's own expectations (ADR 0007).

A draft walks `describe -> shape -> author -> preview -> rehearse -> verdict -> saved`. Shaping is a
stage turn in the draft's Project that changes a sketch (the person's picture of the process, not
the chore's source); the flow, never the model, computes coverage and decides when it is agreed.
Authoring writes a real chore folder in one step, the preview's marks become its answer key, a test
run on her practice apps is scored against that key, and a kept chore moves to the person's library.

Modules: `store` (the drafts table), `sketch` (applying ops), `rubric` (coverage), `shape` (stage
turns), `author`, `preview`, `key`, `rehearse`, `save`, and `routes`.
"""

from __future__ import annotations

DRAFT_PREFIX = "drf_"
